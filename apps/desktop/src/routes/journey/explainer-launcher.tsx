"use client";

/**
 * 场景 2/3 的讲解入口（§5.1）
 *
 * - 场景 2：练习错题详情页 →「动画讲解这个知识点」
 * - 场景 3：知识地图节点 → 已预生成的讲解直接秒开
 *
 * 两个场景的区别只在「入口长在哪」，后面的链路完全一样（生成/缓存命中/沙箱
 * 渲染/降级），所以拆成两个部件复用：
 * - :func:`ExplainerTrigger` —— 入口按钮（kids 主题下 ≥48px 热区 + 图标 + TTS）
 * - :func:`ExplainerDock` —— 承载讲解页/降级视图的面板
 *
 * 刻意让 Trigger 与 Dock 分离：错题本可能有十几条，每条都塞一个讲解面板会把
 * 页面撑爆；正确形态是「点哪条看哪条，讲解只显示一份」。
 */

import { AudioButton, Button } from "@xueban/ui";

import { ExplainerCard } from "./explainer-blocks";
import type { useExplainer } from "@/journey/use-explainer";

/** :func:`useExplainer` 的返回类型（用 typeof 取，避免重复声明）。 */
export type ExplainerState = ReturnType<typeof useExplainer>;

export interface ExplainerTriggerProps {
  /** 课程知识点编码（如 `g1m-add-within-10`）。为空时按钮禁用，不生成垃圾讲解。 */
  knowledgeId: string;
  /** 传给 onOpen 的入口标识，用于区分是哪条错题发起的。 */
  testId: string;
  label?: string;
  speakable?: boolean;
  onOpen: (knowledgeId: string) => void;
}

const DEFAULT_LABEL = "动画讲解这个知识点";

export function ExplainerTrigger({
  knowledgeId,
  testId,
  label = DEFAULT_LABEL,
  speakable = false,
  onOpen,
}: ExplainerTriggerProps) {
  const text = label ?? DEFAULT_LABEL;
  const button = (
    <Button
      type="button"
      variant="outline"
      data-testid={testId}
      // 入口没有知识点就不给点：按下去只能得到一个「不知道讲什么」的讲解
      disabled={!knowledgeId}
      onClick={() => onOpen(knowledgeId)}
      className="min-h-[var(--tap-min)]"
    >
      <span aria-hidden className="mr-xs">
        🎬
      </span>
      {text}
    </Button>
  );
  // 朗读按钮是按钮的**兄弟**而不是子节点：button 里嵌 button 是非法 HTML，
  // 屏幕阅读器与键盘导航都会失灵。
  if (!speakable) return button;
  return (
    <span className="inline-flex items-center gap-hair">
      {button}
      <AudioButton text={`${text}，点一下就能看动画讲解`} />
    </span>
  );
}

export interface ExplainerDockProps {
  explainer: ExplainerState;
  /** 当前打开的知识点（可能为空，说明用户还没点任何入口）。 */
  knowledgeId: string;
  speakable?: boolean;
  testId?: string;
}

/**
 * 讲解面板。idle 时不渲染任何东西——入口由 :func:`ExplainerTrigger` 负责，
 * 这里只负责「已经打开之后」的生成中/就绪/失败三种状态与降级。
 */
export function ExplainerDock({
  explainer,
  knowledgeId,
  speakable = false,
  testId = "explainer-dock",
}: ExplainerDockProps) {
  if (!knowledgeId || explainer.status === "idle") return null;
  return (
    <div className="mt-md" data-testid={testId}>
      <ExplainerCard
        status={explainer.status}
        content={explainer.content}
        error={explainer.error}
        speakable={speakable}
        busy={explainer.status === "pending"}
        onOpen={() => void explainer.open(knowledgeId)}
        onRetry={() => void explainer.open(knowledgeId)}
        onClose={explainer.close}
        onFeedback={explainer.feedback}
      />
    </div>
  );
}
