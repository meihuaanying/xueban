import type { Metadata } from "next";
import Link from "next/link";

import { CONTACT_EMAIL } from "@/lib/site";

export const metadata: Metadata = {
  title: "隐私政策",
  description:
    "学伴隐私政策：说明我们收集哪些信息、如何使用与保护学习数据、未成年人信息处理规则，以及你享有的查询、更正、删除与注销权利。",
  alternates: { canonical: "/privacy" },
  openGraph: {
    title: "学伴隐私政策",
    description: "学习数据的收集范围、使用方式与你的权利。",
    url: "/privacy",
  },
};

const sections = [
  {
    title: "一、引言与适用范围",
    paragraphs: [
      "学伴（XueBan，以下称“我们”）深知个人信息与学习数据的重要性。本政策说明你在使用学伴网站、桌面客户端与移动客户端（以下统称“本服务”）时，我们如何收集、使用、存储、共享和保护你的信息，以及你享有的权利。",
      "使用本服务前，请仔细阅读本政策。若你为未成年人，请在监护人陪同下阅读，并由监护人决定是否同意。",
    ],
  },
  {
    title: "二、我们收集的信息",
    paragraphs: [
      "账号信息：手机号、密码（加密存储）、昵称、角色（学生 / 家长）、学段信息、订阅与试用状态。",
      "学习数据：诊断作答、练习与模考记录、错题与掌握度画像、讲解求助层级、复习计划完成情况、学习时长与打卡记录。",
      "设备与日志：设备类型、操作系统、浏览器或客户端版本、IP 地址、请求日志与错误日志（含用于排查问题的 trace_id）。",
      "你主动提供的信息：反馈、客服沟通、上传的文档或图片（用于解析与练习生成）。",
    ],
  },
  {
    title: "三、信息的使用",
    paragraphs: [
      "提供与改进本服务：生成学情画像、学习路径、任务卡、周报与冲刺包，推荐练习与讲解内容。",
      "安全与风控：识别异常登录、滥用行为，保障服务稳定与内容安全。",
      "订阅与结算：开通试用、处理 mock 或正式支付、对账与退订。",
      "法律合规：在法律法规要求时履行配合义务。",
    ],
  },
  {
    title: "四、未成年人信息保护",
    paragraphs: [
      "我们遵循未成年人利益优先原则，实行数据最小必要收集。未成年人账号的注册、订阅购买与功能开通需取得监护人同意。",
      "未成年人的学习数据仅用于学情分析与安全保护，不用于与学习无关的商业目的。更多说明见《未成年人保护声明》。",
    ],
  },
  {
    title: "五、信息的存储与保护",
    paragraphs: [
      "数据存储于中国境内的服务器，采用传输加密与访问控制、最小权限账号、操作审计等措施。密码使用单向哈希存储，任何人员均无法读取明文。",
      "我们按实现处理目的所需的最短期限保存信息；超出保存期限或你注销账号后，我们会删除或匿名化处理，法律法规另有规定的除外。",
    ],
  },
  {
    title: "六、信息共享与对外提供",
    paragraphs: [
      "我们不会出售你的个人信息。仅在以下情形对外提供：取得你的单独同意；为提供服务所必需且受托方（如云服务、短信、模型服务商）遵守保密与安全义务；法律法规或监管机关要求。",
      "涉及跨境传输时，我们将依法进行安全评估并单独告知。",
    ],
  },
  {
    title: "七、你的权利",
    paragraphs: [
      "你可以查询、更正、复制你的账号与学习数据；可以删除错题、文档等学习记录；可以注销账号并要求删除个人信息；可以撤回已作出的同意。",
      `行使上述权利或提出投诉，请发送邮件至 ${CONTACT_EMAIL}，我们将在 15 个工作日内处理并回复。`,
    ],
  },
  {
    title: "八、Cookie 与本地存储",
    paragraphs: [
      "我们使用必要的 Cookie 与浏览器本地存储维持登录态、保存偏好与保障安全；不使用第三方广告跟踪 Cookie。你可以通过浏览器设置清理本地存储，但可能影响登录状态。",
    ],
  },
  {
    title: "九、政策更新与联系我们",
    paragraphs: [
      "本政策可能随功能与法规变化更新，更新后我们会在本页面公示并标注日期；重大变更将以显著方式提示。",
      `如对本政策有任何疑问，请联系：${CONTACT_EMAIL}。`,
    ],
  },
];

export default function PrivacyPage() {
  return (
    <main className="flex-1">
      <article className="mx-auto w-full max-w-3xl px-6 py-16">
        <h1 className="text-4xl font-bold tracking-tight">隐私政策</h1>
        <p className="mt-3 text-sm text-muted-foreground">更新日期：2026 年 9 月 15 日</p>
        <p className="mt-6 leading-7 text-muted-foreground">
          本政策适用于学伴全端服务。我们会依据本政策处理你的个人信息与学习数据，并持续保障你的知情权与选择权。
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
          <Link className="ml-1 underline underline-offset-4" href="/minor-protection">
            未成年人保护声明
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
