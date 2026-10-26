import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "./api";
import { AuthProvider, useAuth } from "./auth";
import { SyncIndicator, SyncProvider, useSync } from "./sync";
import { clearTokensSync, isTauri, loadTokens, saveTokens } from "./token-store";

vi.mock("./api", async () => {
  const actual = await vi.importActual<typeof import("./api")>("./api");
  return {
    ...actual,
    api: {
      me: vi.fn(),
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      syncState: vi.fn(),
    },
    setAccessToken: vi.fn(),
  };
});

const mockedApi = vi.mocked(api);

// 测试口令运行时生成：源码里不留口令字面量（安全扫描红线）
const TEST_PASSWORD = "Tst-" + crypto.randomUUID().slice(0, 12);

// 测试令牌运行时生成：源码里不留令牌字面量（安全扫描红线）
const ACCESS_TOKEN = "acc-" + crypto.randomUUID();
const REFRESH_TOKEN = "ref-" + crypto.randomUUID();

const TOKENS = {
  access_token: ACCESS_TOKEN,
  refresh_token: REFRESH_TOKEN,
  token_type: "bearer",
  expires_in: 900,
};

beforeEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
  clearTokensSync();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("登录态存储（keyring 回退 localStorage）", () => {
  it("浏览器环境走 localStorage", async () => {
    expect(isTauri()).toBe(false);
    await saveTokens(TOKENS);
    const tokens = await loadTokens();
    expect(tokens).toEqual({ accessToken: ACCESS_TOKEN, refreshToken: REFRESH_TOKEN });
  });

});

function AuthProbe() {
  const { status, user, login, register, logout, refreshUser } = useAuth();
  return (
    <div>
      <span data-testid="status">{status}</span>
      <span data-testid="user">{user?.phone ?? "-"}</span>
      <button onClick={() => void login("13900000000", TEST_PASSWORD)}>login</button>
      <button onClick={() => void register("13900000001", TEST_PASSWORD, "昵称")}>register</button>
      <button onClick={() => void logout()}>logout</button>
      <button onClick={() => void refreshUser()}>refresh</button>
    </div>
  );
}

const PROFILE = {
  id: "u1",
  phone: "13900000000",
  role: "student",
  nickname: null,
  is_k12: false,
  created_at: "2026-09-16T00:00:00Z",
};

describe("AuthProvider", () => {
  it("无令牌 → anonymous", async () => {
    render(
      <AuthProvider>
        <AuthProbe />
      </AuthProvider>,
    );
    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("anonymous"));
  });

  it("已存令牌 → 拉取用户进入 authenticated", async () => {
    window.localStorage.setItem("xueban.desktop.access_token", ACCESS_TOKEN);
    window.localStorage.setItem("xueban.desktop.refresh_token", REFRESH_TOKEN);
    mockedApi.me.mockResolvedValue(PROFILE);
    render(
      <AuthProvider>
        <AuthProbe />
      </AuthProvider>,
    );
    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("authenticated"));
    expect(screen.getByTestId("user").textContent).toBe("13900000000");
  });

  it("令牌失效（401）→ 清理并匿名", async () => {
    const { ApiError } = await vi.importActual<typeof import("./api")>("./api");
    window.localStorage.setItem("xueban.desktop.access_token", "stale");
    mockedApi.me.mockRejectedValue(new ApiError(401, { code: "AUTH_UNAUTHORIZED", message: "未认证" }));
    render(
      <AuthProvider>
        <AuthProbe />
      </AuthProvider>,
    );
    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("anonymous"));
    expect(window.localStorage.getItem("xueban.desktop.access_token")).toBeNull();
  });

  it("登录/注册/退出流程", async () => {
    mockedApi.login.mockResolvedValue(TOKENS);
    mockedApi.register.mockResolvedValue(TOKENS);
    mockedApi.me.mockResolvedValue(PROFILE);
    mockedApi.logout.mockResolvedValue(undefined);

    render(
      <AuthProvider>
        <AuthProbe />
      </AuthProvider>,
    );
    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("anonymous"));

    screen.getByText("login").click();
    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("authenticated"));

    screen.getByText("refresh").click();
    await waitFor(() => expect(mockedApi.me).toHaveBeenCalledTimes(2));

    screen.getByText("logout").click();
    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("anonymous"));

    screen.getByText("register").click();
    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("authenticated"));
    expect(mockedApi.register).toHaveBeenCalledWith({
      phone: "13900000001",
      password: TEST_PASSWORD,
      nickname: "昵称",
    });
  });
});

function SyncProbe() {
  const { version } = useSync();
  return <span data-testid="version">{version ?? "-"}</span>;
}

describe("SyncProvider（T9.1）", () => {
  it("轮询获取版本并渲染指示器", async () => {
    mockedApi.syncState.mockResolvedValue({
      version: "v1",
      summary: { completed_today: 1, total_today: 3, streak_days: 2, mistakes_active: 4 },
      server_time: "2026-09-16T00:00:00Z",
      channel: "sync:u1",
    });
    render(
      <SyncProvider>
        <SyncProbe />
        <SyncIndicator />
      </SyncProvider>,
    );
    await waitFor(() => expect(screen.getByTestId("version").textContent).toBe("v1"));
    expect(screen.getByTestId("sync-indicator").textContent).toContain("今日 1/3");
    expect(screen.getByTestId("sync-indicator").textContent).toContain("连续 2 天");
  });

  it("同步失败不影响渲染（下次轮询重试）", async () => {
    mockedApi.syncState.mockRejectedValue(new Error("network"));
    render(
      <SyncProvider>
        <SyncProbe />
        <SyncIndicator />
      </SyncProvider>,
    );
    await waitFor(() => expect(mockedApi.syncState).toHaveBeenCalled());
    expect(screen.queryByTestId("sync-indicator")).toBeNull();
  });
});
