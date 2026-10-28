"use client";

/** 错题重练：从错题本抽题 → 作答 → 刷新错题/复习卡（§5.1 闭环）。 */
import { useCallback, useState } from "react";

import { api, type MistakeRepractice, type PracticeAnswer } from "../lib/api";

export function useRepractice() {
  const [set, setSet] = useState<MistakeRepractice | null>(null);
  const [index, setIndex] = useState(0);
  const [last, setLast] = useState<PracticeAnswer | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [finished, setFinished] = useState(false);

  const start = useCallback(
    async (count = 5, scope: { subject?: string; stage?: string } = {}) => {
      setBusy(true);
      setError(null);
      setSet(null);
      setLast(null);
      setFinished(false);
      setIndex(0);
      try {
        setSet(await api.repractice({ count, ...scope }));
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : "取错题失败，请稍后重试。");
      } finally {
        setBusy(false);
      }
    },
    [],
  );

  const answer = useCallback(
    async (value: string) => {
      const current = set?.questions[index];
      if (!current) return null;
      setBusy(true);
      setError(null);
      try {
        const result = await api.answerPractice({
          question_id: current.id,
          answer: value,
          source: "repractice",
        });
        setLast(result);
        return result;
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : "提交答案失败。");
        return null;
      } finally {
        setBusy(false);
      }
    },
    [index, set],
  );

  const next = useCallback(() => {
    if (!set) return;
    setLast(null);
    if (index + 1 >= set.questions.length) {
      setFinished(true);
      return;
    }
    setIndex((prev) => prev + 1);
  }, [index, set]);

  return {
    set,
    index,
    current: set?.questions[index] ?? null,
    last,
    busy,
    error,
    finished,
    start,
    answer,
    next,
  };
}
