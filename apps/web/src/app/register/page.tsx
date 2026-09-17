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
  buttonVariants,
  cn,
} from "@xueban/ui";

import { ApiError, registerAccount, startTrial } from "@/lib/api";
import { saveTokens } from "@/lib/auth-storage";

const PHONE_PATTERN = /^1[3-9]\d{9}$/;

type SubmitState = "idle" | "submitting" | "activating" | "done";

export default function RegisterPage() {
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
      router.push("/app");
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
    <main className="flex-1">
      <section aria-labelledby="register-title" className="mx-auto w-full max-w-5xl px-6 py-16">
        <div className="grid gap-10 lg:grid-cols-[1.1fr_1fr]">
          <div>
            <h1 id="register-title" className="text-4xl font-bold tracking-tight">
              免费注册，开启 7 天试用
            </h1>
            <p className="mt-3 text-lg text-muted-foreground">
              注册后立即开通试用，全端功能开放：诊断、规划、守护型讲解、智能练习、错题本与复盘。
            </p>
            <ul className="mt-6 space-y-3 text-sm text-muted-foreground">
              <li>· 分层提示讲解，不直接给答案</li>
              <li>· 自适应诊断 + 薄弱点优先练习</li>
              <li>· FSRS 复习计划与学习周报</li>
              <li>· 未成年人保护与家长端看板</li>
            </ul>
          </div>

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
                  <Link className="ml-1 underline underline-offset-4" href="/app">
                    进入学习中心
                  </Link>
                </p>
              </form>
            </CardContent>
          </Card>
        </div>

        <p className="mt-10 text-sm text-muted-foreground">
          需要帮助？查看
          <Link
            className={cn(buttonVariants({ variant: "link", size: "sm" }), "px-1")}
            href="/help"
          >
            帮助中心
          </Link>
          或
          <Link
            className={cn(buttonVariants({ variant: "link", size: "sm" }), "px-1")}
            href="/download"
          >
            下载客户端
          </Link>
          。
        </p>
      </section>
    </main>
  );
}
