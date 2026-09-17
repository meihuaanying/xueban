/** 免登录学情看板（F-41）：签名 token 只读访问，可吊销。 */

import type { Metadata } from "next";
import Link from "next/link";

import { Badge, Card, CardContent, CardHeader, CardTitle, StatCard, buttonVariants, cn } from "@xueban/ui";

import { API_BASE_URL, type ParentDashboard } from "@/lib/api";

export const metadata: Metadata = {
  title: "学情看板",
  robots: { index: false, follow: false },
};

export const dynamic = "force-dynamic";

async function loadDashboard(token: string): Promise<ParentDashboard | null> {
  try {
    const response = await fetch(`${API_BASE_URL}/v1/parents/dashboard/${token}`, {
      cache: "no-store",
    });
    if (!response.ok) return null;
    return (await response.json()) as ParentDashboard;
  } catch {
    return null;
  }
}

export default async function SharedDashboardPage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  const dashboard = await loadDashboard(token);

  if (!dashboard) {
    return (
      <main className="mx-auto max-w-3xl px-6 py-16">
        <Card>
          <CardHeader>
            <CardTitle>链接无效或已过期</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-muted-foreground">
            <p>该学情看板链接可能已被家长吊销或超过有效期。</p>
            <Link href="/" className={cn(buttonVariants({ variant: "outline" }))}>
              返回官网
            </Link>
          </CardContent>
        </Card>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-4xl space-y-6 px-6 py-16" data-testid="shared-dashboard">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">
          {dashboard.child_nickname ?? "孩子"}的学情看板
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          只读分享视图 · 数据生成于 {new Date(dashboard.generated_at).toLocaleString("zh-CN")}
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-4">
        <StatCard title="连续打卡" value={`${dashboard.streak_days} 天`} tone="success" />
        <StatCard title="近 7 天练习" value={`${dashboard.practice_7d} 题`} />
        <StatCard title="任务完成率" value={`${Math.round(dashboard.task_completion_7d * 100)}%`} />
        <StatCard title="待掌握错题" value={dashboard.mistakes_active} tone="danger" />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>掌握度分布</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap items-center gap-3 text-sm">
          <Badge variant="danger">红 {dashboard.mastery.red_count}</Badge>
          <Badge variant="warning">黄 {dashboard.mastery.yellow_count}</Badge>
          <Badge variant="success">绿 {dashboard.mastery.green_count}</Badge>
          <span className="text-muted-foreground">
            平均掌握度：
            {dashboard.mastery.average_mastery === null
              ? "—"
              : `${Math.round(dashboard.mastery.average_mastery * 100)}%`}
          </span>
          {dashboard.behavior_style ? (
            <span className="text-muted-foreground">学习风格：{dashboard.behavior_style}</span>
          ) : null}
        </CardContent>
      </Card>

      <p className="text-xs text-muted-foreground">
        本页面为家长分享的只读视图，不含对话原文与个人信息。
      </p>
    </main>
  );
}
