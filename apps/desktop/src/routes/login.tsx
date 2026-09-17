/** 登录 / 注册（T5.1）：登录态写入系统 keyring，成功后进入诊断。 */

import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { APP_NAME, APP_SLOGAN } from "@xueban/core";
import {
  Alert,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Input,
  Label,
  Tabs,
} from "@xueban/ui";

import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const PHONE_PATTERN = /^1[3-9]\d{9}$/;

export default function LoginPage() {
  const { login, register } = useAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [nickname, setNickname] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    if (!PHONE_PATTERN.test(phone)) {
      setError("请输入有效的中国大陆手机号。");
      return;
    }
    if (mode === "register" && password.length < 8) {
      setError("密码至少 8 位。");
      return;
    }
    if (mode === "login" && password.length === 0) {
      setError("请输入密码。");
      return;
    }
    setBusy(true);
    try {
      if (mode === "register") {
        await register(phone, password, nickname || undefined);
      } else {
        await login(phone, password);
      }
      navigate("/diagnosis", { replace: true });
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "无法连接服务器，请稍后重试。");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-6 py-12">
      <div className="w-full max-w-md space-y-6">
        <div className="space-y-2 text-center">
          <span className="inline-flex items-center rounded-full bg-accent px-3 py-1 text-xs font-medium text-accent-foreground">
            {APP_NAME} 桌面端
          </span>
          <h1 className="text-2xl font-bold tracking-tight">{APP_SLOGAN}</h1>
          <p className="text-sm text-muted-foreground">登录后进入学情闭环：诊断 → 规划 → 讲解 → 练习 → 复盘。</p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>{mode === "login" ? "登录" : "注册新账号"}</CardTitle>
            <CardDescription>登录态将写入系统凭据库（Windows 凭据管理器 / 钥匙串）。</CardDescription>
          </CardHeader>
          <CardContent>
            <Tabs
              tabs={[
                {
                  key: "login",
                  label: "登录",
                  content: null,
                },
                {
                  key: "register",
                  label: "注册",
                  content: null,
                },
              ]}
              defaultKey="login"
              onChange={(key) => {
                setMode(key === "register" ? "register" : "login");
                setError(null);
              }}
            />
            <form className="mt-4 space-y-4" onSubmit={handleSubmit} noValidate>
              <div className="space-y-2">
                <Label htmlFor="phone">手机号</Label>
                <Input
                  id="phone"
                  type="tel"
                  inputMode="numeric"
                  maxLength={11}
                  placeholder="请输入 11 位手机号"
                  value={phone}
                  onChange={(event) => setPhone(event.target.value.trim())}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="password">密码</Label>
                <Input
                  id="password"
                  type="password"
                  autoComplete={mode === "login" ? "current-password" : "new-password"}
                  placeholder={mode === "register" ? "至少 8 位" : "请输入密码"}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                />
              </div>
              {mode === "register" ? (
                <div className="space-y-2">
                  <Label htmlFor="nickname">昵称（选填）</Label>
                  <Input
                    id="nickname"
                    maxLength={50}
                    value={nickname}
                    onChange={(event) => setNickname(event.target.value)}
                  />
                </div>
              ) : null}
              {error ? (
                <Alert variant="danger" title="登录未完成">
                  {error}
                </Alert>
              ) : null}
              <Button type="submit" size="lg" className="w-full" disabled={busy}>
                {busy ? "处理中…" : mode === "login" ? "登录" : "注册并登录"}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
