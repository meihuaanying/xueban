/** 防沉迷闸门（T7.2 / F-40）：服务端判定锁屏，客户端每 60s 复核，无法本地绕过。 */

import { useCallback, useEffect, useState, type ReactNode } from "react";
import { Alert, Badge, Button, Card, CardContent, CardHeader, CardTitle } from "@xueban/ui";

import { api } from "@/lib/api";

interface GuardianState {
  locked: boolean;
  reasons: string[];
  used_minutes: number;
  limit_minutes: number | null;
  suggest_break: boolean;
  curfew_active: boolean;
  available_from: string | null;
}

const REASON_LABELS: Record<string, string> = {
  daily_limit: "今日学习时长已达上限",
  curfew: "当前不在允许使用时段",
};

export function GuardianGate({ children }: { children: ReactNode }) {
  const [state, setState] = useState<GuardianState | null>(null);
  const [error, setError] = useState<string | null>(null);

  const check = useCallback(async () => {
    try {
      setState(await api.guardianStatus());
      setError(null);
    } catch {
      // 判定失败不锁屏（避免网络问题误伤），但保持上次状态
      setError("防沉迷状态获取失败，将在稍后重试。");
    }
  }, []);

  useEffect(() => {
    void check();
    const timer = setInterval(() => void check(), 60_000);
    return () => clearInterval(timer);
  }, [check]);

  if (state?.locked) {
    return (
      <div
        className="flex min-h-[70vh] items-center justify-center px-6"
        data-testid="guardian-lock"
      >
        <Card className="w-full max-w-lg">
          <CardHeader>
            <CardTitle>学习时间已到</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <p className="text-muted-foreground">
              家长设置了使用管理，当前学习已暂停。看一会儿远处，休息一下再回来。
            </p>
            <div className="flex flex-wrap items-center gap-2">
              {state.reasons.map((reason) => (
                <Badge key={reason} variant="warning">
                  {REASON_LABELS[reason] ?? reason}
                </Badge>
              ))}
            </div>
            <p data-testid="guardian-usage">
              今日已学习 {state.used_minutes} 分钟
              {state.limit_minutes ? ` / 上限 ${state.limit_minutes} 分钟` : ""}
            </p>
            {state.available_from ? (
              <p className="text-muted-foreground">允许使用时段从 {state.available_from} 开始。</p>
            ) : null}
            <Button variant="outline" onClick={() => void check()}>
              我休息好了，重新检查
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
