"use client";

import { useEffect, useState, type HTMLAttributes, type ReactNode } from "react";

import { cn } from "../cn";

export interface ExplainerFrameProps extends Omit<HTMLAttributes<HTMLDivElement>, "onError"> {
  /**
   * 已消毒的单文件 HTML（内联 CSS/JS，禁止外部请求）。
   * 必须来自后端 §5.2 管线并经 DOMPurify + CSP 校验。
   */
  html?: string;
  /** 视频讲解 URL（P3；与 html 二选一） */
  videoUrl?: string;
  title: string;
  /** 渲染超时兜底文案（§5.4：>60s 必须降级为图文分步讲解，禁止白屏） */
  fallback?: ReactNode;
  /** 注入沙箱 CSP；由宿主按 §5.4 提供，默认沿用页面 CSP */
  sandbox?: string;
  timeoutMs?: number;
  /** 降级触发回调，便于埋点与日志 */
  onFallback?: (reason: "timeout" | "empty" | "error") => void;
  onFeedback?: (understood: boolean) => void;
}

const DEFAULT_SANDBOX = "allow-scripts";
const DEFAULT_TIMEOUT_MS = 60_000;

/**
 * Explainer 沙箱内嵌框（§5.4 安全红线）。
 * - AI 生成的 HTML 只能在此渲染，禁止网络出站由宿主 CSP 负责（`default-src 'none'`）。
 * - 视频/HTML 缺失、加载失败或超过 timeoutMs，一律降级为「图文分步讲解」，禁止白屏。
 */
export function ExplainerFrame({
  className,
  html,
  videoUrl,
  title,
  fallback,
  sandbox = DEFAULT_SANDBOX,
  timeoutMs = DEFAULT_TIMEOUT_MS,
  onFallback,
  onFeedback,
  ...props
}: ExplainerFrameProps) {
  const [degraded, setDegraded] = useState<"timeout" | "empty" | "error" | null>(null);

  useEffect(() => {
    if (!html || degraded) return;
    const timer = window.setTimeout(() => {
      setDegraded("timeout");
      onFallback?.("timeout");
    }, timeoutMs);
    return () => window.clearTimeout(timer);
  }, [degraded, html, onFallback, timeoutMs]);

  const degradedView = fallback ?? (
    <div className="rounded-control border border-border-strong bg-surface-sunken p-sm text-app-sm text-muted-foreground">
      讲解暂时无法播放，已切换为图文分步讲解。
    </div>
  );

  return (
    <figure
      aria-label={title}
      className={cn(
        "overflow-hidden rounded-card border border-border bg-card p-sm text-card-foreground shadow-card",
        className,
      )}
      {...props}
    >
      <figcaption className="mb-xs flex flex-wrap items-center justify-between gap-xs">
        <span className="text-app-sm font-semibold">{title}</span>
        {degraded ? null : (
          <span className="flex items-center gap-hair">
            <button
              type="button"
              onClick={() => onFeedback?.(true)}
              className="min-h-[var(--tap-min)] rounded-control border border-border-strong px-sm text-app-sm hover:bg-accent"
            >
              看懂了
            </button>
            <button
              type="button"
              onClick={() => onFeedback?.(false)}
              className="min-h-[var(--tap-min)] rounded-control border border-border-strong px-sm text-app-sm hover:bg-accent"
            >
              还是不懂
            </button>
          </span>
        )}
      </figcaption>

      {degraded ? (
        degradedView
      ) : videoUrl ? (
        // 视频走 <video>，不注入远程脚本
        <video className="w-full rounded-control" controls preload="metadata" src={videoUrl} />
      ) : html ? (
        <iframe
          title={title}
          // 关键安全约束：sandbox 不给 allow-same-origin/allow-popups，
          // 任何网络出站由宿主 CSP（default-src 'none'）阻断
          sandbox={sandbox}
          referrerPolicy="no-referrer"
          className="h-[420px] w-full rounded-control border border-border"
          srcDoc={html}
          onError={() => {
            setDegraded("error");
            onFallback?.("error");
          }}
        />
      ) : (
        <div className="rounded-control border border-border-strong bg-surface-sunken p-sm text-app-sm text-muted-foreground">
          讲解内容生成中…
        </div>
      )}
    </figure>
  );
}
