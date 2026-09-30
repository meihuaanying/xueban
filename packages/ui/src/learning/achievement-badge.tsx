"use client";

import type { HTMLAttributes } from "react";

import { cn } from "../cn";

export interface Achievement {
  id: string;
  label: string;
  /** 已解锁 */
  unlocked?: boolean;
  /** 展示图标；缺省按 id 映射 */
  icon?: string;
  hint?: string;
}

export interface AchievementBadgeProps extends HTMLAttributes<HTMLSpanElement> {
  achievement: Achievement;
}

const ICONS: Record<string, string> = {
  streak: "🔥",
  mastery: "🎯",
  first_explainer: "🎬",
  no_hint: "🧠",
  review: "🔁",
  perfect: "⭐",
};

export function AchievementBadge({ className, achievement, ...props }: AchievementBadgeProps) {
  const unlocked = achievement.unlocked ?? false;
  const icon = achievement.icon ?? ICONS[achievement.id] ?? "🏅";
  return (
    <span
      role="img"
      aria-label={`${achievement.label}${unlocked ? "（已解锁）" : "（未解锁）"}`}
      title={achievement.hint}
      className={cn(
        "inline-flex min-h-[var(--tap-min)] items-center gap-hair rounded-control border px-sm py-xs text-app-sm",
        unlocked
          ? "border-primary bg-primary-soft text-accent-foreground"
          : "border-border bg-surface-sunken text-muted-foreground opacity-70",
        className,
      )}
      {...props}
    >
      <span aria-hidden="true">{icon}</span>
      <span className="font-medium">{achievement.label}</span>
    </span>
  );
}
