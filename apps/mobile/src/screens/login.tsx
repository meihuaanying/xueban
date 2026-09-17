/** 登录 / 注册（T6.1）。 */

import { useState } from "react";
import { Pressable, Text, View } from "react-native";

import { ApiError } from "../lib/api";
import { useAuth } from "../lib/auth";
import { Card, PrimaryButton, Screen, TextField } from "../components/ui";

const PHONE_PATTERN = /^1[3-9]\d{9}$/;

export function LoginScreen() {
  const { login, register } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [nickname, setNickname] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit() {
    setError(null);
    if (!PHONE_PATTERN.test(phone)) {
      setError("请输入有效的中国大陆手机号。");
      return;
    }
    if (mode === "register" && password.length < 8) {
      setError("密码至少 8 位。");
      return;
    }
    setBusy(true);
    try {
      if (mode === "register") await register(phone, password, nickname || undefined);
      else await login(phone, password);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "无法连接服务器，请稍后重试。");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Screen title="学伴 · 移动端" hint="登录后进入学情闭环；登录态保存在系统安全存储（SecureStore）。" scroll={false}>
      <View className="flex-row gap-2">
        {(["login", "register"] as const).map((key) => (
          <Pressable
            key={key}
            accessibilityRole="tab"
            accessibilityState={{ selected: mode === key }}
            onPress={() => {
              setMode(key);
              setError(null);
            }}
            className={`flex-1 items-center rounded-xl px-4 py-2 ${
              mode === key ? "bg-accent" : "bg-secondary"
            }`}
          >
            <Text className={mode === key ? "font-semibold text-accent-foreground" : "text-muted"}>
              {key === "login" ? "登录" : "注册"}
            </Text>
          </Pressable>
        ))}
      </View>

      <Card>
        <View className="gap-3">
          <TextField
            label="手机号"
            testID="phone-input"
            keyboardType="phone-pad"
            maxLength={11}
            value={phone}
            onChangeText={setPhone}
            placeholder="11 位手机号"
          />
          <TextField
            label="密码"
            testID="password-input"
            secureTextEntry
            value={password}
            onChangeText={setPassword}
            placeholder={mode === "register" ? "至少 8 位" : "请输入密码"}
          />
          {mode === "register" ? (
            <TextField
              label="昵称（选填）"
              testID="nickname-input"
              value={nickname}
              onChangeText={setNickname}
            />
          ) : null}
          {error ? (
            <Text className="text-sm text-danger" testID="login-error">
              {error}
            </Text>
          ) : null}
          <PrimaryButton
            label={busy ? "处理中…" : mode === "login" ? "登录" : "注册并登录"}
            onPress={() => void submit()}
            disabled={busy}
            testID="submit-auth"
          />
        </View>
      </Card>
    </Screen>
  );
}
