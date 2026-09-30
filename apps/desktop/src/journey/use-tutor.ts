"use client";

/** 学习单元页的讲解会话状态（守护型三层提示的数据层）。 */

import { useCallback, useState } from "react";

import { api, type TutorHint, type TutorSession } from "../lib/api";

/**
 * 讲解会话：进入讲解即拉第 1 层提示，后续层由学生主动索取（三层之后仍不给答案）。
 * LLM 不可用时把原因上抛给 UI，而不是留下空白提示区（REBUILD §8 约束 4 / §5.4 降级不白屏）。
 */
export function useTutorHints() {
  const [session, setSession] = useState<TutorSession | null>(null);
  const [hints, setHints] = useState<TutorHint[]>([]);
  const [revealed, setRevealed] = useState(1);
  const [error, setError] = useState<string | null>(null);

  const openTutor = useCallback(async (questionId: string) => {
    setHints([]);
    setRevealed(1);
    setError(null);
    try {
      const created = await api.createTutorSession(questionId);
      setSession(created);
      const first = await api.tutorHint(created.session_id);
      setHints([first]);
      setRevealed(first.level ?? 1);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "讲解加载失败，请稍后重试。");
    }
  }, []);

  const askHint = useCallback(
    async (level?: number) => {
      if (!session) return;
      try {
        const next = await api.tutorHint(session.session_id, level);
        setHints((prev) =>
          prev.some((item) => item.level === next.level) ? prev : [...prev, next],
        );
        if (next.level) setRevealed(next.level);
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : "提示加载失败，请稍后重试。");
      }
    },
    [session],
  );

  return { session, hints, revealed, error, openTutor, askHint };
}
