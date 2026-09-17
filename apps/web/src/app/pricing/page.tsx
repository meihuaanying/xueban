import type { Metadata } from "next";
import Link from "next/link";
import {
  Badge,
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
  buttonVariants,
  cn,
} from "@xueban/ui";

import { API_BASE_URL, type Plan } from "@/lib/api";

export const revalidate = 600;

export const metadata: Metadata = {
  title: "订阅定价",
  description:
    "学伴订阅定价：月度 / 季度 / 年度会员，免费注册赠 7 天试用。守护型 AI 讲解、智能练习、错题本与复习计划全包含。",
  alternates: { canonical: "/pricing" },
  openGraph: {
    title: "学伴订阅定价",
    description: "月度 / 季度 / 年度会员，注册即赠 7 天试用。",
    url: "/pricing",
  },
};

const FALLBACK_PLANS: Plan[] = [
  { cycle: "monthly", title: "月度会员", price_cents: 3900, days: 30 },
  { cycle: "quarterly", title: "季度会员", price_cents: 9900, days: 90 },
  { cycle: "yearly", title: "年度会员", price_cents: 29900, days: 365 },
];

const PERIOD_LABEL: Record<string, string> = {
  monthly: "/ 月",
  quarterly: "/ 季",
  yearly: "/ 年",
};

const PLAN_FEATURES: Record<string, string[]> = {
  monthly: ["五步学情闭环全部功能", "不限次分层讲解", "智能练习与错题本", "FSRS 复习计划"],
  quarterly: ["月度会员全部权益", "模考与无辅助测评", "周报与冲刺包", "优先客服支持"],
  yearly: ["季度会员全部权益", "全端同步（桌面 / 移动）", "年度学情报告", "新功能优先体验"],
};

async function loadPlans(): Promise<Plan[]> {
  try {
    const response = await fetch(`${API_BASE_URL}/v1/billing/plans`, {
      next: { revalidate: 600 },
    });
    if (!response.ok) return FALLBACK_PLANS;
    const data = (await response.json()) as Plan[];
    return data.length > 0 ? data : FALLBACK_PLANS;
  } catch {
    // 构建期 API 不可达时使用与后端 PLAN_SPECS 对齐的静态套餐。
    return FALLBACK_PLANS;
  }
}

function formatPrice(cents: number): string {
  const yuan = cents / 100;
  return Number.isInteger(yuan) ? `¥${yuan}` : `¥${yuan.toFixed(2)}`;
}

export default async function PricingPage() {
  const plans = await loadPlans();

  return (
    <main className="flex-1">
      <section aria-labelledby="pricing-title" className="mx-auto w-full max-w-6xl px-6 py-16">
        <div className="max-w-2xl">
          <h1 id="pricing-title" className="text-4xl font-bold tracking-tight">
            订阅定价
          </h1>
          <p className="mt-3 text-lg text-muted-foreground">
            免费注册即赠 7 天试用，试用期包含全部会员权益；到期自动回到免费版，不扣费。
          </p>
        </div>

        <div className="mt-10 grid gap-6 lg:grid-cols-4">
          <Card className="flex flex-col">
            <CardHeader>
              <CardTitle>免费版</CardTitle>
              <CardDescription>先体验完整学习闭环</CardDescription>
            </CardHeader>
            <CardContent className="flex-1">
              <p className="text-3xl font-bold">¥0</p>
              <ul className="mt-4 space-y-2 text-sm text-muted-foreground">
                <li>自适应诊断与学情画像</li>
                <li>每日任务卡与学习路径</li>
                <li>基础分层讲解（每日有限次）</li>
                <li>错题本与基础练习</li>
              </ul>
            </CardContent>
            <CardFooter>
              <Link
                href="/register"
                className={cn(buttonVariants({ variant: "outline" }), "w-full")}
              >
                免费注册
              </Link>
            </CardFooter>
          </Card>

          {plans.map((plan) => {
            const highlighted = plan.cycle === "yearly";
            return (
              <Card
                key={plan.cycle}
                className={cn("flex flex-col", highlighted && "border-primary shadow-md")}
              >
                <CardHeader>
                  <div className="flex items-center justify-between gap-2">
                    <CardTitle>{plan.title}</CardTitle>
                    {highlighted ? <Badge>最划算</Badge> : null}
                  </div>
                  <CardDescription>
                    折合 {(plan.price_cents / 100 / (plan.days / 30)).toFixed(1)} 元 / 月
                  </CardDescription>
                </CardHeader>
                <CardContent className="flex-1">
                  <p className="text-3xl font-bold">
                    {formatPrice(plan.price_cents)}
                    <span className="ml-1 text-base font-normal text-muted-foreground">
                      {PERIOD_LABEL[plan.cycle] ?? `/ ${plan.days} 天`}
                    </span>
                  </p>
                  <ul className="mt-4 space-y-2 text-sm text-muted-foreground">
                    {(PLAN_FEATURES[plan.cycle] ?? []).map((feature) => (
                      <li key={feature}>{feature}</li>
                    ))}
                  </ul>
                </CardContent>
                <CardFooter>
                  <Link
                    href="/register"
                    className={cn(
                      buttonVariants({ variant: highlighted ? "primary" : "outline" }),
                      "w-full",
                    )}
                  >
                    开通{plan.title}
                  </Link>
                </CardFooter>
              </Card>
            );
          })}
        </div>

        <div className="mt-10 rounded-xl border border-border bg-card p-6 text-sm text-muted-foreground">
          <p className="font-semibold text-foreground">支付说明</p>
          <p className="mt-2">
            当前为开发阶段 mock 支付收银台，仅用于验证订阅流程；正式支付渠道（微信 /
            支付宝）开通后， 所有价格与权益以收银台页面为准。未成年人购买需取得监护人同意。
          </p>
        </div>
      </section>
    </main>
  );
}
