"use client";

/** 一年级强制休息闸门（§8 约束 2）。
 *
 * 与 GuardianGate 并排挂在 AppLayout 上：GuardianGate 管「今天还能不能学」
 * （服务端判定、家长可调），这里管「这一次连着学太久了必须歇」——
 * 阈值固定 20 分钟，休息时长固定 5 分钟，期间不能跳过。
 */

import type { ReactNode } from "react";

import { Alert, Card, CardContent, CardHeader, CardTitle } from "@xueban/ui";

import {
  useRestBreak,
  type RestBreakState,
  type UseRestBreakOptions,
} from "@/journey/use-rest-break";

/** 秒数格式化成「M 分 SS 秒」。倒计时里秒位补零，且绝不为负。 */
export function formatSeconds(total: number): string {
  const safe = Math.max(0, Math.floor(total));
  const minutes = Math.floor(safe / 60);
  const seconds = safe % 60;
  return `${minutes} 分 ${String(seconds).padStart(2, "0")} 秒`;
}

export function RestBreakOverlay({
  restRemainingSeconds,
}: {
  restRemainingSeconds: number;
}) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-background/95 px-6"
      data-testid="rest-break-overlay"
      role="dialog"
      aria-modal="true"
      aria-label="强制休息"
    >
      <Card className="w-full max-w-lg text-center">
        <CardHeader className="items-center">
          <CardTitle>休息一下，看看远处 👀</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col items-center gap-md">
          <p className="text-app text-muted-foreground">
            已经连着学了很久啦。站起来走一走，看看窗外的绿色，眼睛也要休息。
          </p>
          <p className="text-app-xl font-semibold tabular-nums" data-testid="rest-break-countdown">
            {formatSeconds(restRemainingSeconds)}
          </p>
          <p className="text-app-xs text-muted-foreground">
            休息够了就能继续，计时会重新开始。
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

export interface RestBreakGateProps extends UseRestBreakOptions {
  children: ReactNode;
  /**
   * 直接指定状态，绕过计时（组件测试与 Storybook 用）。
   * 生产路径不要传：真实状态一律来自 ``useRestBreak``。
   */
  state?: Partial<RestBreakState>;
}

export function RestBreakGate({ children, state, ...options }: RestBreakGateProps) {
  const measured = useRestBreak(options);
  const breakState: RestBreakState = { ...measured, ...state };

  return (
    <>
      {breakState.warning && !breakState.resting ? (
        <div className="mb-4 px-4">
          <Alert variant="warning" title="快到休息时间了">
            已经学了 {breakState.elapsedMinutes} 分钟，还剩{" "}
            {formatSeconds(breakState.remainingSeconds)}，先放下手里的题。
          </Alert>
        </div>
      ) : null}
      {children}
      {breakState.resting ? (
        <RestBreakOverlay restRemainingSeconds={breakState.restRemainingSeconds} />
      ) : null}
    </>
  );
}
