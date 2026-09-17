"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  Alert,
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Separator,
  Skeleton,
  buttonVariants,
  cn,
} from "@xueban/ui";

import { fetchSubscription, type SubscriptionState } from "@/lib/api";
import { loadAccessToken } from "@/lib/auth-storage";

type PageState = "loading" | "unauthenticated" | "error" | "ready";

const PLAN_LABEL: Record<string, string> = {
  free: "免费版",
  trial: "试用中",
  pro: "专业版",
};

const PLAN_BADGE: Record<string, "default" | "success" | "warning" | "outline"> = {
  free: "outline",
  trial: "warning",
  pro: "success",
};

function formatDate(value: string | null): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat("zh-CN", { dateStyle: "long" }).format(new Date(value));
}

function remainingDays(value: string | null): number | null {
  if (!value) return null;
  const diff = new Date(value).getTime() - Date.now();
  return Math.max(0, Math.ceil(diff / 86_400_000));
}

export default function AppHomePage() {
  const [state, setState] = useState<PageState>("loading");
  const [subscription, setSubscription] = useState<SubscriptionState | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const token = loadAccessToken();
    if (!token) {
      setState("unauthenticated");
      return;
    }
    setState("loading");
    try {
      const data = await fetchSubscription(token);
      setSubscription(data);
      setState("ready");
    } catch {
      setError("登录状态已失效，请重新注册或登录。");
      setState("error");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const days = subscription ? remainingDays(subscription.expires_at) : null;

  return (
    <main className="flex-1">
      <section aria-labelledby="app-title" className="mx-auto w-full max-w-4xl px-6 py-16">
        <h1 id="app-title" className="text-4xl font-bold tracking-tight">
          学习中心
        </h1>
        <p className="mt-3 text-lg text-muted-foreground">
          这里展示你的订阅状态。完整的诊断、规划、讲解与练习功能在桌面端与移动端提供。
        </p>

        <div className="mt-10">
          {state === "loading" ? (
            <Card aria-busy="true">
              <CardHeader>
                <Skeleton className="h-6 w-32" />
                <Skeleton className="h-4 w-48" />
              </CardHeader>
              <CardContent className="space-y-3">
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-2/3" />
              </CardContent>
            </Card>
          ) : null}

          {state === "unauthenticated" ? (
            <Card>
              <CardHeader>
                <CardTitle>尚未登录</CardTitle>
                <CardDescription>请先注册或登录账号，再查看订阅状态与学习数据。</CardDescription>
              </CardHeader>
              <CardContent>
                <Link href="/register" className={cn(buttonVariants({ size: "lg" }))}>
                  免费注册并开通试用
                </Link>
              </CardContent>
            </Card>
          ) : null}

          {state === "error" ? (
            <div className="space-y-4">
              <Alert variant="danger" title="无法加载订阅状态">
                {error}
              </Alert>
              <div className="flex gap-3">
                <Button variant="outline" onClick={() => void load()}>
                  重试
                </Button>
                <Link href="/register" className={cn(buttonVariants({ variant: "ghost" }))}>
                  重新注册
                </Link>
              </div>
            </div>
          ) : null}

          {state === "ready" && subscription ? (
            <Card>
              <CardHeader>
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <CardTitle>订阅状态</CardTitle>
                  <Badge variant={PLAN_BADGE[subscription.plan] ?? "default"}>
                    {PLAN_LABEL[subscription.plan] ?? subscription.plan}
                  </Badge>
                </div>
                <CardDescription>
                  {subscription.plan === "trial"
                    ? "试用已开通，全部会员功能已解锁。"
                    : subscription.plan === "pro"
                      ? "专业版已生效，感谢你的支持。"
                      : "当前为免费版，可随时升级解锁全部功能。"}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4 text-sm">
                <dl className="grid gap-3 sm:grid-cols-2">
                  <div>
                    <dt className="text-muted-foreground">当前套餐</dt>
                    <dd className="mt-1 font-semibold">
                      {PLAN_LABEL[subscription.plan] ?? subscription.plan}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-muted-foreground">到期时间</dt>
                    <dd className="mt-1 font-semibold">{formatDate(subscription.expires_at)}</dd>
                  </div>
                  <div>
                    <dt className="text-muted-foreground">剩余天数</dt>
                    <dd className="mt-1 font-semibold">
                      {days === null ? "长期有效" : `${days} 天`}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-muted-foreground">自动续费</dt>
                    <dd className="mt-1 font-semibold">
                      {subscription.auto_renew ? "已开启" : "未开启"}
                    </dd>
                  </div>
                </dl>
                <Separator />
                <div className="flex flex-wrap gap-3">
                  <Link
                    href="/download"
                    className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
                  >
                    下载客户端
                  </Link>
                  <Link
                    href="/pricing"
                    className={cn(buttonVariants({ variant: "ghost", size: "sm" }))}
                  >
                    查看订阅方案
                  </Link>
                  <Link
                    href="/help"
                    className={cn(buttonVariants({ variant: "ghost", size: "sm" }))}
                  >
                    帮助中心
                  </Link>
                </div>
              </CardContent>
            </Card>
          ) : null}
        </div>
      </section>
    </main>
  );
}
