"use client";

/** 新高考数学 19 题模考的数据层：组卷 → 作答 → 交卷 → 解答题逐题批改。 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  ApiError,
  api,
  type ExamCreate,
  type ExamReport,
  type ExamSubjectiveGrade,
} from "../lib/api";

export type MockExamPhase = "intro" | "running" | "report";

/** 刷新恢复用的 sessionStorage 键：只保存当前标签页的未完成考试。 */
export const MOCK_EXAM_STORAGE_KEY = "xueban.mockExam";

interface StoredMockExam {
  phase: MockExamPhase;
  exam: ExamCreate | null;
  answers: Record<string, string>;
  report: ExamReport | null;
  grades: Record<string, ExamSubjectiveGrade>;
}

function readStored(): StoredMockExam | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.sessionStorage.getItem(MOCK_EXAM_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<StoredMockExam>;
    if (parsed.phase !== "running" && parsed.phase !== "report") return null;
    if (!parsed.exam || !Array.isArray(parsed.exam.questions)) return null;
    if (parsed.phase === "report" && !parsed.report) return null;
    return {
      phase: parsed.phase,
      exam: parsed.exam,
      answers: parsed.answers ?? {},
      report: parsed.report ?? null,
      grades: parsed.grades ?? {},
    };
  } catch {
    return null;
  }
}

function writeStored(value: StoredMockExam | null): void {
  if (typeof window === "undefined") return;
  try {
    if (!value || value.phase === "intro") {
      window.sessionStorage.removeItem(MOCK_EXAM_STORAGE_KEY);
      return;
    }
    window.sessionStorage.setItem(MOCK_EXAM_STORAGE_KEY, JSON.stringify(value));
  } catch {
    // 隐私模式 / 配额不足：退回纯内存态，不阻断作答
  }
}

function toFriendlyError(caught: unknown): string {
  if (caught instanceof ApiError && caught.code === "EXAM_NO_QUESTIONS") {
    return "题库还在补充中，这一卷暂时组不出来；先去做今日任务，稍后再试。";
  }
  if (caught instanceof Error && caught.message) return caught.message;
  return "操作失败，请稍后重试。";
}

function secondsLeft(deadline: string | null): number | null {
  if (!deadline) return null;
  const ms = new Date(deadline).getTime() - Date.now();
  return Math.max(0, Math.floor(ms / 1000));
}

export function useMockExam() {
  const [restored] = useState(readStored);
  const [phase, setPhase] = useState<MockExamPhase>(restored?.phase ?? "intro");
  const [exam, setExam] = useState<ExamCreate | null>(restored?.exam ?? null);
  const [answers, setAnswers] = useState<Record<string, string>>(restored?.answers ?? {});
  const [index, setIndex] = useState(0);
  const [report, setReport] = useState<ExamReport | null>(restored?.report ?? null);
  const [grades, setGrades] = useState<Record<string, ExamSubjectiveGrade>>(
    restored?.grades ?? {},
  );
  // 恢复 running 时按原 deadline 续算，过期直接归零并触发自动交卷
  const [remaining, setRemaining] = useState<number | null>(() =>
    secondsLeft(restored?.exam?.deadline ?? null),
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const submittingRef = useRef(false);

  // 答卷快照随状态落盘：交卷/批改成功后的新 report/grades 也会被写入
  useEffect(() => {
    writeStored({ phase, exam, answers, report, grades });
  }, [answers, exam, grades, phase, report]);

  const discard = useCallback(() => {
    writeStored(null);
    setPhase("intro");
    setExam(null);
    setAnswers({});
    setReport(null);
    setGrades({});
    setIndex(0);
    setRemaining(null);
    setError(null);
  }, []);

  const start = useCallback(async () => {
    // 开始新卷即作废旧卷快照，组卷失败也不回到上一份报告
    discard();
    setBusy(true);
    try {
      const created = await api.createBlueprintExam();
      setExam(created);
      setRemaining(secondsLeft(created.deadline));
      setPhase("running");
    } catch (caught) {
      setError(toFriendlyError(caught));
    } finally {
      setBusy(false);
    }
  }, [discard]);

  const answer = useCallback((questionId: string, value: string) => {
    setAnswers((prev) => ({ ...prev, [questionId]: value }));
  }, []);

  const submit = useCallback(async () => {
    if (!exam || submittingRef.current) return;
    submittingRef.current = true;
    setBusy(true);
    setError(null);
    try {
      const payload = Object.entries(answers).map(([question_id, value]) => ({
        question_id,
        answer: value,
      }));
      const result = await api.submitExam(exam.exam_id, payload);
      setReport(result);
      setPhase("report");
    } catch (caught) {
      setError(toFriendlyError(caught));
    } finally {
      submittingRef.current = false;
      setBusy(false);
    }
  }, [answers, exam]);

  const gradeSubjective = useCallback(
    async (questionId: string, studentAnswer: string) => {
      if (!exam) return;
      setBusy(true);
      setError(null);
      try {
        const result = await api.gradeExamSubjective(exam.exam_id, {
          question_id: questionId,
          student_answer: studentAnswer,
        });
        setGrades((prev) => ({ ...prev, [questionId]: result }));
      } catch (caught) {
        setError(toFriendlyError(caught));
      } finally {
        setBusy(false);
      }
    },
    [exam],
  );

  useEffect(() => {
    if (phase !== "running" || !exam) return;
    const tick = () => setRemaining(secondsLeft(exam.deadline));
    tick();
    const timer = window.setInterval(tick, 1_000);
    return () => window.clearInterval(timer);
  }, [exam, phase]);

  // 倒计时归零自动交卷（服务端也会在读取报告时兜底自动收卷）
  useEffect(() => {
    if (phase === "running" && remaining === 0) void submit();
  }, [phase, remaining, submit]);

  const current = exam?.questions[index] ?? null;
  const answeredCount = useMemo(
    () => (exam ? exam.questions.filter((item) => answers[item.id]).length : 0),
    [answers, exam],
  );
  const subjectiveCount = useMemo(
    () => (exam ? exam.questions.filter((item) => item.qtype === "short_answer").length : 0),
    [exam],
  );
  const gradedCount = Object.keys(grades).length;

  return {
    phase,
    exam,
    current,
    index,
    total: exam?.questions.length ?? 0,
    answers,
    answeredCount,
    subjectiveCount,
    report,
    grades,
    gradedCount,
    remaining,
    busy,
    error,
    start,
    answer,
    submit,
    gradeSubjective,
    discard,
    setIndex: (next: number) => {
      if (!exam) return;
      setIndex(Math.min(Math.max(next, 0), exam.questions.length - 1));
    },
  };
}
