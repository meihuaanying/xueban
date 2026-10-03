"use client";

import type { CSSProperties, HTMLAttributes, ReactNode } from "react";

import { cn } from "../cn";
import { AudioButton } from "./audio-button";
import { MasteryBar } from "./mastery-bar";

/** 掌握度档位 1~5（与 --mastery-1..5 对应，Khan 式核心视觉语言） */
export type MasteryLevel = 1 | 2 | 3 | 4 | 5;

export const MASTERY_LABELS: Record<MasteryLevel, string> = {
  1: "未接触",
  2: "初识",
  3: "入门",
  4: "熟练",
  5: "精通",
};

export interface KnowledgeNode {
  id: string;
  label: string;
  /**
   * 方块里显示的短名（可选）。`label` 是完整知识点名（「20 以内数的认识」），
   * 直接塞进 52/64px 的方块必然溢出——所以视觉用短名，无障碍与朗读仍用完整名。
   */
  shortLabel?: string;
  level: MasteryLevel;
  /** 掌握度 0~1；省略时用 level 换算的默认进度 */
  progress?: number;
  subject?: string;
  href?: string;
  locked?: boolean;
  /** 该知识点已有交互讲解（场景 3：已预生成的讲解直接秒开） */
  hasExplainer?: boolean;
}

export interface KnowledgeMapProps
  extends Omit<HTMLAttributes<HTMLDivElement>, "onSelect"> {
  nodes: KnowledgeNode[];
  /** 学科标题，如「数学」 */
  title?: string;
  /** 单个节点尺寸覆盖（默认 --kmap-node） */
  nodeSize?: string;
  caption?: ReactNode;
  /**
   * 点击节点（场景 3）。传了就把节点渲染成可点按钮，不传仍是纯展示。
   * 刻意做成可选：这个组件同时服务「只展示」和「可导航」两种用法，
   * 默认给所有节点套上点击态反而会误导——看起来能点却点不动。
   *
   * 名字借了 DOM 的 `onSelect`（而不是 `onNodeClick` 之类），但语义不同，
   * 所以必须 Omit 掉 DOM 版本，否则类型不兼容还容易被误用。
   */
  onSelect?: (id: string) => void;
  speakable?: boolean;
}

function defaultProgress(level: MasteryLevel): number {
  return { 1: 0, 2: 0.3, 3: 0.6, 4: 0.85, 5: 1 }[level];
}

/**
 * 知识地图（Khan 式导航）。
 * 节点底色 = 掌握度档位色（--mastery-N），节点尺寸随主题变化（focus 52px / kids 64px），
 * 低档位节点仍提供 TTS 朗读按钮（kids 7 岁可用性要求：一切文本可朗读）。
 */
export function KnowledgeMap({
  className,
  nodes,
  title,
  nodeSize,
  caption,
  onSelect,
  speakable = false,
  ...props
}: KnowledgeMapProps) {
  return (
    <section
      aria-label={title ?? "知识地图"}
      className={cn(
        "rounded-card border border-border bg-card p-sm text-card-foreground shadow-card",
        className,
      )}
      {...props}
    >
      {title ? (
        <header className="mb-xs flex items-center justify-between gap-xs">
          <h3 className="text-app font-semibold">{title}</h3>
          {caption}
        </header>
      ) : null}
      <ul className="flex flex-wrap gap-xs" role="list">
        {nodes.map((node) => {
          const progress = node.progress ?? defaultProgress(node.level);
          const size = nodeSize ?? "var(--kmap-node)";
          // 方块内只放短名；完整名留给 sr-only 与朗读，避免中文长名撑破方块。
          const visual = node.shortLabel ?? node.label;
          const body = (
            <>
              <span
                aria-hidden="true"
                className={cn(
                  "block leading-none font-bold",
                  visual.length > 3 ? "text-app-sm" : "text-app-lg",
                )}
                style={{ color: node.level >= 4 ? "var(--primary-foreground)" : "var(--card)" }}
              >
                {visual}
              </span>
              {/* sr-only 是 position:absolute 且没定 top/left，会贴到 relative 按钮的
                  (0,0)；不加 pointer-events-none 时它会盖在按钮中心点上，自动化点击
                  被判成「被别的元素拦截」。读屏专用文本永远不该拦指针。 */}
              <span className="pointer-events-none sr-only">
                {node.label}，掌握度{MASTERY_LABELS[node.level]}
              </span>
            </>
          );
          const interactive = Boolean(onSelect) && !node.locked;
          const paintStyle: CSSProperties = {
            width: size,
            height: size,
            background: `var(--mastery-${node.level})`,
          };
          const paintClass = cn(
            "relative flex items-center justify-center rounded-control border border-border",
            node.locked && "opacity-60",
          );
          return (
            <li key={node.id} className="flex flex-col items-center gap-hair">
              {interactive ? (
                <button
                  type="button"
                  style={paintStyle}
                  className={cn(paintClass, "cursor-pointer")}
                  data-testid={`kmap-node-${node.id}`}
                  aria-label={`${node.label}，${MASTERY_LABELS[node.level]}，打开讲解`}
                  onClick={() => onSelect?.(node.id)}
                >
                  {node.hasExplainer ? (
                    <span aria-hidden className="absolute -right-xs -top-xs text-app-xs">
                      🎬
                    </span>
                  ) : null}
                  {body}
                </button>
              ) : (
                <span style={paintStyle} className={paintClass}>
                  {node.href ? <a href={node.href}>{body}</a> : body}
                </span>
              )}
              <MasteryBar
                value={progress}
                tone={`var(--mastery-${node.level})`}
                label={`${node.label} 掌握度`}
                className="w-[var(--kmap-node)]"
              />
              {speakable ? (
                <AudioButton text={`${node.label}，${MASTERY_LABELS[node.level]}`} />
              ) : null}
            </li>
          );
        })}
      </ul>
      {title ? null : caption}
    </section>
  );
}

export interface KnowledgeMapItemProps extends HTMLAttributes<HTMLLIElement> {
  node: KnowledgeNode;
  /** 朗读整行文本（kids 主题默认开启） */
  speakable?: boolean;
}

export function KnowledgeMapItem({ className, node, speakable, ...props }: KnowledgeMapItemProps) {
  return (
    <li className={cn("flex items-center gap-xs", className)} {...props}>
      <span className="text-app-sm">{node.label}</span>
      <MasteryBar value={node.progress ?? defaultProgress(node.level)} label={node.label} />
      {speakable ? <AudioButton text={`${node.label}，${MASTERY_LABELS[node.level]}`} /> : null}
    </li>
  );
}
