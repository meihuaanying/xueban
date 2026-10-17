/**
 * 防沉迷闸门（T7.2 / F-40）：服务端判定锁屏，客户端每 60s 复核，无法本地绕过。
 *
 * 状态形状、锁定原因文案、锁屏页文案与轮询周期都来自 `@xueban/core` 的 `guardian`
 * （三端共享，§8 约束 7）；本文件只负责桌面端的画法。
 */

import {
  GUARDIAN_COPY,
  GUARDIAN_POLL_MS,
  guardianAvailableText,
  guardianReasonLabel,
  guardianUsageText,
  type GuardianStatus,
} from "@xueban/core";
import { Alert, Badge, Button, Card, CardContent, CardHeader, CardTitle } from "@xueban/ui";
import { useCallback, useEffect, useState, type ReactNode } from "react";

import { api } from "@/lib/api";

export function GuardianGate({ children }: { children: ReactNode }) {
  const [state, setState] = useState<GuardianStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  const check = useCallback(async () => {
    try {
      setState(await api.guardianStatus());
      setError(null);
    } catch {
      // 判定失败不锁屏（避免网络问题误伤），但保持上次状态并提示重试
      setError(GUARDIAN_COPY.fetchFailed);
    }
  }, []);

  useEffect(() => {
    void check();
    const timer = setInterval(() => void check(), GUARDIAN_POLL_MS);
    return () => clearInterval(timer);
  }, [check]);

  if (state?.locked) {
    return (
      <div className="flex min-h-[70vh] items-center justify-center px-6" data-testid="guardian-lock">
        <Card className="w-full max-w-lg">
          <CardHeader>
            <CardTitle>{GUARDIAN_COPY.title}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <p className="text-muted-foreground">{GUARDIAN_COPY.body}</p>
            <div className="flex flex-wrap items-center gap-2">
              {state.reasons.map((reason) => (
                <Badge key={reason} variant="warning">
                  {guardianReasonLabel(reason)}
                </Badge>
              ))}
            </div>
            <p data-testid="guardian-usage">{guardianUsageText(state)}</p>
            {state.available_from ? (
              <p className="text-muted-foreground">{guardianAvailableText(state.available_from)}</p>
            ) : null}
            <Button variant="outline" onClick={() => void check()}>
              {GUARDIAN_COPY.retry}
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <>
      {state?.suggest_break ? (
        <div className="mb-4">
          <Alert variant="warning" title="休息提醒">
            连续学习较久，建议起身活动 5 分钟，保护视力与注意力。
          </Alert>
        </div>
      ) : null}
      {error ? (
        <div className="mb-4">
          <Alert variant="info">{error}</Alert>
        </div>
      ) : null}
      {children}
    </>
  );
}
