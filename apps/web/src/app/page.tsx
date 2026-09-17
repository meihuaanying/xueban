import Link from "next/link";
import { APP_SLOGAN } from "@xueban/core";
import {
  Badge,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  buttonVariants,
  cn,
} from "@xueban/ui";

import { JsonLd } from "@/components/json-ld";
import { SITE_URL } from "@/lib/site";

const features = [
  {
    title: "自适应诊断",
    description:
      "CAT 动态选题：答对加难、答错降难，快速定位薄弱知识点；错因归因写入五类枚举，不做模糊评价。",
    tag: "F-01 / F-02",
  },
  {
    title: "BKT 学情画像",
    description: "贝叶斯知识追踪持续更新每一点掌握度，雷达图呈现学科结构，让进步可见、让短板具体。",
    tag: "F-03",
  },
  {
    title: "规划引擎",
    description:
      "按前置依赖拓扑排序生成学习路径，每日任务卡、考期倒排、落后自动压缩，计划始终跟着你走。",
    tag: "F-06 ~ F-10",
  },
  {
    title: "守护型讲解",
    description: "三层提示：先思路、再关键步骤、最后才是全解。SSE 流式输出，讲解不越层、不代做。",
    tag: "F-11（红线）",
  },
  {
    title: "智能练习与错题本",
    description:
      "薄弱知识点占比不低于 60%，7 天自动去重；错题分组重练，FSRS 间隔复习排进每日任务。",
    tag: "F-17 ~ F-19",
  },
  {
    title: "批改与无辅助测评",
    description:
      "客观题秒批、主观题逐步给分、作文多口径评阅；周期性无辅助限时测评，独立能力单独建模。",
    tag: "F-20 ~ F-28",
  },
];

const loop = [
  { step: "诊断", detail: "定位薄弱与错因" },
  { step: "规划", detail: "今天学什么、学多少" },
  { step: "讲解", detail: "分层提示，学会而不是看懂" },
  { step: "练习", detail: "薄弱优先，错题回炉" },
  { step: "复盘", detail: "周报、日历、冲刺包" },
];

const guardians = [
  {
    step: "1",
    title: "给思路",
    detail: "先反问与提示，激活你自己的思考。",
  },
  {
    step: "2",
    title: "给关键步骤",
    detail: "卡住时分解关键步骤，仍由你完成推导。",
  },
  {
    step: "3",
    title: "给完整解析",
    detail: "只有在确实需要时才展开全解，并附同类变式巩固。",
  },
];

export default function HomePage() {
  const jsonLd = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "Organization",
        name: "学伴（XueBan）",
        url: SITE_URL,
        description: "以学情闭环为核心的 AI 学习软件，提供守护型 AI 讲解。",
      },
      {
        "@type": "WebSite",
        name: "学伴",
        url: SITE_URL,
        inLanguage: "zh-CN",
      },
      {
        "@type": "Product",
        name: "学伴 AI 学习软件",
        description:
          "诊断、规划、讲解、练习、复盘五步学情闭环；守护型 AI 讲解不直接给答案，分层提示陪学生独立做得对。",
        brand: { "@type": "Brand", name: "学伴" },
        offers: {
          "@type": "Offer",
          price: "0",
          priceCurrency: "CNY",
          description: "免费注册，赠送 7 天试用",
        },
      },
    ],
  };

  return (
    <main className="flex-1">
      <JsonLd data={jsonLd} />

      <section aria-labelledby="hero-title" className="border-b border-border bg-card">
        <div className="mx-auto flex w-full max-w-6xl flex-col items-center gap-6 px-6 py-20 text-center">
          <Badge variant="default">AI 学习软件 · 全端同步</Badge>
          <h1 id="hero-title" className="max-w-3xl text-4xl font-bold tracking-tight sm:text-6xl">
            {APP_SLOGAN}
          </h1>
          <p className="max-w-2xl text-lg text-muted-foreground">
            诊断 → 规划 → 讲解 → 练习 → 复盘，五步学情闭环。守护型 AI 讲解不直接给答案，
            而是分层提示，陪你独立做得对。
          </p>
          <div className="flex flex-wrap items-center justify-center gap-4">
            <Link href="/register" className={cn(buttonVariants({ size: "lg" }))}>
              免费开始学习
            </Link>
            <Link
              href="/#guardian"
              className={cn(buttonVariants({ variant: "outline", size: "lg" }))}
            >
              了解守护型讲解
            </Link>
          </div>
          <p className="text-sm text-muted-foreground">
            注册即赠 7 天试用 · 无需绑定支付方式 · 未成年人保护优先
          </p>
        </div>
      </section>

      <section
        id="features"
        aria-labelledby="features-title"
        className="mx-auto w-full max-w-6xl px-6 py-16"
      >
        <div className="max-w-2xl">
          <h2 id="features-title" className="text-3xl font-bold tracking-tight">
            不是又一个“答案生成器”
          </h2>
          <p className="mt-3 text-muted-foreground">
            学伴把学习过程拆成可测量、可干预的闭环：先知道哪里不会，再决定学什么、怎么讲、
            练什么，最后用数据复盘。
          </p>
        </div>
        <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((feature) => (
            <Card key={feature.title}>
              <CardHeader>
                <CardTitle>{feature.title}</CardTitle>
                <CardDescription>{feature.description}</CardDescription>
              </CardHeader>
              <CardContent>
                <Badge variant="outline">{feature.tag}</Badge>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      <section
        id="guardian"
        aria-labelledby="guardian-title"
        className="border-y border-border bg-card"
      >
        <div className="mx-auto grid w-full max-w-6xl gap-10 px-6 py-16 lg:grid-cols-2">
          <div>
            <h2 id="guardian-title" className="text-3xl font-bold tracking-tight">
              守护型讲解：把“会做”留给学生
            </h2>
            <p className="mt-3 text-muted-foreground">
              直接把答案给你，等于替你把题做了。学伴的讲解按层级展开，每一层都要求你先思考；
              连续求助会触发回炉练习，而不是无限索取答案。
            </p>
            <Link
              href="/help#guardian"
              className={cn(buttonVariants({ variant: "link", size: "sm" }), "mt-4 px-0")}
            >
              了解分层提示如何工作 →
            </Link>
          </div>
          <ol className="grid gap-4 sm:grid-cols-3 lg:grid-cols-1">
            {guardians.map((item) => (
              <li
                key={item.step}
                className="flex gap-4 rounded-xl border border-border bg-background p-5"
              >
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary text-sm font-semibold text-primary-foreground">
                  {item.step}
                </span>
                <div>
                  <p className="font-semibold">{item.title}</p>
                  <p className="mt-1 text-sm text-muted-foreground">{item.detail}</p>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section aria-labelledby="loop-title" className="mx-auto w-full max-w-6xl px-6 py-16">
        <h2 id="loop-title" className="text-3xl font-bold tracking-tight">
          五步学情闭环
        </h2>
        <p className="mt-3 max-w-2xl text-muted-foreground">
          每一步都有数据留下：诊断留下错因，讲解留下求助层级，练习留下错题与复习计划，
          复盘把这些串成下一周的行动。
        </p>
        <ol className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          {loop.map((item, index) => (
            <li key={item.step} className="rounded-xl border border-border bg-card p-5">
              <p className="text-sm text-muted-foreground">第 {index + 1} 步</p>
              <p className="mt-1 text-lg font-semibold">{item.step}</p>
              <p className="mt-2 text-sm text-muted-foreground">{item.detail}</p>
            </li>
          ))}
        </ol>
      </section>

      <section aria-labelledby="trust-title" className="border-t border-border bg-card">
        <div className="mx-auto grid w-full max-w-6xl gap-6 px-6 py-16 sm:grid-cols-3">
          <h2 id="trust-title" className="sr-only">
            为什么选择学伴
          </h2>
          <div>
            <h3 className="text-lg font-semibold">独立能力单独建模</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              周期性无辅助限时测评，服务端强制关闭提示，防止“拐杖效应”。
            </p>
          </div>
          <div>
            <h3 className="text-lg font-semibold">未成年人保护优先</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              内容安全过滤、防沉迷与家长端看板，详见未成年人保护声明。
            </p>
          </div>
          <div>
            <h3 className="text-lg font-semibold">数据可查可控</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              学习数据用于学情分析与服务改进，隐私政策说明收集范围与你的权利。
            </p>
          </div>
        </div>
      </section>

      <section aria-labelledby="cta-title" className="mx-auto w-full max-w-6xl px-6 py-20">
        <div className="flex flex-col items-center gap-4 rounded-2xl border border-border bg-card px-6 py-12 text-center">
          <h2 id="cta-title" className="text-3xl font-bold tracking-tight">
            今天就把第一道题学到会
          </h2>
          <p className="max-w-xl text-muted-foreground">
            注册即赠 7 天试用，支持 Web / Windows / macOS / Linux / Android 全端学习。
          </p>
          <div className="flex flex-wrap items-center justify-center gap-4">
            <Link href="/register" className={cn(buttonVariants({ size: "lg" }))}>
              免费注册
            </Link>
            <Link
              href="/download"
              className={cn(buttonVariants({ variant: "outline", size: "lg" }))}
            >
              下载客户端
            </Link>
          </div>
        </div>
      </section>
    </main>
  );
}
