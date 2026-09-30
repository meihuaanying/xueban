/**
 * 旅程阶段通用页壳：标题、说明、动作区。
 * 让每个阶段页保持 ≤150 行，复杂区块下沉到 components/。
 */
import type { ReactNode } from "react";

import { AudioButton } from "@xueban/ui";
import { cn } from "@xueban/ui";

import { useJourney } from "../journey/journey-context";
import { stageDefinition, type JourneyStage } from "../journey/stages";

export interface StageShellProps {
  stage: JourneyStage;
  /** 覆盖默认标题 */
  title?: string;
  /** 标题旁的一句话说明 */
  description?: string;
  /** 该页正文是否需要 TTS 朗读（一年级默认全站支持） */
  speakable?: boolean;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}

export function StageShell({
  stage,
  title,
  description,
  speakable = false,
  actions,
  children,
  className,
}: StageShellProps) {
  const def = stageDefinition(stage);
  const { theme } = useJourney();
  const heading = title ?? def.label;
  const intro = description ?? def.hint;

  return (
    <section
      aria-label={heading}
      className={cn("flex min-w-0 flex-1 flex-col gap-md p-lg text-foreground", className)}
    >
      <header className="flex flex-wrap items-start justify-between gap-sm">
        <div className="flex min-w-0 flex-col gap-hair">
          <p className="text-app-xs text-muted-foreground">
            第 {def.order} 站 · {def.label}
          </p>
          <h1 className="text-app-2xl font-semibold">{heading}</h1>
          <p className="text-app text-muted-foreground">{intro}</p>
        </div>
        <div className="flex shrink-0 items-center gap-xs">
          {speakable ? <AudioButton text={`${heading}。${intro}`} /> : null}
          {actions}
          {theme === "kids" ? (
            <span className="rounded-pill bg-primary-soft px-sm py-xs text-app-xs text-accent-foreground">
              儿童模式
            </span>
          ) : null}
        </div>
      </header>
      {children}
    </section>
  );
}
