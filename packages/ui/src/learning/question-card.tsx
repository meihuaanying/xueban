"use client";

import { useEffect, useId, useState, type HTMLAttributes, type ReactNode } from "react";

import { cn } from "../cn";
import { AudioButton } from "./audio-button";
import { MathFormula } from "../formula";

export type QuestionKind = "choice" | "fill" | "judge" | "link" | "oral" | "dictation";

export interface QuestionOption {
  key: string;
  label: ReactNode;
}

export interface QuestionCardProps extends Omit<HTMLAttributes<HTMLDivElement>, "onSelect"> {
  /** 题干（支持 KaTeX 时用 formula 字段） */
  stem: string;
  /** KaTeX 公式题干（一二年级通常不用） */
  formula?: string;
  meta?: string;
  kind?: QuestionKind;
  options?: QuestionOption[];
  /** 拼音标注（语文/英语启蒙） */
  pinyin?: string;
  /** 已选中的选项 */
  value?: string;
  onSelect?: (key: string) => void;
  /** 提交按钮（受控由父组件决定何时可提交） */
  footer?: ReactNode;
  /** 朗读题干（一年级默认开启） */
  speakable?: boolean;
  /** 田字格书写区（语文识字/写字） */
  tian?: boolean;
  disabled?: boolean;
}

/**
 * 题卡。
 * 选项热区走 --tap-min（focus 32px / kids 48px），kids 下天然满足 7 岁可点性；
 * 一年级默认开启朗读；支持选择题/填空/判断/连线/口算/听写六种题型容器。
 */
export function QuestionCard({
  className,
  stem,
  formula,
  meta,
  kind = "choice",
  options,
  pinyin,
  value,
  onSelect,
  footer,
  speakable,
  tian,
  disabled,
  ...props
}: QuestionCardProps) {
  const fillId = useId();
  // 填空题草稿自持：选项题的 onSelect 语义是「点选即提交」，
  // 若直接绑到输入框的 onChange 会每次按键都提交一次，因此这里只存草稿，
  // 由「提交答案」按钮显式触发 onSelect。
  const [draft, setDraft] = useState("");
  useEffect(() => setDraft(""), [stem]);
  return (
    <section
      aria-label={stem}
      data-kind={kind}
      className={cn(
        "rounded-card border border-border bg-card p-sm text-card-foreground shadow-card",
        className,
      )}
      {...props}
    >
      <header className="mb-xs flex flex-wrap items-center justify-between gap-xs">
        {meta ? <span className="text-app-xs text-muted-foreground">{meta}</span> : <span />}
        {speakable ? <AudioButton text={stem} /> : null}
      </header>

      {pinyin ? (
        <p className="text-app-xs tracking-wide text-info" aria-label={`拼音 ${pinyin}`}>
          {pinyin}
        </p>
      ) : null}

      <p className="text-app-lg font-semibold">{stem}</p>
      {formula ? (
        <p className="mt-xs">
          <MathFormula formula={formula} displayMode />
        </p>
      ) : null}

      {options?.length ? (
        <ul
          className={cn(
            "mt-sm grid gap-xs",
            options.length <= 2 ? "grid-cols-1" : "grid-cols-1 sm:grid-cols-2",
          )}
          role="list"
        >
          {options.map((option) => {
            const selected = value === option.key;
            return (
              <li key={option.key}>
                <button
                  type="button"
                  disabled={disabled}
                  aria-pressed={selected}
                  data-testid={"option-" + option.key}
                  onClick={() => onSelect?.(option.key)}
                  className={cn(
                    "flex min-h-[var(--tap-min)] w-full items-center justify-center gap-xs",
                    "rounded-control border px-sm text-app transition-colors",
                    selected
                      ? "border-primary bg-primary-soft text-accent-foreground"
                      : "border-border-strong bg-card text-foreground hover:bg-accent",
                    disabled && "cursor-not-allowed opacity-60",
                  )}
                >
                  <span className="font-semibold">{option.key}.</span>
                  <span>{option.label}</span>
                </button>
              </li>
            );
          })}
        </ul>
      ) : null}

      {options?.length ? null : (
        <div className="mt-sm flex flex-col gap-xs">
          <label className="text-app-sm text-muted-foreground" htmlFor={fillId}>
            你的答案
          </label>
          <input
            id={fillId}
            data-testid="fill-input"
            type="text"
            value={draft}
            disabled={disabled}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="请输入答案"
            className={cn(
              "min-h-[var(--input-height)] w-full rounded-control",
              "border border-border-strong bg-card px-sm text-app text-foreground",
              "placeholder:text-muted-foreground",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              disabled && "cursor-not-allowed opacity-60",
            )}
          />
          <button
            type="button"
            data-testid="fill-submit"
            disabled={disabled || draft.trim().length === 0}
            onClick={() => onSelect?.(draft.trim())}
            className={cn(
              "min-h-[var(--tap-min)] w-full rounded-control border border-primary",
              "bg-primary px-sm text-app-md text-primary-foreground",
              "disabled:cursor-not-allowed disabled:opacity-60",
            )}
          >
            提交答案
          </button>
        </div>
      )}

      {tian ? (
        <div
          aria-label="田字格"
          className="mt-sm grid grid-cols-4 gap-hair"
          style={{ color: "var(--border-strong)" }}
        >
          {Array.from({ length: 4 }, (_, index) => (
            <div
              key={index}
              className="aspect-square w-full rounded-sm border border-current"
              style={{ backgroundImage: "linear-gradient(var(--border), var(--border))" }}
            />
          ))}
        </div>
      ) : null}

      {footer ? <div className="mt-sm">{footer}</div> : null}
    </section>
  );
}
