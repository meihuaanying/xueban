import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api, type PracticeAnswer, type QuestionBrief } from "@/lib/api";

import { useRepractice } from "./use-repractice";

vi.mock("@/lib/api", () => ({
  api: { repractice: vi.fn(), answerPractice: vi.fn() },
}));

const repractice = vi.mocked(api.repractice);
const answerPractice = vi.mocked(api.answerPractice);

function question(id: string): QuestionBrief {
  return {
    id,
    stem: "1 + 1 等于几？",
    qtype: "choice",
    options: { A: "2", B: "3" },
    difficulty: 1,
    knowledge_points: ["10 以内加法"],
    knowledge_point_ids: ["0123456789abcdef0123456789abcdef"],
  };
}

function answer(overrides: Partial<PracticeAnswer> = {}): PracticeAnswer {
  return {
    is_correct: true,
    correct_answer: "A",
    next_difficulty: 2,
    mistake_collected: false,
    mistake_removed: false,
    card_due_at: null,
    explanation: "对啦",
    ...overrides,
  };
}

beforeEach(() => {
  repractice.mockReset();
  answerPractice.mockReset();
});

describe("useRepractice（§5.1 错题重做闭环）", () => {
  it("从错题本取题，按 repractice 来源提交并可逐题前进", async () => {
    repractice.mockResolvedValue({ count: 2, questions: [question("q1"), question("q2")] });
    answerPractice.mockResolvedValue(answer());
    const { result } = renderHook(() => useRepractice());

    await act(async () => {
      await result.current.start(2);
    });
    expect(repractice).toHaveBeenCalledWith({ count: 2 });
    expect(result.current.current?.id).toBe("q1");

    await act(async () => {
      await result.current.answer("A");
    });
    expect(answerPractice).toHaveBeenCalledWith({
      question_id: "q1",
      answer: "A",
      source: "repractice",
    });
    expect(result.current.last?.is_correct).toBe(true);
    expect(result.current.last?.explanation).toBe("对啦");

    act(() => result.current.next());
    expect(result.current.current?.id).toBe("q2");
    expect(result.current.last).toBeNull();
  });

  it("最后一题答完进入完成态", async () => {
    repractice.mockResolvedValue({ count: 1, questions: [question("q1")] });
    answerPractice.mockResolvedValue(answer());
    const { result } = renderHook(() => useRepractice());
    await act(async () => {
      await result.current.start(1);
    });
    await act(async () => {
      await result.current.answer("A");
    });
    act(() => result.current.next());
    expect(result.current.finished).toBe(true);
  });

  it("取题失败时保留错误并清掉半截题目", async () => {
    repractice.mockRejectedValue(new Error("网络断了"));
    const { result } = renderHook(() => useRepractice());
    await act(async () => {
      await result.current.start();
    });
    expect(result.current.busy).toBe(false);
    expect(result.current.error).toBe("网络断了");
    expect(result.current.set).toBeNull();
    expect(result.current.current).toBeNull();
  });
});
