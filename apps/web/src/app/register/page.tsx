"use client";

import Link from "next/link";
import { buttonVariants, cn } from "@xueban/ui";

import { RegisterForm } from "@/components/register-form";

/**
 * 注册页（REBUILD §8 约束 7：≤150 行）。表单逻辑见 `components/register-form.tsx`。
 * h1「免费注册，开启 7 天试用」与两个 checkbox 文案被 `conversion.spec.ts` 依赖，保持不变。
 */
export default function RegisterPage() {
  return (
    <main className="flex-1">
      <section aria-labelledby="register-title" className="mx-auto w-full max-w-5xl px-6 py-16">
        <div className="grid gap-10 lg:grid-cols-[1.1fr_1fr]">
          <div>
            <h1 id="register-title" className="text-4xl font-bold tracking-tight">
              免费注册，开启 7 天试用
            </h1>
            <p className="mt-3 text-lg text-muted-foreground">
              注册后立即开通试用，全端功能开放：诊断、规划、守护型讲解、智能练习、错题本与复盘。
            </p>
            <ul className="mt-6 space-y-3 text-sm text-muted-foreground">
              <li>· 分层提示讲解，不直接给答案</li>
              <li>· 自适应诊断 + 薄弱点优先练习</li>
              <li>· FSRS 复习计划与学习周报</li>
              <li>· 未成年人保护与家长端看板</li>
            </ul>
          </div>

          <RegisterForm />
        </div>

        <p className="mt-10 text-sm text-muted-foreground">
          需要帮助？查看
          <Link
            className={cn(buttonVariants({ variant: "link", size: "sm" }), "px-1")}
            href="/help"
          >
            帮助中心
          </Link>
          或
          <Link
            className={cn(buttonVariants({ variant: "link", size: "sm" }), "px-1")}
            href="/download"
          >
            下载客户端
          </Link>
          。
        </p>
      </section>
    </main>
  );
}
