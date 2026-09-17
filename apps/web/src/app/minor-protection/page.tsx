import type { Metadata } from "next";
import Link from "next/link";

import { CONTACT_EMAIL } from "@/lib/site";

export const metadata: Metadata = {
  title: "未成年人保护声明",
  description:
    "学伴未成年人保护声明：监护人同意、内容安全过滤、防沉迷与时长管理、家长端看板与投诉举报渠道，坚持未成年人利益优先。",
  alternates: { canonical: "/minor-protection" },
  openGraph: {
    title: "学伴未成年人保护声明",
    description: "监护人同意、内容安全、防沉迷与家长端看板。",
    url: "/minor-protection",
  },
};

const sections = [
  {
    title: "一、基本原则",
    paragraphs: [
      "学伴坚持未成年人利益优先，提供学习工具而非娱乐内容。我们不做诱导性付费设计，不使用针对未成年人的成瘾机制，不以延长使用时长为目标。",
      "本声明适用于未满 18 周岁的用户；未满 14 周岁的儿童，我们按儿童个人信息保护要求处理其信息。",
    ],
  },
  {
    title: "二、监护人知情同意",
    paragraphs: [
      "未成年人注册账号、购买订阅、开启拍照与语音等涉及个人信息的功能前，需取得监护人同意。",
      "监护人可通过家长绑定功能关联孩子账号，查看学习概览、设置使用时段与时长上限，并随时解除绑定或申请删除数据。",
    ],
  },
  {
    title: "三、内容安全",
    paragraphs: [
      "所有 AI 生成的讲解、题目与建议均经过内容安全审核流程；发现不当内容会即时拦截并记录，必要时转人工复核。",
      "我们提供举报入口，监护人可对任何内容提出复核申请，我们将在 24 小时内响应处理。",
    ],
  },
  {
    title: "四、防沉迷与时长管理",
    paragraphs: [
      "默认开启学习时长提醒与连续使用休息提示；监护人可以设置禁用时段（如夜间）与每日时长上限。",
      "我们不对未成年人开放社交、直播等与学习无关的功能。",
    ],
  },
  {
    title: "五、数据最小化",
    paragraphs: [
      "仅收集实现学习功能所必需的最小信息；未成年人的学习数据不用于定向广告或与学习无关的商业用途。",
      "账号注销或监护人提出删除要求后，我们将在法定期限内删除或匿名化相关信息。",
    ],
  },
  {
    title: "六、投诉与举报",
    paragraphs: [
      `如发现不利于未成年人保护的内容或功能，请发送邮件至 ${CONTACT_EMAIL}，或通过客户端内的举报入口反馈。我们承诺优先处理涉未成年人投诉。`,
    ],
  },
];

export default function MinorProtectionPage() {
  return (
    <main className="flex-1">
      <article className="mx-auto w-full max-w-3xl px-6 py-16">
        <h1 className="text-4xl font-bold tracking-tight">未成年人保护声明</h1>
        <p className="mt-3 text-sm text-muted-foreground">更新日期：2026 年 9 月 15 日</p>
        <p className="mt-6 leading-7 text-muted-foreground">
          学伴是面向学生与家长的学习软件。我们相信，技术应当帮助孩子独立学会，而不是替他完成任务。
          以下措施用于保障未成年人在使用本服务过程中的安全与权益。
        </p>
        {sections.map((section) => (
          <section key={section.title} className="mt-10">
            <h2 className="text-xl font-bold tracking-tight">{section.title}</h2>
            {section.paragraphs.map((paragraph) => (
              <p key={paragraph} className="mt-3 leading-7 text-muted-foreground">
                {paragraph}
              </p>
            ))}
          </section>
        ))}
        <p className="mt-10 text-sm text-muted-foreground">
          相关页面：
          <Link className="ml-1 underline underline-offset-4" href="/privacy">
            隐私政策
          </Link>
          、
          <Link className="ml-1 underline underline-offset-4" href="/help">
            帮助中心
          </Link>
          。
        </p>
      </article>
    </main>
  );
}
