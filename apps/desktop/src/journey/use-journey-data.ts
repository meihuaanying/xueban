"use client";

/**
 * 旅程数据钩子（§7 P0：页面只做编排，数据与状态收在此处）。
 * 所有请求统一经 lib/api，绝不在此层写 mock；失败一律降级为空态并提示。
 */
import { useCallback, useEffect, useState } from "react";

import {
  ApiError,
  api,
  type DiagnosisAnswer,
  type DiagnosisStart,
  type MasteryOverview,
  type MistakeList,
  type PracticeAnswer,
  type PracticeGenerate,
  type ReviewDue,
  type TodayResponse,
  type WeeklyReport,
} from "../lib/api";

export interface AsyncState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}

const idle = <T,>(): AsyncState<T> => ({ data: null, loading: false, error: null });

/** 通用「取数 + 刷新」钩子 */
export function useAsync<T>(load: () => Promise<T>, deps: unknown[] = []) {
  const [state, setState] = useState<AsyncState<T>>(idle<T>);

  const run = useCallback(async () => {
    setState({ data: null, loading: true, error: null });
    try {
      setState({ data: await load(), loading: false, error: null });
    } catch (caught) {
      setState({
        data: null,
        loading: false,
        error: caught instanceof Error ? caught.message : "加载失败，请稍后重试。",
      });
    }
    // load 由调用方保证稳定；deps 显式声明触发条件
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    void run();
  }, [run]);

  return { ...state, reload: run };
}

/* ---------- 今日任务 ---------- */
export function useToday() {
  const [state, setState] = useState<AsyncState<TodayResponse>>(idle<TodayResponse>());

  const reload = useCallback(async () => {
    setState((prev) => ({ ...prev, loading: true, error: null }));
    try {
      setState({ data: await api.today(), loading: false, error: null });
    } catch (caught) {
      setState({
        data: null,
        loading: false,
        error: caught instanceof Error ? caught.message : "今日任务加载失败。",
      });
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  const complete = useCallback(async (taskId: string) => {
    const result = await api.completeTask(taskId);
    setState({ data: result.today, loading: false, error: null });
    return result;
  }, []);

  return { ...state, reload, complete };
}

/* ---------- 诊断 ---------- */
export function useDiagnosis() {
  const [start, setStart] = useState<DiagnosisStart | null>(null);
  const [last, setLast] = useState<DiagnosisAnswer | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [errorCode, setErrorCode] = useState<string | null>(null);

  const begin = useCallback(async (subject: string, stage: string, count = 20) => {
    setBusy(true);
    setError(null);
    setErrorCode(null);
    setLast(null);
    try {
      setStart(await api.startDiagnosis({ subject, stage, target_count: count }));
    } catch (caught) {
      // 409 题库暂无可用题目属正常空态（该学段题库待补），需与真故障区分
      if (caught instanceof ApiError) {
        setError(caught.message);
        setErrorCode(caught.code);
      } else {
        setError(caught instanceof Error ? caught.message : "诊断启动失败。");
        setErrorCode(null);
      }
    } finally {
      setBusy(false);
    }
  }, []);

  const answer = useCallback(async (questionId: string, value: string) => {
    if (!start) return;
    setBusy(true);
    setError(null);
    try {
      const result = await api.answerDiagnosis(start.exam_id, {
        question_id: questionId,
        answer: value,
      });
      setLast(result);
      setStart((prev) =>
        prev
          ? { ...prev, progress: result.progress, question: result.next_question ?? prev.question }
          : prev,
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "提交答案失败。");
    } finally {
      setBusy(false);
    }
  }, [start]);

  return { start, last, busy, error, errorCode, begin, answer, examId: start?.exam_id ?? null };
}

/* ---------- 掌握度 / 规划 ---------- */
export function useMastery(subject: string) {
  return useAsync<MasteryOverview>(() => api.mastery(subject), [subject]);
}

/* ---------- 练习 ---------- */
export function usePractice(subject: string) {
  const [set, setSet] = useState<PracticeGenerate | null>(null);
  const [index, setIndex] = useState(0);
  const [last, setLast] = useState<PracticeAnswer | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // 连续答错次数。§5.1 触发场景 1：连续 2 次答错即自动建议动画讲解。
  const [wrongStreak, setWrongStreak] = useState(0);

  const generate = useCallback(async () => {
    setBusy(true);
    setError(null);
    setLast(null);
    setWrongStreak(0);
    try {
      setSet(await api.generatePractice({ subject, count: 5 }));
      setIndex(0);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "出题失败，请稍后重试。");
    } finally {
      setBusy(false);
    }
  }, [subject]);

  const answer = useCallback(
    async (questionId: string, value: string) => {
      setBusy(true);
      setError(null);
      try {
        const result = await api.answerPractice({
          question_id: questionId,
          answer: value,
          source: "practice",
        });
        setLast(result);
        setWrongStreak((prev) => (result.is_correct ? 0 : prev + 1));
        return result;
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : "提交答案失败。");
        return null;
      } finally {
        setBusy(false);
      }
    },
    [],
  );

  const next = useCallback(() => {
    setLast(null);
    setIndex((prev) => prev + 1);
  }, []);

  return {
    set,
    index,
    current: set?.questions[index] ?? null,
    last,
    busy,
    error,
    wrongStreak,
    generate,
    answer,
    next,
  };
}

/* ---------- 错题本 ---------- */
export function useMistakes() {
  return useAsync<MistakeList>(() => api.mistakes({ limit: 20 }), []);
}

/* ---------- 复习卡（FSRS 到期） ---------- */
export function useReviewDue() {
  return useAsync<ReviewDue>(() => api.reviewDue(10), []);
}

/* ---------- 周复盘 ---------- */
export function useWeeklyReport() {
  return useAsync<WeeklyReport>(() => api.weeklyReport(), []);
}
