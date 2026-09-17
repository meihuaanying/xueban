import Link from "next/link";
import { APP_NAME, APP_SLOGAN } from "@xueban/core";

import { CONTACT_EMAIL, FOOTER_LINKS } from "@/lib/site";

/** 官网页脚：导航、合规入口与版权。 */
export function SiteFooter() {
  return (
    <footer className="border-t border-border bg-card">
      <div className="mx-auto grid w-full max-w-6xl gap-10 px-6 py-12 sm:grid-cols-2 lg:grid-cols-4">
        <div className="space-y-3">
          <p className="text-lg font-bold">{APP_NAME}</p>
          <p className="text-sm text-muted-foreground">{APP_SLOGAN}</p>
          <p className="text-xs text-muted-foreground">
            联系邮箱：
            <a className="underline underline-offset-4" href={`mailto:${CONTACT_EMAIL}`}>
              {CONTACT_EMAIL}
            </a>
          </p>
        </div>
        {FOOTER_LINKS.map((group) => (
          <nav key={group.title} aria-label={group.title}>
            <p className="text-sm font-semibold">{group.title}</p>
            <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
              {group.links.map((link) => (
                <li key={link.href}>
                  <Link className="transition-colors hover:text-foreground" href={link.href}>
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
        ))}
      </div>
      <div className="border-t border-border">
        <div className="mx-auto flex w-full max-w-6xl flex-wrap items-center justify-between gap-2 px-6 py-4 text-xs text-muted-foreground">
          <p>
            © {new Date().getFullYear()} {APP_NAME}（XueBan）. 保留所有权利。
          </p>
          <p>守护型 AI 讲解 · 不直接给答案 · 未成年人保护优先</p>
        </div>
      </div>
    </footer>
  );
}
