/**
 * 防沉迷闸门（T7.2 / F-40）：服务端判定锁屏，与原桌面端一致。
 *
 * 状态形状、锁定原因文案、锁屏页文案与轮询周期都来自 `@xueban/core` 的 `guardian`
 * （三端共享，§8 约束 7）；本文件只负责原生端的画法。
 */

import {
  GUARDIAN_COPY,
  GUARDIAN_POLL_MS,
  guardianAvailableText,
  guardianReasonLabel,
  guardianUsageText,
  type GuardianStatus,
} from "@xueban/core";
import { useCallback, useEffect, useState, type ReactNode } from "react";
import { Text, View } from "react-native";

import { api } from "../lib/api";
import { Card, PrimaryButton } from "./ui";

export function GuardianGate({ children }: { children: ReactNode }) {
  const [state, setState] = useState<GuardianStatus | null>(null);

  const check = useCallback(async () => {
    try {
      setState(await api.guardianStatus());
    } catch {
      // 网络异常不锁屏
    }
  }, []);

  useEffect(() => {
    void check();
    const timer = setInterval(() => void check(), GUARDIAN_POLL_MS);
    return () => clearInterval(timer);
  }, [check]);

  if (state?.locked) {
    return (
      <View className="flex-1 items-center justify-center bg-background p-6" testID="guardian-lock">
        <Card testID="guardian-card">
          <Text className="text-lg font-semibold text-foreground">{GUARDIAN_COPY.title}</Text>
          <Text className="mt-2 text-sm text-muted">{GUARDIAN_COPY.body}</Text>
          {state.reasons.map((reason) => (
            <Text key={reason} className="mt-2 text-sm text-warning">
              {guardianReasonLabel(reason)}
            </Text>
          ))}
          <Text className="mt-2 text-sm text-muted" testID="guardian-usage">
            {guardianUsageText(state)}
          </Text>
          {state.available_from ? (
            <Text className="mt-1 text-xs text-muted">
              {guardianAvailableText(state.available_from)}
            </Text>
          ) : null}
          <View className="mt-3">
            <PrimaryButton
              label={GUARDIAN_COPY.retry}
              variant="outline"
              onPress={() => void check()}
            />
          </View>
        </Card>
      </View>
    );
  }

  return <>{children}</>;
}
