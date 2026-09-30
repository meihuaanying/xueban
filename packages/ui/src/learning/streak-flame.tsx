"use client";

import type { HTMLAttributes } from "react";

import { cn } from "../cn";

export interface StreakFlameProps extends HTMLAttributes<HTMLDivElement> {
  /** 连续天数 */
  days: number;
  /** 目标天数（默认 7） */
  goal?: number;
  /** 今天是否已打卡 */
  doneToday?: boolean;
}

function toneOf(days: number, goal: number, doneToday: boolean): string {
  if (days >= goal) return "var(--primary)";
  if (doneToday) return "var(--mastery-3)";
  return "var(--muted-foreground)";
}

/**
 * 连续打卡火苗（Duolingo 式 streak，但仅在 kids 主题呈现游戏化元素）。
 * 达到目标天数用主色，未达标用掌握度三段绿，today 未打卡用中性灰。
 */
export function StreakFlame({
  className,
  days,
  goal = 7,
  doneToday = false,
  ...props
}: StreakFlameProps) {
  const reached = days >= goal;
  return (
    <div
      role="status"
      aria-label={`连续学习 ${days} 天，目标 ${goal} 天${doneToday ? "，今天已完成" : "，今天还没完成"}`}
      className={cn(
        "inline-flex items-center gap-hair rounded-pill border border-border-strong bg-card px-sm py-hair",
        className,
      )}
      {...props}
    >
      <span aria-hidden="true" className="text-app-md leading-none" style={{ color: toneOf(days, goal, doneToday) }}>
        🔥
      </span>
      <span className="text-app-sm font-semibold" style={{ color: toneOf(days, goal, doneToday) }}>
        {days} 天
      </span>
      {reached ? <span className="text-app-xs text-muted-foreground">目标达成</span> : null}
    </div>
  );
}
