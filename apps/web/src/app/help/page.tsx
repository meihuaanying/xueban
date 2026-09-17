import type { Metadata } from "next";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@xueban/ui";

import { CONTACT_EMAIL } from "@/lib/site";

export const metadata: Metadata = {
  title: "帮助中心",
  description:
    "学伴帮助中心：如何开始学习、守护型讲解的分层提示规则、订阅与试用说明、账号与数据安全常见问题。",
  alternates: { canonical: "/help" },
  openGraph: {
    title: "学伴帮助中心",
    description: "新手入门、守护型讲解规则、订阅试用与数据安全常见问题。",
    url: "/help",
  },
};

const faqs = [
  {
    question: "如何开始使用学伴？",
    answer:
      "访问注册页，用手机号创建账号后即可获得 7 天试用。第一件事是完成一次自适应诊断：系统会动态选题定位薄弱知识点，并生成你的第一份学情画像与学习路径。",
  },
  {
    question: "为什么讲解不直接给答案？",
    answer:
      "直接给答案会让学生停在“看懂了”，而不是“会做了”。学伴的守护型讲解按三层展开：先给思路提示，再给关键步骤，只有确实需要时才给完整解析。连续求助会触发同类变式练习，帮助巩固而不是跳过思考。",
  },
  {
    question: "提示可以跳过层级吗？",
    answer:
      "不可以。服务端状态机会校验提示顺序，必须从第一层开始逐层解锁；这是学伴的核心红线设计，用于保证讲解过程始终由学生主导思考。",
  },
  {
    question: "试用到期后会怎样？",
    answer:
      "试用期为 7 天，包含会员全部权益。到期后自动回到免费版，不扣费、不自动续订。你可以随时在定价页选择合适的订阅周期。",
  },
  {
    question: "如何取消订阅或关闭自动续费？",
    answer:
      "在个人中心可以随时取消自动续费，已购买的剩余时长继续有效，到期后不再扣费。如遇问题可邮件联系客服协助处理。",
  },
  {
    question: "学习数据会被如何使用？",
    answer:
      "学习记录用于生成学情画像、路径规划与复盘报告，帮助改进讲解与练习推荐。收集范围、保存期限与你享有的查询、更正、删除权利详见隐私政策。",
  },
  {
    question: "未成年人使用时有什么保护措施？",
    answer:
      "学伴默认启用内容安全过滤与使用时长提醒，并提供家长端看板用于查看学习情况。购买订阅与开通功能需监护人知情同意，详见未成年人保护声明。",
  },
];

export default function HelpPage() {
  return (
    <main className="flex-1">
      <section aria-labelledby="help-title" className="mx-auto w-full max-w-4xl px-6 py-16">
        <h1 id="help-title" className="text-4xl font-bold tracking-tight">
          帮助中心
        </h1>
        <p className="mt-3 text-lg text-muted-foreground">
          快速了解学伴的学习流程、守护型讲解规则与账号使用问题。
        </p>

        <div id="guardian" className="mt-10">
          <h2 className="text-2xl font-bold tracking-tight">守护型讲解规则</h2>
          <p className="mt-3 text-muted-foreground">每一道题的讲解会话都遵循同一套规则：</p>
          <ol className="mt-4 space-y-3">
            <li className="rounded-xl border border-border bg-card p-4">
              <p className="font-semibold">第一层：思路提示</p>
              <p className="mt-1 text-sm text-muted-foreground">
                给出方向与提问，引导你回忆相关概念，不出现完整解题步骤。
              </p>
            </li>
            <li className="rounded-xl border border-border bg-card p-4">
              <p className="font-semibold">第二层：关键步骤</p>
              <p className="mt-1 text-sm text-muted-foreground">
                卡住时分解关键步骤与易错点，仍由你完成推导与计算。
              </p>
            </li>
            <li className="rounded-xl border border-border bg-card p-4">
              <p className="font-semibold">第三层：完整解析</p>
              <p className="mt-1 text-sm text-muted-foreground">
                展开完整解析，并附带同类变式题，确认你真正掌握。
              </p>
            </li>
          </ol>
        </div>

        <h2 className="mt-12 text-2xl font-bold tracking-tight">常见问题</h2>
        <div className="mt-4 space-y-3">
          {faqs.map((faq) => (
            <details key={faq.question} className="rounded-xl border border-border bg-card p-4">
              <summary className="cursor-pointer font-semibold marker:text-primary">
                {faq.question}
              </summary>
              <p className="mt-3 text-sm leading-6 text-muted-foreground">{faq.answer}</p>
            </details>
          ))}
        </div>

        <Card className="mt-12">
          <CardHeader>
            <CardTitle>仍未解决？</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            <p>
              发送邮件至{" "}
              <a className="underline underline-offset-4" href={`mailto:${CONTACT_EMAIL}`}>
                {CONTACT_EMAIL}
              </a>
              ，或先阅读{" "}
              <Link className="underline underline-offset-4" href="/privacy">
                隐私政策
              </Link>{" "}
              与{" "}
              <Link className="underline underline-offset-4" href="/minor-protection">
                未成年人保护声明
              </Link>
              。
            </p>
          </CardContent>
        </Card>
      </section>
    </main>
  );
}
