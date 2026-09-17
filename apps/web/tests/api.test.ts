import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  adminApi,
  apiRequest,
  fetchPlans,
  fetchSubscription,
  parentApi,
  registerAccount,
  startTrial,
  type Plan,
  type SubscriptionState,
  type TokenPair,
} from "@/lib/api";
import {
  clearTokens,
  loadAccessToken,
  saveAccessToken,
  saveTokens,
} from "@/lib/auth-storage";

const TOKEN_PAIR: TokenPair = {
  access_token: "access-1",
  refresh_token: "refresh-1",
  token_type: "bearer",
  expires_in: 900,
};

const SUBSCRIPTION: SubscriptionState = {
  plan: "trial",
  started_at: "2026-09-16T00:00:00Z",
  expires_at: "2026-09-23T00:00:00Z",
  trial_used: true,
  auto_renew: false,
};

const PLANS: Plan[] = [{ cycle: "monthly", title: "月度会员", price_cents: 3900, days: 30 }];

function mockFetch(payload: unknown, status = 200) {
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(JSON.stringify(payload), {
      status,
      headers: { "Content-Type": "application/json" },
    }),
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function lastRequest(fetchMock: ReturnType<typeof mockFetch>) {
  const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
  return { url, init };
}

beforeEach(() => {
  window.localStorage.clear();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("官网 API 客户端", () => {
  it("apiRequest 解析成功响应并附带 JSON 头", async () => {
    const fetchMock = mockFetch({ ok: true });
    const result = await apiRequest<{ ok: boolean }>("/v1/healthz");
    expect(result.ok).toBe(true);
    const { url, init } = lastRequest(fetchMock);
    expect(url).toContain("/v1/healthz");
    expect((init.headers as Record<string, string>)["Content-Type"]).toBe("application/json");
  });

  it("非 2xx 抛出 ApiError（含 code/trace_id）", async () => {
    mockFetch({ code: "AUTH_BAD_CREDENTIALS", message: "手机号或密码错误", trace_id: "t-1" }, 401);
    await expect(apiRequest("/v1/auth/login")).rejects.toMatchObject({
      name: "ApiError",
      status: 401,
      code: "AUTH_BAD_CREDENTIALS",
      traceId: "t-1",
    });
    mockFetch({ code: "AUTH_BAD_CREDENTIALS", message: "手机号或密码错误" }, 401);
    try {
      await apiRequest("/v1/auth/login");
    } catch (error) {
      expect(error).toBeInstanceOf(ApiError);
      expect((error as ApiError).message).toBe("手机号或密码错误");
    }
  });

  it("非 JSON 响应体回退默认错误信息", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("boom", { status: 503 })),
    );
    await expect(apiRequest("/v1/anything")).rejects.toMatchObject({ code: "HTTP_503" });
  });

  it("注册与订阅链路", async () => {
    const fetchMock = mockFetch(TOKEN_PAIR, 201);
    const tokens = await registerAccount({
      phone: "13900000000",
      password: "password123",
      role: "parent",
    });
    expect(tokens.access_token).toBe("access-1");
    const { init } = lastRequest(fetchMock);
    expect(JSON.parse(String(init.body))).toMatchObject({
      phone: "13900000000",
      role: "parent",
    });

    mockFetch(SUBSCRIPTION);
    expect((await startTrial("token")).plan).toBe("trial");
    mockFetch(SUBSCRIPTION);
    expect((await fetchSubscription("token")).trial_used).toBe(true);
    mockFetch(PLANS);
    expect((await fetchPlans())[0]!.title).toBe("月度会员");
  });

  it("parentApi 全部端点拼装正确并携带鉴权头", async () => {
    const fetchMock = mockFetch({});
    await parentApi.me("tok");
    expect(lastRequest(fetchMock).init.headers).toMatchObject({ Authorization: "Bearer tok" });

    const childrenMock = mockFetch([]);
    await parentApi.children("tok");
    expect(lastRequest(childrenMock).url).toContain("/v1/auth/parents/children");

    const bindMock = mockFetch({});
    await parentApi.bindChild("tok", "13800000000");
    expect(lastRequest(bindMock).init.method).toBe("POST");

    for (const call of [
      () => parentApi.dashboard("tok", "child-1"),
      () => parentApi.controls("tok", "child-1"),
      () => parentApi.safety("tok", "child-1"),
      () => parentApi.tasks("tok", "child-1"),
    ]) {
      mockFetch({});
      await call();
    }
    const controlsMock = mockFetch({});
    await parentApi.updateControls("tok", {
      child_id: "child-1",
      parent_password: "password123",
      is_enabled: true,
      daily_limit_minutes: 30,
      rest_after_minutes: 20,
    });
    expect(lastRequest(controlsMock).init.method).toBe("PUT");

    mockFetch({});
    await parentApi.confirmTask("tok", "task-1");
    mockFetch({});
    await parentApi.createLink("tok", "child-1");
    mockFetch({});
    await parentApi.revokeLink("tok", "share-1");
    mockFetch({});
    await parentApi.sharedDashboard("share-1");
  });

  it("adminApi 全部端点可用", async () => {
    mockFetch({ role: "admin" });
    await adminApi.me("tok");
    mockFetch({ access_token: "a" });
    expect((await adminApi.login("13900000000", "pw")).access_token).toBe("a");

    mockFetch({ total: 0, items: [] });
    await adminApi.questions("tok", { status: "draft", keyword: "分数" });
    mockFetch({});
    await adminApi.coverage("tok");
    mockFetch({});
    await adminApi.createQuestion("tok", {
      subject: "math",
      stem: "1+1",
      answer: "A",
      analysis: "解析",
    });
    mockFetch({});
    await adminApi.transition("tok", "q1", "review");
    mockFetch([]);
    await adminApi.versions("tok", "q1");
    mockFetch({});
    await adminApi.inspect("tok", 10);
    mockFetch([]);
    await adminApi.inspectionReports("tok");
    mockFetch({});
    await adminApi.metrics("tok");
    mockFetch([]);
    await adminApi.experiments("tok");
    mockFetch({});
    await adminApi.createExperiment("tok", {
      key: "exp-1",
      name: "实验",
      variants: [{ name: "control", weight: 1 }],
    });
    mockFetch({});
    await adminApi.experimentReport("tok", "exp-1");
  });
});

describe("登录态本地存储", () => {
  it("保存/读取/清理令牌", () => {
    saveTokens(TOKEN_PAIR);
    expect(loadAccessToken()).toBe("access-1");
    expect(window.localStorage.getItem("xueban.refresh_token")).toBe("refresh-1");

    saveAccessToken("override");
    expect(loadAccessToken()).toBe("override");

    clearTokens();
    expect(loadAccessToken()).toBeNull();
    expect(window.localStorage.getItem("xueban.refresh_token")).toBeNull();
  });
});
