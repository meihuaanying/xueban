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

import { RELEASE_BASE_URL } from "@/lib/site";

export const metadata: Metadata = {
  title: "下载客户端",
  description:
    "下载学伴客户端：Windows、macOS、Linux 桌面版与 Android APK，学习进度全端同步；也可直接在浏览器中使用 Web 版。",
  alternates: { canonical: "/download" },
  openGraph: {
    title: "下载学伴客户端",
    description: "Windows / macOS / Linux / Android 全端同步，或直接使用 Web 版。",
    url: "/download",
  },
};

const platforms = [
  {
    name: "Windows",
    detail: "Windows 10/11（64 位）· 安装包 .exe",
    fileName: "XueBan-Setup-x64.exe",
    status: "最新 Release",
  },
  {
    name: "macOS",
    detail: "macOS 12+ · Intel 与 Apple Silicon（通用包）",
    fileName: "XueBan-universal.dmg",
    status: "最新 Release",
  },
  {
    name: "Linux",
    detail: "Ubuntu 22.04+ 等主流发行版 · AppImage / deb",
    fileName: "XueBan-x86_64.AppImage",
    status: "最新 Release",
  },
  {
    name: "Android",
    detail: "Android 9+ · APK 直装",
    fileName: "xueban-release.apk",
    status: "上架审核中",
  },
];

export default function DownloadPage() {
  return (
    <main className="flex-1">
      <section aria-labelledby="download-title" className="mx-auto w-full max-w-6xl px-6 py-16">
        <div className="max-w-2xl">
          <h1 id="download-title" className="text-4xl font-bold tracking-tight">
            下载学伴
          </h1>
          <p className="mt-3 text-lg text-muted-foreground">
            桌面端提供完整学习体验（含 LaTeX 公式与流式讲解），移动端支持拍照搜题与语音输入。
            现在也可以直接在浏览器中使用 Web 版，学习进度多端同步。
          </p>
        </div>

        <div className="mt-8 flex flex-wrap items-center gap-3">
          <Link href="/register" className={cn(buttonVariants({ size: "lg" }))}>
            使用 Web 版学习
          </Link>
          <p className="text-sm text-muted-foreground">
            桌面端安装包由 CI 于每个版本自动构建并发布到 Release，下载页始终指向最新版本。
          </p>
        </div>

        <div className="mt-10 grid gap-4 sm:grid-cols-2">
          {platforms.map((platform) => (
            <Card key={platform.name} className="flex flex-col">
              <CardHeader>
                <div className="flex items-center justify-between gap-2">
                  <CardTitle>{platform.name}</CardTitle>
                  <Badge variant="outline">{platform.status}</Badge>
                </div>
                <CardDescription>{platform.detail}</CardDescription>
              </CardHeader>
              <CardContent className="flex-1 text-sm text-muted-foreground">
                文件名：{platform.fileName}
              </CardContent>
              <CardFooter>
                <a
                  href={`${RELEASE_BASE_URL}/${platform.fileName}`}
                  className={cn(buttonVariants({ variant: "outline" }), "w-full")}
                >
                  前往 Release 下载
                </a>
              </CardFooter>
            </Card>
          ))}
        </div>

        <div className="mt-10 rounded-xl border border-border bg-card p-6 text-sm text-muted-foreground">
          <p className="font-semibold text-foreground">安装与校验</p>
          <ul className="mt-2 list-disc space-y-1 pl-5">
            <li>安装前请核对发布页提供的 SHA-256 校验值，避免第三方来源篡改。</li>
            <li>Windows 安装包使用 Tauri 构建，首次运行如遇 SmartScreen 提示请选择“仍要运行”。</li>
            <li>Android 版本安装需在系统设置中允许安装未知来源应用。</li>
          </ul>
        </div>
      </section>
    </main>
  );
}
