"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import {
  Alert,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Checkbox,
  Input,
  Label,
  Select,
} from "@xueban/ui";

import { ApiError, registerAccount, startTrial } from "@/lib/api";
import { saveTokens } from "@/lib/auth-storage";

/**
 * 注册表单（REBUILD §8 约束 7：页面文件 ≤150 行，表单逻辑下沉到组件）。
 * 字段 id/name、`data-testid="role-select"`、按钮文案「注册并开通试用」与错误 Alert
 * 都被 `conversion.spec.ts` 依赖，拆分时保持逐字不变。
 */

const PHONE_PATTERN = /^1[3-9]\d{9}$/;

type SubmitState = "idle" | "submitting" | "activating" | "done";

export function RegisterForm() {
  const router = useRouter();
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [nickname, setNickname] = useState("");
  const [role, setRole] = useState<"student" | "parent">("student");
  const [isK12, setIsK12] = useState(false);
  const [agreed, setAgreed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [state, setState] = useState<SubmitState>("idle");

  const busy = state === "submitting" || state === "activating";

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    if (!PHONE_PATTERN.test(phone)) {
      setError("请输入有效的中国大陆手机号。");
      return;
    }
    if (password.length < 8) {
      setError("密码至少 8 位。");
      return;
    }
    if (!agreed) {
      setError("请先阅读并同意隐私政策与未成年人保护声明。");
      return;
    }

    setState("submitting");
    try {
      const tokens = await registerAccount({
        phone,
        password,
        nickname: nickname || undefined,
        is_k12: isK12,
        role,
      });
      saveTokens(tokens);
      setState("activating");
      if (role === "student") {
        await startTrial(tokens.access_token);
      }
      setState("done");
      // P0 / D4：Web 收缩为官网 + 下载页，学习中心由桌面端承载，故注册后引导下载客户端
      router.push("/download");
    } catch (caught) {
      if (caught instanceof ApiError) {
        setError(caught.message);
      } else {
        setError("无法连接服务器，请稍后重试。");
      }
      setState("idle");
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>创建账号</CardTitle>
        <CardDescription>手机号仅用于登录与账号安全，不会对外公开。</CardDescription>
      </CardHeader>
      <CardContent>
        <form className="space-y-5" method="post" onSubmit={handleSubmit} noValidate>
          <div className="space-y-2">
            <Label htmlFor="phone">手机号</Label>
            <Input
              id="phone"
              name="phone"
              type="tel"
              inputMode="numeric"
              autoComplete="tel"
              maxLength={11}
              placeholder="请输入 11 位手机号"
              value={phone}
              onChange={(event) => setPhone(event.target.value.trim())}
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">密码</Label>
            <Input
              id="password"
              name="password"
              type="password"
              autoComplete="new-password"
              minLength={8}
              maxLength={64}
              placeholder="至少 8 位，建议字母与数字组合"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="role">账号类型</Label>
            <Select
              id="role"
              data-testid="role-select"
              options={[
                { value: "student", label: "学生" },
                { value: "parent", label: "家长（查看孩子学情）" },
              ]}
              value={role}
              onChange={(event) => setRole(event.target.value as "student" | "parent")}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="nickname">昵称（选填）</Label>
            <Input
              id="nickname"
              name="nickname"
              maxLength={50}
              placeholder="用于学习报告展示"
              value={nickname}
              onChange={(event) => setNickname(event.target.value)}
            />
          </div>
          <div className="space-y-3">
            <label className="flex items-start gap-3 text-sm text-muted-foreground">
              <Checkbox
                className="mt-0.5"
                checked={isK12}
                onChange={(event) => setIsK12(event.target.checked)}
              />
              <span>我是 K12 阶段学生（含未成年人），希望启用未成年人保护与家长端。</span>
            </label>
            <label className="flex items-start gap-3 text-sm text-muted-foreground">
              <Checkbox
                className="mt-0.5"
                checked={agreed}
                onChange={(event) => setAgreed(event.target.checked)}
                required
              />
              <span>
                我已阅读并同意
                <Link className="mx-1 underline underline-offset-4" href="/privacy">
                  隐私政策
                </Link>
                与
                <Link className="mx-1 underline underline-offset-4" href="/minor-protection">
                  未成年人保护声明
                </Link>
                ；未成年人请在监护人陪同下注册。
              </span>
            </label>
          </div>

          {error ? (
            <Alert variant="danger" title="注册未完成" role="alert">
              {error}
            </Alert>
          ) : null}

          <Button type="submit" size="lg" className="w-full" disabled={busy}>
            {state === "submitting"
              ? "正在创建账号…"
              : state === "activating"
                ? "正在开通试用…"
                : "注册并开通试用"}
          </Button>
          <p className="text-xs text-muted-foreground">
            已有账号？
            <Link className="ml-1 underline underline-offset-4" href="/download">
              下载客户端开始学习
            </Link>
          </p>
        </form>
      </CardContent>
    </Card>
  );
}
