"use client";

/** 交互讲解卡（§5.3 触发 → §5.4 安全与降级）。 */

import { AudioButton, Badge, Button, Card, CardContent, CardHeader, CardTitle, ExplainerFrame } from "@xueban/ui";

import type { ExplainerContent } from "@/lib/api";

/** 教学脚本的一幕（后端 prompts.py 的 EXPLAINER 脚本结构）。 */
interface ExplainerAct {
  name?: string;
  goal?: string;
  narration?: string;
}

function readActs(script: Record<string, unknown>): ExplainerAct[] {
  const acts = script.acts;
  return Array.isArray(acts) ? (acts as ExplainerAct[]) : [];
}

/**
 * 图文分步降级视图（§5.4「渲染超时或失败必须降级，禁止白屏」）。
 * 直接复用后端产出的教学脚本：即使交互页没跑起来，讲解词也还能读给孩子听。
 */
function ScriptFallback({
  content,
  speakable,
}: {
  content: ExplainerContent;
  speakable: boolean;
}) {
  const acts = readActs(content.script);
  if (acts.length === 0) {
    return (
      <p className="text-app-sm text-muted-foreground" data-testid="explainer-steps">
        这段讲解暂时放不出来，换个时间再看看吧。
      </p>
    );
  }
  return (
    <ol className="flex flex-col gap-sm" data-testid="explainer-steps">
      {acts.map((act, index) => (
        <li key={index} className="rounded-control border border-border-strong p-sm">
          <p className="text-app-xs font-semibold">
            第 {index + 1} 幕 · {act.name ?? "讲解"}
          </p>
          <p className="text-app-sm">{act.narration ?? act.goal ?? ""}</p>
          {speakable && act.narration ? <AudioButton text={act.narration} /> : null}
        </li>
      ))}
    </ol>
  );
}

/** 讲解卡：空闲/生成中/失败重试/已就绪四种状态，缺一不可。 */
export function ExplainerCard({
  status,
  content,
  error,
  speakable,
  busy,
  onOpen,
  onRetry,
  onClose,
  onFeedback,
}: {
  status: "idle" | "pending" | "ready" | "failed";
  content: ExplainerContent | null;
  error: string | null;
  speakable: boolean;
  busy: boolean;
  onOpen: () => void;
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
        <CardContent>
          <Button type="button" data-testid="explainer-open" disabled={busy} onClick={onOpen}>
            {busy ? "准备中…" : "看讲解"}
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (status === "pending") {
    return (
      <Card data-testid="explainer-pending">
        <CardContent className="py-lg text-center text-app-sm text-muted-foreground">
          正在给你准备讲解，马上就好…
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

  const narration = readActs(content.script)
    .map((act) => act.narration ?? "")
    .join("");

  return (
    <Card data-testid="explainer-ready">
      <CardHeader>
        <CardTitle className="flex items-center gap-sm">
          讲解 · {content.title}
          {content.degraded ? <Badge variant="warning">图文版</Badge> : null}
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-sm">
        {/* 降级产物**不能**靠「html 传空 + fallback」来显示：那样看门狗不武装，
            ExplainerFrame 会一直停在「生成中…」。所以这里直接分流到图文分步视图。 */}
        {content.degraded ? (
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
          {/* 看懂了就该收起，别一直挡着下一题 */}
          <Button type="button" variant="outline" data-testid="explainer-close" onClick={onClose}>
            看完了，去做题
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}