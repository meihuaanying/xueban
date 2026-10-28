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
  const [phase, setPhase] = useState<MockExamPhase>("intro");
  const [exam, setExam] = useState<ExamCreate | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [index, setIndex] = useState(0);
  const [report, setReport] = useState<ExamReport | null>(null);
  const [grades, setGrades] = useState<Record<string, ExamSubjectiveGrade>>({});
  const [remaining, setRemaining] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const submittingRef = useRef(false);

  const start = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const created = await api.createBlueprintExam();
      setExam(created);
      setAnswers({});
      setGrades({});
      setReport(null);
      setIndex(0);
      setRemaining(secondsLeft(created.deadline));
      setPhase("running");
    } catch (caught) {
      setError(toFriendlyError(caught));
    } finally {
      setBusy(false);
    }
  }, []);

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
    setIndex: (next: number) => {
      if (!exam) return;
      setIndex(Math.min(Math.max(next, 0), exam.questions.length - 1));
    },
  };
}
