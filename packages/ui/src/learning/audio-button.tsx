"use client";

import { useCallback, useState } from "react";

import { cn } from "../cn";

export interface AudioButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  /** 要朗读的文本；不传则取 children 文本 */
  text?: string;
  /** 朗读语言，默认中文 */
  lang?: string;
  /** 语速 0.5~2 */
  rate?: number;
}

/**
 * TTS 朗读按钮（一年级可用性硬要求：所有文本可朗读）。
 * 优先 Web Speech API；不支持时降级为无操作并标记 disabled，
 * 不抛错、不影响主流程（见 P1 门禁「无文字依赖导航」）。
 */
export function AudioButton({
  className,
  text,
  lang = "zh-CN",
  rate = 0.9,
  children,
  onClick,
  ...props
}: AudioButtonProps) {
  const supported =
    typeof window !== "undefined" &&
    typeof window.speechSynthesis !== "undefined" &&
    typeof window.SpeechSynthesisUtterance !== "undefined";
  const [speaking, setSpeaking] = useState(false);

  const speak = useCallback(() => {
    if (!supported) return;
    const content = text ?? (typeof children === "string" ? children : "");
    if (!content) return;
    const utter = new window.SpeechSynthesisUtterance(content);
    utter.lang = lang;
    utter.rate = rate;
    utter.onend = () => setSpeaking(false);
    utter.onerror = () => setSpeaking(false);
    setSpeaking(true);
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utter);
  }, [children, lang, rate, supported, text]);

  if (!supported) {
    return null;
  }

  return (
    <button
      type="button"
      aria-label="朗读"
      aria-pressed={speaking}
      onClick={(event) => {
        onClick?.(event);
        speak();
      }}
      className={cn(
        "inline-flex min-h-[var(--tap-min)] min-w-[var(--tap-min)] items-center justify-center gap-hair",
        "rounded-control border border-border-strong bg-surface-sunken px-sm",
        "text-app-sm text-secondary-foreground transition-colors hover:bg-accent",
        speaking && "border-primary text-accent-foreground",
        className,
      )}
      {...props}
    >
      <span aria-hidden="true">{speaking ? "🔊" : "🔈"}</span>
      {children ?? <span className="text-app-sm">朗读</span>}
    </button>
  );
}
