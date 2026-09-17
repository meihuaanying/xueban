/** 主布局：左侧功能导航 + 顶部用户栏（T5.1）。 */

import { useEffect } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { APP_NAME } from "@xueban/core";
import { Badge, Button, cn } from "@xueban/ui";

import { useAuth } from "@/lib/auth";
import { GuardianGate } from "@/components/guardian-gate";
import { SyncIndicator } from "@/lib/sync";

const NAV_ITEMS = [
  { to: "/diagnosis", label: "诊断", hint: "F-01/F-02" },
  { to: "/plan", label: "规划", hint: "F-06~F-10" },
  { to: "/tutor", label: "讲解", hint: "F-11~F-15" },
  { to: "/coach", label: "陪练", hint: "F-32~F-35" },
  { to: "/practice", label: "练习", hint: "F-17~F-19" },
  { to: "/grading", label: "批改", hint: "F-22~F-24" },
  { to: "/review", label: "复盘", hint: "F-27~F-30" },
  { to: "/tools", label: "工具", hint: "微课/拍照" },
  { to: "/settings", label: "设置", hint: "账号/订阅" },
];

export function AppLayout() {
  const { user, logout } = useAuth();

  useEffect(() => {
    if (window.localStorage.getItem("xueban.theme") === "dark") {
      document.documentElement.classList.add("dark");
    }
  }, []);

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <aside className="flex w-56 shrink-0 flex-col border-r border-border bg-card">
        <div className="flex items-center gap-2 px-5 py-5">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-sm font-bold text-primary-foreground">
            学
          </span>
          <div>
            <p className="text-sm font-bold">{APP_NAME}</p>
            <p className="text-xs text-muted-foreground">桌面端</p>
          </div>
        </div>
        <nav aria-label="功能导航" className="flex-1 px-3">
          <ul className="space-y-1">
            {NAV_ITEMS.map((item) => (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  className={({ isActive }) =>
                    cn(
                      "flex items-center justify-between rounded-lg px-3 py-2 text-sm transition-colors",
                      isActive
                        ? "bg-accent font-semibold text-accent-foreground"
                        : "text-muted-foreground hover:bg-muted hover:text-foreground",
                    )
                  }
                >
                  {({ isActive }) => (
                    <>
                      <span>{item.label}</span>
                      <span
                        className={cn(
                          "text-[10px]",
                          isActive ? "text-accent-foreground" : "text-muted-foreground",
                        )}
                      >
                        {item.hint}
                      </span>
                    </>
                  )}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
        <div className="space-y-2 border-t border-border px-5 py-4 text-xs text-muted-foreground">
          <p>守护型讲解 · 不直接给答案</p>
          <p>数据云端同步（M9 实时同步）</p>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between gap-4 border-b border-border bg-card px-6 py-3">
          <h1 className="text-sm font-semibold text-muted-foreground">学情闭环工作台</h1>
          <div className="flex items-center gap-3">
            <SyncIndicator />
            <Button
              variant="ghost"
              size="sm"
              data-testid="theme-toggle"
              onClick={() => {
                const root = document.documentElement;
                root.classList.toggle("dark");
                window.localStorage.setItem(
                  "xueban.theme",
                  root.classList.contains("dark") ? "dark" : "light",
                );
              }}
            >
              切换主题
            </Button>
            {user ? (
              <>
                <span className="text-sm" data-testid="current-user">
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
        <main className="min-w-0 flex-1 px-6 py-6">
          <GuardianGate>
            <Outlet />
          </GuardianGate>
        </main>
      </div>
    </div>
  );
}
