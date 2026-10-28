import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, api, type ExamCreate, type ExamReport, type ExamSubjectiveGrade } from "@/lib/api";

import { useMockExam } from "./use-mock-exam";

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    api: {
      createBlueprintExam: vi.fn(),
      submitExam: vi.fn(),
      gradeExamSubjective: vi.fn(),
    },
  };
});

const createBlueprintExam = vi.mocked(api.createBlueprintExam);
const submitExam = vi.mocked(api.submitExam);
const gradeExamSubjective = vi.mocked(api.gradeExamSubjective);

function exam(): ExamCreate {
  return {
    exam_id: "exam-1",
    kind: "mock",
    title: "高考数学新结构模考",
    time_limit_minutes: 120,
    deadline: new Date(Date.now() + 120 * 60_000).toISOString(),
    questions: [
      {
        id: "q1",
        stem: "1 + 1 = ?",
        qtype: "choice",
        options: { A: "2", B: "3" },
        difficulty: 1,
        knowledge_points: ["集合"],
        knowledge_point_ids: ["k1"],
      },
      {
        id: "q2",
        stem: "求导",
        qtype: "short_answer",
        options: null,
        difficulty: 3,
        knowledge_points: ["导数"],
        knowledge_point_ids: ["k2"],
      },
    ],
  };
}

function report(): ExamReport {
  return {
    exam_id: "exam-1",
    kind: "mock",
    status: "SUBMITTED",
    auto_submitted: false,
    summary: {
      objective_earned: 5,
      objective_total: 5,
      subjective_total: 13,
      subjective_pending: 1,
      score: null,
    },
    diagnoses: [
      {
        question_id: "q1",
        stem: "1 + 1 = ?",
        is_correct: true,
        correct_answer: "A",
        analysis: null,
      },
      {
        question_id: "q2",
        stem: "求导",
        is_correct: null,
        correct_answer: "略",
        analysis: null,
        subjective: true,
      },
    ],
    submitted_at: null,
  };
}

function grade(examScore: number | null): ExamSubjectiveGrade {
  return {
    question_id: "q2",
    score: 10.4,
    max_score: 13,
    exam_score: examScore,
    graded_count: examScore === null ? 0 : 1,
    subjective_count: 1,
    all_graded: examScore !== null,
    steps: [],
    rewrite: "",
    summary: "还不错",
    machine_check: null,
  };
}

beforeEach(() => {
  createBlueprintExam.mockReset();
  submitExam.mockReset();
  gradeExamSubjective.mockReset();
});

describe("useMockExam（19 题蓝图模考）", () => {
  it("组卷 → 作答 → 交卷 → 解答题批改", async () => {
    createBlueprintExam.mockResolvedValue(exam());
    submitExam.mockResolvedValue(report());
    gradeExamSubjective.mockResolvedValue(grade(null));
    const { result } = renderHook(() => useMockExam());

    await act(async () => {
      await result.current.start();
    });
    expect(result.current.phase).toBe("running");
    expect(result.current.total).toBe(2);
    expect(result.current.subjectiveCount).toBe(1);
    expect(result.current.remaining).toBeGreaterThan(7_000);

    act(() => {
      result.current.answer("q1", "A");
      result.current.answer("q2", "解答过程");
      result.current.setIndex(5);
    });
    expect(result.current.answeredCount).toBe(2);
    expect(result.current.index).toBe(1); // 越界钳到最后一题

    await act(async () => {
      await result.current.submit();
    });
    expect(submitExam).toHaveBeenCalledWith("exam-1", [
      { question_id: "q1", answer: "A" },
      { question_id: "q2", answer: "解答过程" },
    ]);
    expect(result.current.phase).toBe("report");
    expect(result.current.report?.summary.objective_earned).toBe(5);

    await act(async () => {
      await result.current.gradeSubjective("q2", "解答过程");
    });
    expect(gradeExamSubjective).toHaveBeenCalledWith("exam-1", {
      question_id: "q2",
      student_answer: "解答过程",
    });
    expect(result.current.gradedCount).toBe(1);
    expect(result.current.grades.q2.score).toBe(10.4);
  });

  it("组卷失败时给出可执行文案且不进入作答", async () => {
    createBlueprintExam.mockRejectedValue(new ApiError(409, {
      message: "题库中「多项选择题」题量不足（需要 3 道）",
      code: "EXAM_NO_QUESTIONS",
    }));
    const { result } = renderHook(() => useMockExam());

    await act(async () => {
      await result.current.start();
    });
    expect(result.current.phase).toBe("intro");
    expect(result.current.error).toContain("题库还在补充中");
  });
});
