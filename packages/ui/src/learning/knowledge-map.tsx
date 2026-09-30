"use client";

import type { HTMLAttributes, ReactNode } from "react";

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
  level: MasteryLevel;
  /** 掌握度 0~1；省略时用 level 换算的默认进度 */
  progress?: number;
  subject?: string;
  href?: string;
  locked?: boolean;
}

export interface KnowledgeMapProps extends HTMLAttributes<HTMLDivElement> {
  nodes: KnowledgeNode[];
  /** 学科标题，如「数学」 */
  title?: string;
  /** 单个节点尺寸覆盖（默认 --kmap-node） */
  nodeSize?: string;
  caption?: ReactNode;
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
          const body = (
            <>
              <span
                aria-hidden="true"
                className="block text-app-lg leading-none font-bold"
                style={{ color: node.level >= 4 ? "var(--primary-foreground)" : "var(--card)" }}
              >
                {node.label}
              </span>
              <span className="sr-only">
                {node.label}，掌握度{MASTERY_LABELS[node.level]}
              </span>
            </>
          );
          return (
            <li key={node.id} className="flex flex-col items-center gap-hair">
              <span
                style={{
                  width: size,
                  height: size,
                  background: `var(--mastery-${node.level})`,
                }}
                className={cn(
                  "flex items-center justify-center rounded-control border border-border",
                  node.locked && "opacity-60",
                )}
              >
                {node.href ? <a href={node.href}>{body}</a> : body}
              </span>
              <MasteryBar
                value={progress}
                tone={`var(--mastery-${node.level})`}
                label={`${node.label} 掌握度`}
                className="w-[var(--kmap-node)]"
              />
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
