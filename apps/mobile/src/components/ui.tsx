/** 移动端基础 UI 原语（NativeWind）。 */

import type { ReactNode } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  Text,
  TextInput,
  View,
  type TextInputProps,
} from "react-native";

export function Screen({
  title,
  hint,
  children,
  scroll = true,
}: {
  title: string;
  hint?: string;
  children: ReactNode;
  scroll?: boolean;
}) {
  const body = (
    <View className="gap-4 p-4">
      <View>
        <Text className="text-2xl font-bold text-foreground" accessibilityRole="header">
          {title}
        </Text>
        {hint ? <Text className="mt-1 text-sm text-muted">{hint}</Text> : null}
      </View>
      {children}
    </View>
  );
  if (!scroll) return <View className="flex-1 bg-background">{body}</View>;
  return (
    <ScrollView className="flex-1 bg-background" contentContainerStyle={{ paddingBottom: 32 }}>
      {body}
    </ScrollView>
  );
}

export function Card({ children, testID }: { children: ReactNode; testID?: string }) {
  return (
    <View className="rounded-2xl border border-border bg-card p-4" testID={testID}>
      {children}
    </View>
  );
}

export function PrimaryButton({
  label,
  onPress,
  disabled,
  testID,
  variant = "primary",
}: {
  label: string;
  onPress: () => void;
  disabled?: boolean;
  testID?: string;
  variant?: "primary" | "outline";
}) {
  const base =
    variant === "primary" ? "bg-primary" : "border border-border bg-transparent";
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      testID={testID}
      disabled={disabled}
      onPress={onPress}
      className={`${base} items-center rounded-xl px-4 py-3 ${disabled ? "opacity-50" : "active:opacity-80"}`}
    >
      <Text className={variant === "primary" ? "font-semibold text-white" : "font-semibold text-foreground"}>
        {label}
      </Text>
    </Pressable>
  );
}

export function TextField({
  label,
  testID,
  ...props
}: TextInputProps & { label: string; testID?: string }) {
  return (
    <View className="gap-1">
      <Text className="text-sm text-muted">{label}</Text>
      <TextInput
        accessibilityLabel={label}
        testID={testID}
        className="rounded-xl border border-border bg-card px-3 py-3 text-base text-foreground"
        placeholderTextColor="#94a3b8"
        {...props}
      />
    </View>
  );
}

export function Badge({ label, tone = "default" }: { label: string; tone?: "default" | "success" | "warning" | "danger" }) {
  const tones = {
    default: "bg-secondary text-secondary-foreground",
    success: "bg-green-100 text-green-800",
    warning: "bg-amber-100 text-amber-800",
    danger: "bg-red-100 text-red-800",
  } as const;
  return (
    <View className={`self-start rounded-full px-2 py-0.5 ${tones[tone]}`}>
      <Text className="text-xs font-medium">{label}</Text>
    </View>
  );
}

export function Loading({ label = "加载中" }: { label?: string }) {
  return (
    <View className="flex-row items-center gap-2" accessibilityRole="progressbar" accessibilityLabel={label}>
      <ActivityIndicator />
      <Text className="text-sm text-muted">{label}</Text>
    </View>
  );
}

export function ErrorBlock({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <Card testID="error-block">
      <Text className="text-sm font-semibold text-danger">操作未完成</Text>
      <Text className="mt-1 text-sm text-muted">{message}</Text>
      {onRetry ? (
        <View className="mt-3">
          <PrimaryButton label="重试" variant="outline" onPress={onRetry} />
        </View>
      ) : null}
    </Card>
  );
}

export function EmptyBlock({ title, hint }: { title: string; hint: string }) {
  return (
    <Card>
      <Text className="text-sm font-semibold text-foreground">{title}</Text>
      <Text className="mt-1 text-sm text-muted">{hint}</Text>
    </Card>
  );
}
