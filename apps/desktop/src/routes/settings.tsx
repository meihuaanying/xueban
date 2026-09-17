/** 设置页（T5.7）：账号、订阅、通知与关于；数据层使用 TanStack Query。 */

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
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
  Switch,
} from "@xueban/ui";

import { ErrorBlock, LoadingBlock, SectionTitle } from "@/components/state";
import { ApiError, api, type BehaviorProfile, type SubscriptionState } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { isTauri } from "@/lib/token-store";

const PLAN_LABEL: Record<string, string> = {
  free: "免费版",
  trial: "试用中",
  pro: "专业版",
};

export default function SettingsPage() {
  const { user, refreshUser } = useAuth();
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [reviewNotify, setReviewNotify] = useState(true);
  const [taskNotify, setTaskNotify] = useState(true);

  const subscriptionQuery = useQuery<SubscriptionState>({
    queryKey: ["billing", "subscription"],
    queryFn: api.subscription,
  });
  const behaviorQuery = useQuery<BehaviorProfile>({
    queryKey: ["profile", "behavior"],
    queryFn: api.behavior,
  });
  const trialMutation = useMutation({
    mutationFn: api.startTrial,
    onSuccess: (data) => {
      queryClient.setQueryData(["billing", "subscription"], data);
    },
    onError: (caught) => {
      setError(caught instanceof ApiError ? caught.message : "试用开通失败。");
    },
  });

  if (subscriptionQuery.isPending) return <LoadingBlock rows={3} label="加载设置" />;

  if (subscriptionQuery.isError) {
    return (
      <div className="mx-auto max-w-4xl">
        <ErrorBlock
          message={
            subscriptionQuery.error instanceof ApiError
              ? subscriptionQuery.error.message
              : "加载设置数据失败。"
          }
          onRetry={() => void subscriptionQuery.refetch()}
        />
      </div>
    );
  }

  const subscription = subscriptionQuery.data;

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <SectionTitle hint="账号信息与订阅状态实时来自 API；登录态持久化于系统凭据库。">设置</SectionTitle>

      {error ? <ErrorBlock message={error} onRetry={() => setError(null)} /> : null}

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <CardTitle>账号</CardTitle>
            <Button variant="outline" size="sm" onClick={() => void refreshUser()}>
              刷新
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-2 text-sm" data-testid="account-card">
          <p>
            手机号：<span data-testid="account-phone">{user?.phone ?? "—"}</span>
          </p>
          <p>昵称：{user?.nickname ?? "未设置"}</p>
          <p>角色：{user?.role === "parent" ? "家长" : "学生"}</p>
          <p>
            K12 保护：
            {user?.is_k12 ? (
              <Badge variant="warning">已开启</Badge>
            ) : (
              <Badge variant="outline">未开启</Badge>
            )}
          </p>
          <p className="text-muted-foreground">
            凭据存储：{isTauri() ? "系统 keyring（凭据管理器/钥匙串）" : "浏览器本地存储（开发/E2E）"}
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>订阅状态</CardTitle>
          <CardDescription>与 API 的 /v1/billing/subscription 保持一致。</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 text-sm" data-testid="subscription-card">
          <p>
            套餐：
            <Badge
              variant={
                subscription?.plan === "pro"
                  ? "success"
                  : subscription?.plan === "trial"
                    ? "warning"
                    : "outline"
              }
              className="ml-2"
              data-testid="subscription-plan"
            >
              {subscription ? (PLAN_LABEL[subscription.plan] ?? subscription.plan) : "—"}
            </Badge>
          </p>
          <p>到期时间：{subscription?.expires_at ?? "—"}</p>
          <p>自动续费：{subscription?.auto_renew ? "已开启" : "未开启"}</p>
          {subscription && subscription.plan === "free" && !subscription.trial_used ? (
            <Button
              size="sm"
              disabled={trialMutation.isPending}
              onClick={() => void trialMutation.mutate()}
            >
              {trialMutation.isPending ? "开通中…" : "开通 7 天试用"}
            </Button>
          ) : null}
          {subscription?.trial_used && subscription.plan === "free" ? (
            <Alert variant="info">试用已使用过；可在官网定价页选择订阅周期。</Alert>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>行为画像（F-05）</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm" data-testid="behavior-card">
          {behaviorQuery.data ? (
            <>
              <p>
                学习风格：
                <Badge variant="default">{behaviorQuery.data.learning_style_label}</Badge>
              </p>
              <p className="text-muted-foreground">
                独立能力分：{behaviorQuery.data.independent_score ?? "—"} · 辅助下表现：
                {behaviorQuery.data.assisted_score ?? "—"}
              </p>
              <details className="text-xs text-muted-foreground">
                <summary className="cursor-pointer">查看可解释依据</summary>
                <pre className="mt-2 overflow-auto rounded bg-muted p-2">
                  {JSON.stringify(behaviorQuery.data.evidence, null, 2)}
                </pre>
              </details>
            </>
          ) : (
            <p className="text-muted-foreground">数据不足，完成几次练习后自动生成画像。</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>通知</CardTitle>
          <CardDescription>桌面端通知在本机生效；移动端推送由 M6 接入。</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <label className="flex items-center justify-between gap-4">
            <span>复习到期提醒</span>
            <Switch checked={reviewNotify} onChange={(event) => setReviewNotify(event.target.checked)} />
          </label>
          <Separator />
          <label className="flex items-center justify-between gap-4">
            <span>每日任务提醒</span>
            <Switch checked={taskNotify} onChange={(event) => setTaskNotify(event.target.checked)} />
          </label>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>关于</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-muted-foreground">
          <p>学伴桌面端 v0.1.0（Tauri 2）</p>
          <p>守护型 AI 讲解：不直接给答案，分层提示陪你独立做得对。</p>
          <p>自动更新为占位配置，正式发布渠道在 M11 接入。</p>
        </CardContent>
      </Card>
    </div>
  );
}
