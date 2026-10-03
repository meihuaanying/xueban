"use client";

/**
 * 儿童模式导航（§4.1）
 *
 * 一年级孩子读不懂「诊断 / 计划 / 单元」这些词，也点不中纯文字条目，所以
 * kids 主题下换成「图标 + 大字 + 吉祥物」这套：每个阶段一个一眼能认的
 * 象形符号，配吉祥物小伴在侧边时常驻。
 *
 * 这里刻意做成和 `JourneyNav` **并列**而不是替换它：
 * 家长/老师仍可能在同一个安装里切到专注模式（`theme-toggle`），
 * 两套导航各有各的适用人群，不该互相覆盖。
 */

import { AudioButton } from "@xueban/ui";

import type { JourneyStage } from "@/journey/stages";

/** 阶段 id → 象形图标。取 emoji 是因为它们跨平台自带「暖色 + 圆脸」，比描边图标更接近儿童读物。 */
const STAGE_ICONS: Record<string, string> = {
  today: "🔥",
  diagnosis: "🩺",
  plan: "🗺️",
  unit: "📖",
  mistakes: "🧩",
  review: "🔁",
};

const FALLBACK_ICON = "⭐";

export interface KidsNavItem {
  id: JourneyStage;
  label: string;
}

export interface KidsNavBarProps {
  items: readonly KidsNavItem[];
  active: string;
  /** 直接接 `useJourney().goTo`，所以形参必须是 JourneyStage 而不是任意 string */
  onNavigate: (id: JourneyStage) => void;
  speakable?: boolean;
}

export function iconOf(id: string): string {
  return STAGE_ICONS[id] ?? FALLBACK_ICON;
}

/**
 * 吉祥物「小伴」。
 *
 * 朗读的是固定欢迎语而不是当前页内容——孩子迷路时有个声音说「我在」，比
 * 每次都把整页念一遍有用，也不至于因为导航抖动就重复播报。
 */
export function KidsMascot({ speakable = false }: { speakable?: boolean }) {
  return (
    <div className="flex items-center gap-sm px-sm py-xs" data-testid="kids-mascot">
      <span aria-hidden className="text-app-xl leading-none">
        🐼
      </span>
      <span className="text-app-sm font-semibold text-sidebar-foreground">小伴</span>
      {speakable ? <AudioButton text="小伴在这儿，我们一起学" /> : null}
    </div>
  );
}

export function KidsNavBar({
  items,
  active,
  onNavigate,
  speakable = false,
}: KidsNavBarProps) {
  return (
    <nav
      aria-label="学习导航"
      data-testid="kids-nav"
      className="flex w-[var(--sidebar-width)] shrink-0 flex-col gap-md border-r border-sidebar-border bg-sidebar px-sm py-md"
    >
      <KidsMascot speakable={speakable} />

      <ol className="flex flex-col gap-hair">
        {items.map((item) => {
          const current = item.id === active;
          return (
            <li key={item.id}>
              <button
                type="button"
                aria-current={current ? "page" : undefined}
                data-testid={`kids-nav-${item.id}`}
                onClick={() => onNavigate(item.id)}
                className={[
                  "flex min-h-[var(--tap-min)] w-full items-center gap-sm rounded-control px-sm py-xs text-app",
                  "transition-colors",
                  current
                    ? "bg-primary font-semibold text-primary-foreground"
                    : "text-sidebar-foreground hover:bg-accent",
                ].join(" ")}
              >
                <span aria-hidden className="text-app-lg leading-none">
                  {iconOf(item.id)}
                </span>
                <span>{item.label}</span>
              </button>
            </li>
          );
        })}
      </ol>

      <p className="mt-auto px-sm text-app-xs text-muted-foreground">
        每天学一会儿，记得看看远处 👀
      </p>
    </nav>
  );
}
