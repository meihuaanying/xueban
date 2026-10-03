/** 主布局：左侧学习旅程导航 + 顶部用户栏（P0 旅程制重构，§4.1 学院派骨架）。 */

import { Outlet } from "react-router-dom";
import { Badge, Button } from "@xueban/ui";

import { useAuth } from "@/lib/auth";
import { GuardianGate } from "@/components/guardian-gate";
import { JourneyNav } from "@/components/journey-nav";
import { KidsNavBar } from "@/components/kids-navigation";
import { RestBreakGate } from "@/components/rest-break";
import { useJourney } from "@/journey/journey-context";
import { STAGES } from "@/journey/stages";
import { SyncIndicator } from "@/lib/sync";

const KIDS_NAV_ITEMS = STAGES.map((stage) => ({ id: stage.id, label: stage.label }));

const SKIN_LABEL = {
  kids: "儿童模式",
  focus: "专注模式",
} as const;

export function AppLayout() {
  const { user, logout } = useAuth();
  const { theme, mode, stage, goTo, setTheme, setMode } = useJourney();

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      {theme === "kids" ? (
        // 儿童模式换成图标 + 吉祥物导航（§4.1）。刻意与学院派侧边栏并存：
        // 家长/老师仍可切回专注模式，两套导航各有适用人群。
        <KidsNavBar items={KIDS_NAV_ITEMS} active={stage} onNavigate={goTo} speakable />
      ) : (
        <JourneyNav />
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between gap-4 border-b border-border bg-card px-lg py-xs">
          <h1 className="text-app text-muted-foreground">学伴学习旅程</h1>
          <div className="flex items-center gap-xs">
            <SyncIndicator />
            <Badge
              variant={theme === "kids" ? "warning" : "outline"}
              data-testid="theme-badge"
            >
              {SKIN_LABEL[theme]}
            </Badge>
            <Button
              variant="ghost"
              size="sm"
              data-testid="theme-toggle"
              onClick={() => setTheme(theme === "kids" ? "focus" : "kids")}
            >
              {theme === "kids" ? "切换到专注模式" : "切换到儿童模式"}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              data-testid="mode-toggle"
              disabled={theme === "kids"}
              title={theme === "kids" ? "儿童模式不提供深色" : undefined}
              onClick={() => setMode(mode === "dark" ? "light" : "dark")}
            >
              {mode === "dark" ? "浅色" : "深色"}
            </Button>
            {user ? (
              <>
                <span className="text-app" data-testid="current-user">
                  {user.nickname ?? user.phone}
                </span>
                {user.is_k12 ? <Badge variant="warning">K12 保护</Badge> : null}
                <Button variant="ghost" size="sm" onClick={() => void logout()}>
                  退出登录
                </Button>
              </>
            ) : null}
          </div>
        </header>
        <main className="min-w-0 flex-1">
          {/* 儿童模式才计时：§8 约束 2 的「一年级每次 20 分钟强制休息」。
              GuardianGate 管「今天还能不能学」，RestBreakGate 管「这一次连着学太久要歇」 */}
          <RestBreakGate enabled={theme === "kids"}>
            <GuardianGate>
              <Outlet />
            </GuardianGate>
          </RestBreakGate>
        </main>
        <footer className="border-t border-border px-lg py-xs text-app-xs text-muted-foreground">
          守护型讲解 · 不直接给答案 ｜ 数据云端同步（实时同步）
        </footer>
      </div>
    </div>
  );
}
