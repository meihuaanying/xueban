/** 防沉迷闸门（T7.2 / F-40）：服务端判定锁屏，移动端与桌面端一致。 */

import { useCallback, useEffect, useState, type ReactNode } from "react";
import { Text, View } from "react-native";

import { api } from "../lib/api";
import { Card, PrimaryButton } from "./ui";

interface GuardianState {
  locked: boolean;
  reasons: string[];
  used_minutes: number;
  limit_minutes: number | null;
  available_from: string | null;
}

const REASON_LABELS: Record<string, string> = {
  daily_limit: "今日学习时长已达上限",
  curfew: "当前不在允许使用时段",
};

export function GuardianGate({ children }: { children: ReactNode }) {
  const [state, setState] = useState<GuardianState | null>(null);

  const check = useCallback(async () => {
    try {
      setState(await api.guardianStatus());
    } catch {
      // 网络异常不锁屏
    }
  }, []);

  useEffect(() => {
    void check();
    const timer = setInterval(() => void check(), 60_000);
    return () => clearInterval(timer);
  }, [check]);

  if (state?.locked) {
    return (
      <View className="flex-1 items-center justify-center bg-background p-6" testID="guardian-lock">
        <Card testID="guardian-card">
          <Text className="text-lg font-semibold text-foreground">学习时间已到</Text>
          <Text className="mt-2 text-sm text-muted">
            家长设置了使用管理，当前学习已暂停。休息一下再回来。
          </Text>
          {state.reasons.map((reason) => (
            <Text key={reason} className="mt-2 text-sm text-warning">
              {REASON_LABELS[reason] ?? reason}
            </Text>
          ))}
          <Text className="mt-2 text-sm text-muted" testID="guardian-usage">
            今日已学习 {state.used_minutes} 分钟
            {state.limit_minutes ? ` / 上限 ${state.limit_minutes} 分钟` : ""}
          </Text>
          {state.available_from ? (
            <Text className="mt-1 text-xs text-muted">允许使用时段从 {state.available_from} 开始。</Text>
          ) : null}
          <View className="mt-3">
            <PrimaryButton label="我休息好了，重新检查" variant="outline" onPress={() => void check()} />
          </View>
        </Card>
      </View>
    );
  }

  return <>{children}</>;
}
