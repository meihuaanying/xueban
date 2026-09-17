import Link from "next/link";
import { APP_NAME } from "@xueban/core";
import { buttonVariants, cn } from "@xueban/ui";

import { ThemeToggle } from "@/components/theme-toggle";
import { NAV_LINKS } from "@/lib/site";

/** 官网页眉：品牌、主导航与转化入口。 */
export function SiteHeader() {
  return (
    <header className="sticky top-0 z-40 w-full border-b border-border bg-background/90 backdrop-blur">
      <div className="mx-auto flex w-full max-w-6xl flex-wrap items-center gap-x-6 gap-y-3 px-6 py-3">
        <Link
          href="/"
          className="flex items-center gap-2 text-lg font-bold"
          aria-label={`${APP_NAME} 首页`}
        >
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-sm font-bold text-primary-foreground">
            学
          </span>
          <span>{APP_NAME}</span>
        </Link>
        <nav aria-label="主导航" className="order-3 w-full sm:order-none sm:w-auto">
          <ul className="flex flex-wrap items-center gap-x-5 gap-y-1 text-sm text-muted-foreground">
            {NAV_LINKS.map((link) => (
              <li key={link.href}>
                <Link className="transition-colors hover:text-foreground" href={link.href}>
                  {link.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
        <div className="ml-auto flex items-center gap-2">
          <ThemeToggle />
          <Link href="/app" className={cn(buttonVariants({ variant: "ghost", size: "sm" }))}>
            登录
          </Link>
          <Link href="/register" className={cn(buttonVariants({ size: "sm" }))}>
            免费注册
          </Link>
        </div>
      </div>
    </header>
  );
}
