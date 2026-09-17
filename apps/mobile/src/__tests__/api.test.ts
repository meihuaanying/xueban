import { ApiError, api, coachApi, setAccessToken, streamTutorHint } from "../lib/api";

function mockFetch(payload: unknown, status = 200) {
  const fetchMock = jest.fn().mockResolvedValue({
    ok: status < 400,
    status,
    text: async () => JSON.stringify(payload),
    json: async () => payload,
  });
  (globalThis as unknown as { fetch: typeof fetchMock }).fetch = fetchMock;
  return fetchMock;
}

function lastRequest(fetchMock: jest.Mock): [string, RequestInit] {
  return fetchMock.mock.calls[0] as [string, RequestInit];
}

beforeEach(() => {
  setAccessToken(null);
  jest.clearAllMocks();
});

describe("移动端 API 端点拼装", () => {
  const cases: [string, () => Promise<unknown>, string, string?][] = [
    ["register", () => api.register({ phone: "13900000000", password: "password123" }), "/v1/auth/register", "POST"],
    ["login", () => api.login({ phone: "13900000000", password: "password123" }), "/v1/auth/login", "POST"],
    ["me", () => api.me(), "/v1/auth/me", "GET"],
    ["startDiagnosis", () => api.startDiagnosis({ subject: "math", stage: "junior", target_count: 20 }), "/v1/diagnosis/start", "POST"],
    ["answerDiagnosis", () => api.answerDiagnosis("e1", { question_id: "q1", answer: "A" }), "/v1/diagnosis/e1/answer", "POST"],
    ["diagnosisReport", () => api.diagnosisReport("e1"), "/v1/diagnosis/e1/report", "GET"],
    ["mastery", () => api.mastery(), "/v1/profile/mastery", "GET"],
    ["behavior", () => api.behavior(), "/v1/profile/behavior", "GET"],
    ["path", () => api.path(), "/v1/plan/path", "GET"],
    ["today", () => api.today(), "/v1/plan/today", "GET"],
    ["completeTask", () => api.completeTask("t1"), "/v1/plan/tasks/t1/complete", "POST"],
    ["createTutorSession", () => api.createTutorSession("q1"), "/v1/tutor/session", "POST"],
    ["tutorHint", () => api.tutorHint("s1", 2), "/v1/tutor/s1/hint", "POST"],
    ["generatePractice", () => api.generatePractice({ subject: "math", count: 5 }), "/v1/practice/generate", "POST"],
    [
      "answerPractice",
      () =>
        api.answerPractice({
          question_id: "q1",
          answer: "A",
          source: "practice",
          client_event_id: "evt-1",
        }),
      "/v1/practice/answer",
      "POST",
    ],
    ["mistakes", () => api.mistakes(), "/v1/mistakes?limit=20", "GET"],
    ["repractice", () => api.repractice(), "/v1/mistakes/repractice", "POST"],
    ["calendar", () => api.calendar(2026, 9), "/v1/stats/calendar?year=2026&month=9", "GET"],
    ["weeklyReport", () => api.weeklyReport(), "/v1/reports/weekly", "GET"],
    ["sprint", () => api.sprint(), "/v1/exam-prep/sprint", "GET"],
    ["guardianStatus", () => api.guardianStatus(), "/v1/guardian/status", "GET"],
    ["subscription", () => api.subscription(), "/v1/billing/subscription", "GET"],
    ["startTrial", () => api.startTrial(), "/v1/billing/trial", "POST"],
    [
      "presignUpload",
      () =>
        api.presignUpload({
          filename: "a.jpg",
          content_type: "image/jpeg",
          size_bytes: 1024,
        }),
      "/v1/storage/presign-upload",
      "POST",
    ],
  ];

  it.each(cases)("%s", async (_name, call, path, method) => {
    const fetchMock = mockFetch({});
    await call();
    const [url, init] = lastRequest(fetchMock);
    expect(url).toContain(path);
    if (method) expect((init.method ?? "GET").toUpperCase()).toBe(method);
  });

  it("携带 Bearer 令牌", async () => {
    setAccessToken("tok-mobile");
    const fetchMock = mockFetch({});
    await api.me();
    const [, init] = lastRequest(fetchMock);
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer tok-mobile");
  });

  it("错误响应抛 ApiError（code/message）", async () => {
    mockFetch({ code: "AUTH_BAD_CREDENTIALS", message: "手机号或密码错误" }, 401);
    await expect(api.login({ phone: "13900000000", password: "x" })).rejects.toBeInstanceOf(ApiError);
  });

  it("陪练端点", async () => {
    for (const [call, path] of [
      [() => coachApi.companion({ message: "hi" }), "/v1/coach/companion"],
      [() => coachApi.roleplay({ message: "hi", scene: "campus" }), "/v1/coach/roleplay"],
    ] as [() => Promise<unknown>, string][]) {
      const fetchMock = mockFetch({});
      await call();
      expect(lastRequest(fetchMock)[0]).toContain(path);
    }
  });
});

describe("SSE 流式提示（XHR 兼容实现）", () => {
  class FakeXHR {
    status = 200;
    responseText = "";
    onprogress: (() => void) | null = null;
    onload: (() => void) | null = null;
    onerror: (() => void) | null = null;
    headers: Record<string, string> = {};
    body: string | null = null;

    url = "";

    open(_method: string, url: string) {
      this.url = url;
    }

    setRequestHeader(key: string, value: string) {
      this.headers[key] = value;
    }

    send(body?: string) {
      this.body = body ?? null;
    }
  }

  function installXhr(frames: string[], status = 200) {
    const xhr = new FakeXHR();
    xhr.status = status;
    (globalThis as unknown as { XMLHttpRequest: unknown }).XMLHttpRequest = jest.fn(() => xhr);
    // 模拟分帧到达：逐段触发 onprogress，最后 onload
    setTimeout(() => {
      let accumulated = "";
      for (const frame of frames) {
        accumulated += frame;
        xhr.responseText = accumulated;
        xhr.onprogress?.();
      }
      xhr.onload?.();
    }, 0);
    return xhr;
  }

  it("解析 start/delta/done 并携带令牌", async () => {
    setAccessToken("tok-sse");
    const NL = String.fromCharCode(10);
    const frame = (...lines: string[]) => lines.join(NL) + NL + NL;
    const xhr = installXhr([
      frame('event: start', 'data: {"level":1,"level_name":"思路提示"}'),
      frame('event: delta', 'data: {"content":"先看条件"}'),
      frame(
        'event: done',
        'data: {"level":1,"level_name":"思路提示","content":"先看条件再找公式"}',
      ),
    ]);
    const events: string[] = [];
    const deltas: string[] = [];
    await streamTutorHint("s1", 1, {
      onStart: (payload) => events.push(`start:${payload.level_name}`),
      onDelta: (content) => deltas.push(content),
      onDone: (payload) => events.push(`done:${payload.content}`),
    });
    expect(events).toEqual(["start:思路提示", "done:先看条件再找公式"]);
    expect(deltas.join("")).toBe("先看条件");
    expect(xhr.headers.Authorization).toBe("Bearer tok-sse");
    expect(xhr.url).toContain("/v1/tutor/s1/hint/stream");
  });

  it("无 done 事件视为流中断", async () => {
    const NL = String.fromCharCode(10);
    installXhr([
      ['event: delta', 'data: {"content":"半句话"}'].join(NL) + NL + NL,
    ]);
    await expect(streamTutorHint("s2", 2, {})).rejects.toMatchObject({
      code: "LLM_STREAM_INTERRUPTED",
    });
  });

  it("HTTP 错误映射为 ApiError", async () => {
    installXhr(['{"code":"TUTOR_LEVEL_SKIPPED","message":"不能跳层"}'], 400);
    await expect(streamTutorHint("s3", 3, {})).rejects.toBeInstanceOf(ApiError);
  });

  it("网络错误回调拒绝", async () => {
    const xhr = new FakeXHR();
    (globalThis as unknown as { XMLHttpRequest: unknown }).XMLHttpRequest = jest.fn(() => xhr);
    setTimeout(() => xhr.onerror?.(), 0);
    await expect(streamTutorHint("s4", undefined, {})).rejects.toThrow("网络异常");
  });
});
