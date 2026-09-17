import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, setAccessToken, streamTutorHint } from "./api";

function sseResponse(chunks: string[]): Response {
  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });
  return new Response(stream, { status: 200, headers: { "Content-Type": "text/event-stream" } });
}

afterEach(() => {
  vi.restoreAllMocks();
  setAccessToken(null);
});

describe("SSE 流式提示解析（T5.4）", () => {
  it("按 start → delta → done 顺序回调并携带鉴权头", async () => {
    setAccessToken("token-123");
    const fetchMock = vi.fn().mockResolvedValue(
      sseResponse([
        'event: start\ndata: {"level":1,"level_name":"思路提示"}\n\n',
        'event: delta\ndata: {"content":"先观察"}\n\n',
        'event: delta\ndata: {"content":"已知条件"}\n\n',
        'event: done\ndata: {"level":1,"level_name":"思路提示","content":"先观察已知条件"}\n\n',
      ]),
    );
    vi.stubGlobal("fetch", fetchMock);

    const events: string[] = [];
    const deltas: string[] = [];
    await streamTutorHint("session-1", 1, {
      onStart: (payload) => events.push(`start:${payload.level_name}`),
      onDelta: (content) => deltas.push(content),
      onDone: (payload) => events.push(`done:${payload.content}`),
    });

    expect(events).toEqual(["start:思路提示", "done:先观察已知条件"]);
    expect(deltas.join("")).toBe("先观察已知条件");
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/v1/tutor/session-1/hint/stream");
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer token-123");
  });

  it("流中断（无 done 事件）抛出明确错误", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        sseResponse(['event: delta\ndata: {"content":"半句话"}\n\n']),
      ),
    );
    await expect(streamTutorHint("session-2", 2, {})).rejects.toMatchObject({
      code: "LLM_STREAM_INTERRUPTED",
    });
  });

  it("HTTP 错误映射为 API 错误契约", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ code: "TUTOR_LEVEL_SKIPPED", message: "不能跳层", trace_id: "t1" }), {
          status: 400,
        }),
      ),
    );
    await expect(streamTutorHint("session-3", 3, {})).rejects.toBeInstanceOf(ApiError);
  });
});
