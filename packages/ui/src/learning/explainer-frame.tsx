"use client";

import {
  useCallback,
  useEffect,
  useState,
  type HTMLAttributes,
  type ReactNode,
} from "react";

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

export interface UseExplainerWatchdogOptions {
  /** 讲解已就绪：html 或 videoUrl 至少有一个。 */
  armed: boolean;
  /** 已渲染成功（iframe onLoad / video loadedmetadata）。就绪后解除武装。 */
  ready: boolean;
  /** 已经降级过，降级不可逆。 */
  degraded: boolean;
  timeoutMs: number;
  onTimeout: () => void;
}

/**
 * §5.4 的渲染超时看门狗：armed 且未就绪超过 timeoutMs 就降级。
 *
 * 单独抽出来是因为这段计时逻辑没法在 jsdom 里靠 iframe 事件测——jsdom 会自动
 * 派发 load，导致 onLoad 一挂上就解除武装，超时路径永远走不到。做成纯计时逻辑
 * 后可以直接用假定时器断言，也方便别的宿主（比如 React Native WebView）复用。
 */
export function useExplainerWatchdog({
  armed,
  ready,
  degraded,
  timeoutMs,
  onTimeout,
}: UseExplainerWatchdogOptions): void {
  useEffect(() => {
    if (!armed || ready || degraded) return;
    const timer = window.setTimeout(onTimeout, timeoutMs);
    return () => window.clearTimeout(timer);
  }, [armed, degraded, onTimeout, ready, timeoutMs]);
}

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
  // 已渲染成功。iframe 的 onLoad 是唯一可靠的"渲染完成"信号——onError 对 iframe
  // 基本不触发，而只靠超时会在讲解正常跑满 60s 后误判为超时并把好内容换成降级页。
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    setLoaded(false);
  }, [html, videoUrl]);

  // 已就绪就不再计时：§5.4 的 60s 是"渲染超时"上限，不是"展示时长"上限。
  const handleTimeout = useCallback(() => {
    setDegraded("timeout");
    onFallback?.("timeout");
  }, [onFallback]);

  useExplainerWatchdog({
    armed: Boolean(html || videoUrl),
    ready: loaded,
    degraded: degraded !== null,
    timeoutMs,
    onTimeout: handleTimeout,
  });

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
        <video
          className="w-full rounded-control"
          controls
          preload="metadata"
          src={videoUrl}
          onLoadedMetadata={() => setLoaded(true)}
        />
      ) : html ? (
        <iframe
          title={title}
          // 关键安全约束：sandbox 不给 allow-same-origin/allow-popups，
          // 网络出站由后端注入的 CSP（default-src 'none'）阻断
          sandbox={sandbox}
          referrerPolicy="no-referrer"
          className="h-[420px] w-full rounded-control border border-border"
          srcDoc={html}
          onLoad={() => setLoaded(true)}
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
