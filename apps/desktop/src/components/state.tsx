/** 三态展示组件：加载 / 错误 / 空态（M9 统一设计语言的桌面端落点）。 */

import type { ReactNode } from "react";
import { Alert, Button, Card, CardContent, Skeleton } from "@xueban/ui";

export function LoadingBlock({ rows = 3, label = "加载中" }: { rows?: number; label?: string }) {
  return (
    <Card aria-busy="true" aria-label={label}>
      <CardContent className="space-y-3 pt-6">
        {Array.from({ length: rows }).map((_, index) => (
          <Skeleton key={index} className="h-5 w-full" style={{ opacity: 1 - index * 0.2 }} />
        ))}
      </CardContent>
    </Card>
  );
}

export function ErrorBlock({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="space-y-3" data-testid="error-block">
      <Alert variant="danger" title="操作未完成">
        {message}
      </Alert>
      {onRetry ? (
        <Button variant="outline" onClick={onRetry}>
          重试
        </Button>
      ) : null}
    </div>
  );
}

export function EmptyBlock({ title, hint, action }: { title: string; hint: string; action?: ReactNode }) {
  return (
    <Card data-testid="empty-block">
      <CardContent className="space-y-3 pt-6 text-sm text-muted-foreground">
        <p className="text-base font-semibold text-foreground">{title}</p>
        <p>{hint}</p>
        {action}
      </CardContent>
    </Card>
  );
}

export function SectionTitle({ children, hint }: { children: ReactNode; hint?: string }) {
  return (
    <div>
      <h2 className="text-xl font-bold tracking-tight">{children}</h2>
      {hint ? <p className="mt-1 text-sm text-muted-foreground">{hint}</p> : null}
    </div>
  );
}
