import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "免费注册",
  description:
    "免费注册学伴账号，立即开通 7 天试用：自适应诊断、分层讲解、智能练习、错题本与复习计划全部开放。",
  alternates: { canonical: "/register" },
  openGraph: {
    title: "免费注册学伴",
    description: "注册即赠 7 天试用，无需绑定支付方式。",
    url: "/register",
  },
};

export default function RegisterLayout({ children }: { children: ReactNode }) {
  return children;
}
