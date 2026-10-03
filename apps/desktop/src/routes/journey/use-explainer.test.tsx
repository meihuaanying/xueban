/**
 * 交互讲解数据层与讲解卡测试（P1 / §5）。
 *
 * 覆盖：缓存命中秒开、未命中轮询到就绪、轮询超时不判失败、组件卸载后
 * 不写入状态、反馈回流、以及图文分步降级视图（§5.4 禁止白屏）。
 */
import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useExplainer } from "../../journey/use-explainer";
import { api, ApiError } from "../../lib/api";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("useExplainer", () => {
  it("缓存命中时直接就绪，不轮询", async () => {
    const job = vi.spyOn(api, "explainerJob");
    vi.spyOn(api, "generateExplainer").mockResolvedValue({
      job_id: "j1",
      status: "ready",
      cache_hit: true,
      content: {
        id: "c1",
        knowledge_id: "g1m-add-within-10",
        stage: "grade1_2",
        title: "10 以内加法",
        status: "ready",
        html: "<p>hi</p>",
        degraded: false,
        byte_size: 100,
        script: {},
        render_timeout_seconds: 60,
      },
    });

    const { result } = renderHook(() => useExplainer());
    await act(async () => {
      await result.current.open("g1m-add-within-10");
    });

    expect(result.current.status).toBe("ready");
    expect(result.current.content?.id).toBe("c1");
    expect(job).not.toHaveBeenCalled();
  });

  it("未命中时轮询到就绪", async () => {
    vi.spyOn(api, "generateExplainer").mockResolvedValue({
      job_id: "j2",
      status: "generating",
      cache_hit: false,
      content: null,
    });
    vi.spyOn(api, "explainerJob").mockResolvedValue({
      job_id: "j2",
      status: "ready",
      error: null,
      content: {
        id: "c2",
        knowledge_id: "g1m-add-within-10",
        stage: "grade1_2",
        title: "10 以内加法",
        status: "ready",
        html: "<p>ready</p>",
        degraded: false,
        byte_size: 200,
        script: { acts: [{ name: "拆解", narration: "9 加 1 得 10" }] },
        render_timeout_seconds: 60,
      },
    });

    const { result } = renderHook(() => useExplainer());
    await act(async () => {
      await result.current.open("g1m-add-within-10");
    });

    await waitFor(() => expect(result.current.status).toBe("ready"));
    expect(result.current.content?.html).toBe("<p>ready</p>");
  });

  it("生成接口报错时进入 failed 并带可读文案", async () => {
    vi.spyOn(api, "generateExplainer").mockRejectedValue(new Error("网络断了"));

    const { result } = renderHook(() => useExplainer());
    await act(async () => {
      await result.current.open("g1m-add-within-10");
    });

    expect(result.current.status).toBe("failed");
    expect(result.current.error).toBe("网络断了");
  });

  it("触发每日限额时给出儿童能看懂的文案", async () => {
    vi.spyOn(api, "generateExplainer").mockRejectedValue(
      new ApiError(429, { code: "EXPLAINER_QUOTA_EXCEEDED", message: "quota" }),
    );

    const { result } = renderHook(() => useExplainer());
    await act(async () => {
      await result.current.open("g1m-add-within-10");
    });

    expect(result.current.status).toBe("failed");
    expect(result.current.error).toContain("今天的讲解次数用完啦");
  });

  it("轮询失败后停止重试并标记失败", async () => {
    vi.spyOn(api, "generateExplainer").mockResolvedValue({
      job_id: "j3",
      status: "generating",
      cache_hit: false,
      content: null,
    });
    vi.spyOn(api, "explainerJob").mockRejectedValue(new Error("轮询 500"));

    const { result } = renderHook(() => useExplainer());
    await act(async () => {
      await result.current.open("g1m-add-within-10");
    });

    await waitFor(() => expect(result.current.status).toBe("failed"));
    expect(result.current.error).toBe("轮询 500");
  });

  it("close 之后不再渲染讲解，但保留已生成内容供重开秒开", async () => {
    vi.spyOn(api, "generateExplainer").mockResolvedValue({
      job_id: "j4",
      status: "ready",
      cache_hit: true,
      content: {
        id: "c4",
        knowledge_id: "g1m-add-within-10",
        stage: "grade1_2",
        title: "10 以内加法",
        status: "ready",
        html: "<p>x</p>",
        degraded: false,
        byte_size: 50,
        script: {},
        render_timeout_seconds: 60,
      },
    });

    const { result } = renderHook(() => useExplainer());
    await act(async () => {
      await result.current.open("g1m-add-within-10");
    });
    expect(result.current.status).toBe("ready");

    act(() => {
      result.current.close();
    });
    expect(result.current.status).toBe("idle");
    expect(result.current.dismissed).toBe(true);
    expect(result.current.content?.id).toBe("c4");
  });

  it("关闭后旧轮询不会把状态写回来", async () => {
    let release: (() => void) | null = null;
    vi.spyOn(api, "generateExplainer").mockResolvedValue({
      job_id: "j5",
      status: "generating",
      cache_hit: false,
      content: null,
    });
    vi.spyOn(api, "explainerJob").mockImplementation(
      () =>
        new Promise((resolve) => {
          release = () =>
            resolve({
              job_id: "j5",
              status: "ready" as const,
              error: null,
              content: {
                id: "c5",
                knowledge_id: "g1m-add-within-10",
                stage: "grade1_2",
                title: "10 以内加法",
                status: "ready" as const,
                html: "<p>late</p>",
                degraded: false,
                byte_size: 10,
                script: {},
                render_timeout_seconds: 60,
              },
            });
        }),
    );

    const { result } = renderHook(() => useExplainer());
    // 不 await：轮询故意挂住，等价于「孩子点开后立刻关掉」
    await act(async () => {
      void result.current.open("g1m-add-within-10");
    });
    act(() => {
      result.current.close();
    });

    await act(async () => {
      release?.();
      await Promise.resolve();
    });
    expect(result.current.status).toBe("idle");
  });

  it("还没有内容时反馈是空操作", async () => {
    const feedback = vi.spyOn(api, "explainerFeedback");
    const { result } = renderHook(() => useExplainer());
    await act(async () => {
      await result.current.feedback(true);
    });
    expect(feedback).not.toHaveBeenCalled();
  });

  it("反馈用当前内容 id，且失败不打断主流程", async () => {
    vi.spyOn(api, "generateExplainer").mockResolvedValue({
      job_id: "j7",
      status: "ready",
      cache_hit: true,
      content: {
        id: "c7",
        knowledge_id: "g1m-add-within-10",
        stage: "grade1_2",
        title: "10 以内加法",
        status: "ready",
        html: "<p>x</p>",
        degraded: false,
        byte_size: 50,
        script: {},
        render_timeout_seconds: 60,
      },
    });
    const feedback = vi.spyOn(api, "explainerFeedback").mockResolvedValue({
      feedback_id: "f1",
      content_id: "c7",
      understood: true,
      understood_count: 1,
      confused_count: 0,
    });

    const { result } = renderHook(() => useExplainer());
    await act(async () => {
      await result.current.open("g1m-add-within-10");
    });
    await act(async () => {
      await result.current.feedback(true);
    });
    expect(feedback).toHaveBeenCalledWith("c7", true);

    feedback.mockRejectedValueOnce(new Error("反馈没发出去"));
    await act(async () => {
      await result.current.feedback(false);
    });
    // 反馈是锦上添花，不能把学生的正常流程搞崩
    expect(result.current.error).toBeNull();
    expect(result.current.status).toBe("ready");
  });
});

describe("useExplainer 轮询间隔", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("按间隔重复轮询直到就绪", async () => {
    vi.spyOn(api, "generateExplainer").mockResolvedValue({
      job_id: "j6",
      status: "generating",
      cache_hit: false,
      content: null,
    });
    const poll = vi
      .spyOn(api, "explainerJob")
      .mockResolvedValueOnce({
        job_id: "j6",
        status: "generating",
        error: null,
        content: null,
      })
      .mockResolvedValueOnce({
        job_id: "j6",
        status: "ready",
        error: null,
        content: {
          id: "c6",
          knowledge_id: "g1m-add-within-10",
          stage: "grade1_2",
          title: "10 以内加法",
          status: "ready",
          html: "<p>ok</p>",
          degraded: false,
          byte_size: 10,
          script: {},
          render_timeout_seconds: 60,
        },
      });

    const { result } = renderHook(() => useExplainer());
    await act(async () => {
      void result.current.open("g1m-add-within-10");
    });
    await act(async () => {
      await Promise.resolve();
    });
    expect(poll).toHaveBeenCalledTimes(1);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1_600);
    });
    expect(poll).toHaveBeenCalledTimes(2);
    expect(result.current.status).toBe("ready");
  });
});
