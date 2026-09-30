"use client";

/** 旅程页面通用状态块：加载 / 空态 / 错误 + 步骤条，避免六个页面各写一套。 */
import { Button, Card, CardContent, CardHeader, CardTitle, Spinner } from "@xueban/ui";

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

  return (
    <div className="flex flex-wrap items-center justify-between gap-sm border-t border-border pt-sm">
      <p className="text-app-xs text-muted-foreground">
        当前：第 {definition.order} 站 · {definition.label}
      </p>
      <div className="flex items-center gap-sm">
        <span className="text-app-xs text-muted-foreground" data-testid="journey-next">
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
