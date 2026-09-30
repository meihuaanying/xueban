"use client";

import type { HTMLAttributes } from "react";

import { cn } from "../cn";

export interface MasteryBarProps extends Omit<HTMLAttributes<HTMLDivElement>, "children"> {
  /** 掌握度 0~1 */
  value: number;
  /** 填充色，默认按档位自动取 --mastery-N */
  tone?: string;
  label?: string;
  /** 显示百分比文字 */
  showValue?: boolean;
}

const TONES: readonly string[] = [
  "var(--mastery-1)",
  "var(--mastery-1)",
  "var(--mastery-2)",
  "var(--mastery-3)",
  "var(--mastery-4)",
  "var(--mastery-5)",
];

/** 按 0~1 映射到 1~5 档色 */
export function toneForValue(value: number): string {
  const ratio = Math.min(Math.max(value, 0), 1);
  const level = Math.min(5, Math.max(1, Math.ceil(ratio * 5) || 1));
  return TONES[level] ?? "var(--mastery-1)";
}

/**
 * 掌握度条（核心视觉语言）。
 * 高度走 --mastery-bar-height（focus 8px / kids 14px），
 * 颜色走 --mastery-N 档位色 ⇒ 双主题自动换肤。
 */
export function MasteryBar({
  className,
  value,
  tone,
  label = "掌握度",
  showValue,
  ...props
}: MasteryBarProps) {
  const ratio = Math.min(Math.max(value, 0), 1);
  const percent = Math.round(ratio * 100);
  return (
    <div className={cn("flex items-center gap-hair", className)} {...props}>
      <div
        role="progressbar"
        aria-label={label}
        aria-valuenow={percent}
        aria-valuemin={0}
        aria-valuemax={100}
        className="h-[var(--mastery-bar-height)] w-full min-w-[var(--kmap-node)] overflow-hidden rounded-pill bg-muted"
      >
        <div
          className="h-full rounded-pill transition-all duration-base ease-soft"
          style={{ width: `${percent}%`, background: tone ?? toneForValue(ratio) }}
        />
      </div>
      {showValue ? (
        <span className="shrink-0 text-app-xs tabular-nums text-muted-foreground">{percent}%</span>
      ) : null}
    </div>
  );
}
