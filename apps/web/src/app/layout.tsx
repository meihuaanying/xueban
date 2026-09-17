import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";

import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";
import { SITE_URL } from "@/lib/site";

import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "学伴 · AI 学习软件",
    template: "%s | 学伴",
  },
  description:
    "以学情闭环为核心的 AI 学习软件：诊断、规划、讲解、练习、复盘。守护型 AI 讲解不直接给答案，把学生教到独立做得对。",
  metadataBase: new URL(SITE_URL),
  alternates: {
    canonical: "/",
  },
  keywords: ["AI 学习软件", "学情诊断", "自适应学习", "守护型讲解", "错题本", "FSRS 复习"],
  openGraph: {
    title: "学伴 · AI 学习软件",
    description: "诊断 → 规划 → 讲解 → 练习 → 复盘，五步学情闭环，守护型 AI 讲解陪伴式学习。",
    locale: "zh_CN",
    type: "website",
    siteName: "学伴",
    url: SITE_URL,
  },
  twitter: {
    card: "summary_large_image",
    title: "学伴 · AI 学习软件",
    description: "守护型 AI 讲解，把每一道题教到你自己会做。",
  },
};

export const viewport: Viewport = {
  themeColor: "#1f66f5",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <head>
        {/* 首帧应用主题，避免暗色模式闪烁（T9.3） */}
        <script
          dangerouslySetInnerHTML={{
            __html:
              "(function(){try{var t=localStorage.getItem('xueban.theme');var d=t?t==='dark':window.matchMedia('(prefers-color-scheme: dark)').matches;if(d)document.documentElement.classList.add('dark');}catch(e){}})();",
          }}
        />
      </head>
      <body className="flex min-h-screen flex-col bg-background font-sans text-foreground antialiased">
        <SiteHeader />
        {children}
        <SiteFooter />
      </body>
    </html>
  );
}
