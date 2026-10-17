"use client";

/** 旅程页面通用状态块：加载 / 空态 / 错误 + 步骤条，避免六个页面各写一套。 */
import { AudioButton, Button, Card, CardContent, CardHeader, CardTitle, Spinner } from "@xueban/ui";

import { useJourney } from "../journey/journey-context";
import { nextStage, stageDefinition } from "../journey/stages";

interface AsyncFeedbackProps {
  loading?: boolean;
  error?: string | null;
  empty?: boolean;
  emptyTitle?: string;
  emptyHint?: string;
  onRetry?: () => void;
  children: React.ReactNode;
}

export function AsyncFeedback({
  loading = false,
  error = null,
  empty = false,
  emptyTitle = "暂无内容",
  emptyHint = "完成前面的步骤后这里会自动出现。",
  onRetry,
  children,
}: AsyncFeedbackProps) {
  if (loading) {
    return (
      <div className="flex items-center gap-sm text-app-sm text-muted-foreground" role="status">
        <Spinner size="sm" />
        加载中…
      </div>
    );
  }
  if (error) {
    return (
      <Card className="border-destructive">
        <CardHeader>
          <CardTitle className="text-destructive">加载失败</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col items-start gap-sm">
          <p className="text-app-sm text-foreground">{error}</p>
          {onRetry ? (
            <Button type="button" variant="outline" onClick={onRetry}>
              重试
            </Button>
          ) : null}
        </CardContent>
      </Card>
    );
  }
  if (empty) {
    return (
      <Card className="border-dashed border-border-strong">
        <CardHeader>
          <CardTitle>{emptyTitle}</CardTitle>
        </CardHeader>
        <CardContent className="text-app-sm text-muted-foreground">{emptyHint}</CardContent>
      </Card>
    );
  }
  return <>{children}</>;
}

/** 旅程步骤条：统一「当前位置 + 下一站」引导，禁止孤立页面跳转。 */
export function JourneyStepper() {
  const { stage, advance, state, theme } = useJourney();
  const target = nextStage(state);
  const definition = stageDefinition(stage);
  const nextDefinition = stageDefinition(target);

  // kids 下提示文字不能用 text-app-xs：kids 档 xs 只有 15.4px，7 岁孩子读「下一站」
  // 这种导航信息本就吃力，小字更读不清。基准 18px 起步（§4.1）。
  const hintClass = theme === "kids" ? "text-app" : "text-app-xs";

  // §4.1「所有文本支持 TTS」+ §7「无文字依赖导航」：一年级孩子很可能还不识字，
  // 步骤条却是每一站都要看的导航信息。
  //
  // 只在 kids 档挂朗读，且**只挂一个喇叭**：这是六个阶段页共用组件，给两处提示
  // 各挂一个会在每页多出两个图标——对专注模式是噪音，对 7 岁孩子则是
  // 「到底该点哪一个」的新困惑。把两处提示合成一句读，一个入口最清楚。
  const speakable = theme === "kids";
  const spoken = `当前在第 ${definition.order} 站，${definition.label}。下一站，${nextDefinition.label}。`;

  return (
    <div className="flex flex-wrap items-center justify-between gap-sm border-t border-border pt-sm">
      <p className={`${hintClass} text-muted-foreground`}>
        当前：第 {definition.order} 站 · {definition.label}
      </p>
      <div className="flex items-center gap-sm">
        {speakable ? <AudioButton data-testid="journey-speak" text={spoken} /> : null}
        <span className={`${hintClass} text-muted-foreground`} data-testid="journey-next">
          下一站：{nextDefinition.label}
        </span>
        <Button
          type="button"
          data-testid="journey-advance"
          onClick={advance}
          className={theme === "kids" ? "text-app-md font-bold" : undefined}
        >
          前往{nextDefinition.label}
        </Button>
      </div>
    </div>
  );
}
