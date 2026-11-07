"use client";

/** 交互讲解卡（§5.3 触发 → §5.4 安全与降级）：idle / pending / ready / failed 四态。
 *
 * 降级的图文分步视图拆在 `script-fallback.tsx`——它是交互页彻底跑不起来时的最后一道
 * 防线，必须独立于卡片的状态机单独维护。
 */

import { AudioButton, Badge, Button, Card, CardContent, CardHeader, CardTitle, ExplainerFrame } from "@xueban/ui";

import type { ExplainerContent } from "@/lib/api";
import { ScriptFallback, narrationOf } from "./script-fallback";
/** 讲解卡：空闲/生成中/失败重试/已就绪四种状态，缺一不可。 */
export function ExplainerCard({
  status,
  content,
  error,
  notice,
  speakable,
  busy,
  onOpen,
  onOpenVideo,
  onRetry,
  onClose,
  onFeedback,
}: {
  status: "idle" | "pending" | "ready" | "failed";
  content: ExplainerContent | null;
  error: string | null;
  /** 视频未预生成时回落互动讲解的提示（§5.3）。 */
  notice?: string | null;
  speakable: boolean;
  busy: boolean;
  onOpen: () => void;
  /** 传了才显示「看视频讲解」；视频是离线预生成，未命中会自动回落互动讲解。 */
  onOpenVideo?: () => void;
  onRetry: () => void;
  onClose: () => void;
  onFeedback: (understood: boolean) => void;
}) {
  if (status === "idle") {
    return (
      <Card data-testid="explainer-idle">
        <CardHeader>
          <CardTitle>看不懂？看我讲一遍</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap items-center gap-sm">
          <Button type="button" data-testid="explainer-open" disabled={busy} onClick={onOpen}>
            {busy ? "准备中…" : "看讲解"}
          </Button>
          {onOpenVideo ? (
            <Button
              type="button"
              variant="outline"
              data-testid="explainer-open-video"
              disabled={busy}
              onClick={onOpenVideo}
            >
              看视频讲解
            </Button>
          ) : null}
        </CardContent>
      </Card>
    );
  }

  if (status === "pending") {
    return (
      <Card data-testid="explainer-pending">
        <CardContent className="flex flex-col items-start gap-sm py-lg">
          <p className="text-app-sm text-muted-foreground">正在给你准备讲解，马上就好…</p>
          {/* 互动页还在生成时也允许直接看预生成视频（§5.3），不必等 LLM。 */}
          {onOpenVideo ? (
            <Button
              type="button"
              variant="outline"
              data-testid="explainer-switch-video"
              onClick={onOpenVideo}
            >
              直接看视频讲解
            </Button>
          ) : null}
        </CardContent>
      </Card>
    );
  }

  if (status === "failed" || !content) {
    return (
      <Card data-testid="explainer-failed">
        <CardHeader>
          <CardTitle>讲解没能加载出来</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col items-start gap-sm">
          <p className="text-app-sm text-destructive">{error ?? "讲解没能生成出来。"}</p>
          <div className="flex gap-sm">
            <Button type="button" data-testid="explainer-retry" onClick={onRetry}>
              再试一次
            </Button>
            <Button type="button" variant="outline" onClick={onClose}>
              先去练题
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  const narration = narrationOf(content);

  return (
    <Card data-testid="explainer-ready">
      <CardHeader>
        <CardTitle className="flex items-center gap-sm">
          讲解 · {content.title}
          {content.mode === "video" ? <Badge variant="info">视频</Badge> : null}
          {content.degraded ? <Badge variant="warning">图文版</Badge> : null}
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-sm">
        {notice ? (
          <p className="text-app-sm text-muted-foreground" data-testid="explainer-notice">
            {notice}
          </p>
        ) : null}
        {content.mode === "video" && content.video_url ? (
          <ExplainerFrame
            title={content.title}
            videoUrl={content.video_url}
            timeoutMs={content.render_timeout_seconds * 1000}
            fallback={<ScriptFallback content={content} speakable={speakable} />}
            onFallback={() => onFeedback(false)}
            onFeedback={onFeedback}
          />
        ) : content.mode === "video" ? (
          // 视频地址缺失（预签名失败/过期）时直接给图文分步，避免停在「生成中」。
          <ScriptFallback content={content} speakable={speakable} />
        ) : content.degraded ? (
          <ScriptFallback content={content} speakable={speakable} />
        ) : (
          <ExplainerFrame
            title={content.title}
            html={content.html}
            timeoutMs={content.render_timeout_seconds * 1000}
            fallback={<ScriptFallback content={content} speakable={speakable} />}
            onFallback={() => onFeedback(false)}
            onFeedback={onFeedback}
          />
        )}
        <div className="flex flex-wrap items-center gap-sm">
          <AudioButton text={`${content.title}。${narration}`}>听讲解</AudioButton>
          {/* 互动页已就绪时也允许切到预生成视频（§5.3）；视频未生成会自动回落。 */}
          {onOpenVideo && content.mode !== "video" ? (
            <Button
              type="button"
              variant="outline"
              data-testid="explainer-switch-video"
              onClick={onOpenVideo}
            >
              看视频讲解
            </Button>
          ) : null}
          {/* 看懂了就该收起，别一直挡着下一题 */}
          <Button type="button" variant="outline" data-testid="explainer-close" onClick={onClose}>
            看完了，去做题
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
