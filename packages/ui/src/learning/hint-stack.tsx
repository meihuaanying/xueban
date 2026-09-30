"use client";

import { type HTMLAttributes, type ReactNode } from "react";

import { cn } from "../cn";
import { AudioButton } from "./audio-button";

/** 三层提示层级（守护型红线：思路 → 关键步骤 → 全解，永不直接给答案） */
export type HintLevel = 1 | 2 | 3;

export const HINT_TITLES: Record<HintLevel, string> = {
  1: "一层·轻推",
  2: "二层·举一反三",
  3: "三层·微支架",
};

export interface HintItem {
  level: HintLevel;
  text: ReactNode;
}

export interface HintStackProps extends HTMLAttributes<HTMLDivElement> {
  hints: HintItem[];
  /** 已解锁到第几层（守护型红线：默认仅 1 层） */
  revealed?: number;
  /** 解锁下一层的回调；未提供时按钮只做展示 */
  onReveal?: (level: HintLevel) => void;
  /** 三层用尽后的兜底：转动画讲解（守护型红线的唯一出口） */
  fallback?: ReactNode;
  /** 朗读整组提示 */
  speakable?: boolean;
}

/**
 * 三层提示栈。
 * 层级用 --hint-1/2/3 颜色编码（蓝 → 琥珀 → 绿），不依赖文案辨识；
 * 三层之后必须给出「看动画讲解」出口，不允许出现完整答案。
 */
export function HintStack({
  className,
  hints,
  revealed,
  onReveal,
  fallback,
  speakable,
  ...props
}: HintStackProps) {
  // 守护型红线：默认只给第 1 层，必须由学生主动索取后续提示
  const limit = revealed ?? 1;
  const next = hints.find((hint) => hint.level > limit);

  return (
    <section
      aria-label="三层提示"
      className={cn(
        "rounded-card border border-border bg-surface-sunken p-sm",
        className,
      )}
      {...props}
    >
      <ol className="flex flex-col gap-xs" role="list">
        {hints
          .filter((hint) => hint.level <= limit)
          .map((hint) => (
            <li
              key={hint.level}
              className="rounded-control border-l-4 bg-card px-sm py-xs text-app"
              style={{ borderLeftColor: `var(--hint-${hint.level})` }}
            >
              <div className="flex items-start justify-between gap-xs">
                <span
                  className="text-app-xs font-semibold"
                  style={{ color: `var(--hint-${hint.level})` }}
                >
                  {HINT_TITLES[hint.level]}
                </span>
                {speakable ? (
                  <AudioButton text={typeof hint.text === "string" ? hint.text : undefined} />
                ) : null}
              </div>
              <div className="text-app-sm text-foreground">{hint.text}</div>
            </li>
          ))}
      </ol>

      {next ? (
        <button
          type="button"
          onClick={() => onReveal?.(next.level)}
          className="mt-sm min-h-[var(--tap-min)] w-full rounded-control border border-border-strong bg-card text-app font-medium text-foreground transition-colors hover:bg-accent"
        >
          {onReveal ? `给我第 ${next.level} 层提示` : `第 ${next.level} 层提示（未解锁）`}
        </button>
      ) : null}

      {!next ? (
        <p className="mt-sm text-app-xs text-muted-foreground">
          三层提示已用完，仍不提供完整答案。
        </p>
      ) : null}
      {!next && fallback ? <div className="mt-sm">{fallback}</div> : null}
    </section>
  );
}
