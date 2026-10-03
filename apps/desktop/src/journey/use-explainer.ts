"use client";

/** 交互讲解的数据层（§5）：202 提交 + 轮询 + 降级 + 反馈回流。 */

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, api, type ExplainerContent } from "../lib/api";

/** 轮询间隔。讲���是给一年级孩子看的，进度提示要密一些。 */
const POLL_INTERVAL_MS = 1_500;
/** 轮询上限兜底：后端 §5.4 渲染超时 60s，这里留一倍余量后停止，避免无限轮询。 */
const MAX_POLL_MS = 150_000;

/** 学生视角的错误文案。额度用完要说人话，其余按 §5.4「不白屏」原则给可执行的下一步。 */
function toFriendlyError(caught: unknown): string {
  if (caught instanceof ApiError && caught.code === "EXPLAINER_QUOTA_EXCEEDED") {
    return "今天的讲解次数用完啦，先去练几道题，明天再来～";
  }
  if (caught instanceof Error && caught.message) return caught.message;
  return "讲解加载失败，请稍后重试。";
}

/**
 * 交互讲解会话。
 *
 * 三条红线在这里落地：
 * 1. 生成失败**不抛给页面**，而是给出可重试的降级入口（§5.4 降级不白屏）；
 * 2. 每用户每日 20 次限额由后端裁决，前端只把超限翻译成孩子能懂的话；
 * 3. 组件卸载或换知识点后，旧轮询立即作废（token 比对），不写入已卸载状态。
 */
export function useExplainer() {
  const [content, setContent] = useState<ExplainerContent | null>(null);
  const [status, setStatus] = useState<"idle" | "pending" | "ready" | "failed">("idle");
  const [error, setError] = useState<string | null>(null);
  /** 孩子主动关掉「看讲解」后不再反复弹；重新 open 或错题数变化时由调用方决定。 */
  const [dismissed, setDismissed] = useState(false);
  /** 每次 open 自增；轮询回调发现 token 过期就静默退出。 */
  const tokenRef = useRef(0);

  const poll = useCallback(
    async (jobId: string, token: number) => {
      const deadline = Date.now() + MAX_POLL_MS;
      for (;;) {
        if (token !== tokenRef.current) return;
        const job = await api.explainerJob(jobId);
        if (token !== tokenRef.current) return;
        if (job.status === "ready" && job.content) {
          setContent(job.content);
          setStatus("ready");
          return;
        }
        if (job.status === "failed") {
          setError(job.error ?? "讲解没能生成出来，换个时间再试试。");
          setStatus("failed");
          return;
        }
        if (Date.now() > deadline) {
          // 超时不判失败：内容可能仍会好，交给「重看讲解」按钮再拉一次即可。
          setError("讲解生成得有点久，先去练题，稍后再点「看讲解」。");
          setStatus("failed");
          return;
        }
        await new Promise((resolve) => window.setTimeout(resolve, POLL_INTERVAL_MS));
      }
    },
    [],
  );

  const open = useCallback(
    async (knowledgeId: string) => {
      if (!knowledgeId) return;
      const token = ++tokenRef.current;
      setContent(null);
      setError(null);
      setDismissed(false);
      setStatus("pending");
      try {
        const created = await api.generateExplainer(knowledgeId);
        if (token !== tokenRef.current) return;
        // 缓存命中：后端直接 200 带内容，不必轮询（§5.2 三级缓存的第一级）。
        if (created.content) {
          setContent(created.content);
          setStatus("ready");
          return;
        }
        await poll(created.job_id, token);
      } catch (caught) {
        if (token !== tokenRef.current) return;
        setError(toFriendlyError(caught));
        setStatus("failed");
      }
    },
    [poll],
  );

  const close = useCallback(() => {
    // 作废在途轮询，但不丢弃已生成内容——孩子切回来还要接着看。
    tokenRef.current += 1;
    setDismissed(true);
    setStatus("idle");
  }, []);

  const feedback = useCallback(
    async (understood: boolean) => {
      if (!content) return;
      try {
        await api.explainerFeedback(content.id, understood);
      } catch {
        // 反馈是「锦上添花」，失败不该打断孩子继续学（§5.4 降级不白屏）。
      }
    },
    [content],
  );

  useEffect(() => () => {
    tokenRef.current += 1;
  }, []);

  return { content, status, error, dismissed, open, close, feedback };
}