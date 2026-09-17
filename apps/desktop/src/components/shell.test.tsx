import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { AppLayout } from "./app-layout";
import { EmptyBlock, ErrorBlock, LoadingBlock, SectionTitle } from "./state";
import { api } from "@/lib/api";
import { AuthProvider } from "@/lib/auth";
import { SyncProvider } from "@/lib/sync";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: { ...actual.api, me: vi.fn(), syncState: vi.fn(), logout: vi.fn() },
    setAccessToken: vi.fn(),
  };
});

const mockedApi = vi.mocked(api);

function renderLayout() {
  return render(
    <MemoryRouter initialEntries={["/plan"]}>
      <AuthProvider>
        <SyncProvider>
          <Routes>
            <Route element={<AppLayout />}>
              <Route path="/plan" element={<p>计划内容</p>} />
            </Route>
          </Routes>
        </SyncProvider>
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("三态组件（T9.3）", () => {
  it("加载态展示骨架与标签", () => {
    render(<LoadingBlock rows={2} label="加载计划" />);
    expect(screen.getByLabelText("加载计划")).toBeTruthy();
  });

  it("错误态展示信息并可重试", () => {
    const retry = vi.fn();
    render(<ErrorBlock message="加载失败" onRetry={retry} />);
    expect(screen.getByTestId("error-block")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "重试" }));
    expect(retry).toHaveBeenCalled();
  });

  it("空态展示标题与提示", () => {
    render(<EmptyBlock title="暂无数据" hint="先去完成任务" />);
    expect(screen.getByTestId("empty-block")).toBeTruthy();
    expect(screen.getByText("暂无数据")).toBeTruthy();
  });

  it("分区标题渲染", () => {
    render(<SectionTitle hint="说明">标题</SectionTitle>);
    expect(screen.getByRole("heading", { level: 2, name: "标题" })).toBeTruthy();
  });
});

describe("主布局（T5.1 / T9.3）", () => {
  it("渲染 9 项导航与主题切换，匿名时无退出按钮", async () => {
    mockedApi.syncState.mockRejectedValue(new Error("offline"));
    renderLayout();
    await waitFor(() => expect(screen.queryByText("计划内容")).toBeTruthy());

    const nav = screen.getByRole("navigation", { name: "功能导航" });
    for (const label of ["诊断", "规划", "讲解", "陪练", "练习", "批改", "复盘", "工具", "设置"]) {
      expect(nav.textContent).toContain(label);
    }
    expect(screen.getByTestId("theme-toggle")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "退出登录" })).toBeNull();
  });

  it("已登录展示用户与退出按钮", async () => {
    mockedApi.syncState.mockResolvedValue({
      version: "v1",
      summary: { completed_today: 0, total_today: 0, streak_days: 0, mistakes_active: 0 },
      server_time: "2026-09-16T00:00:00Z",
      channel: "sync:u1",
    });
    window.localStorage.setItem("xueban.desktop.access_token", "token");
    window.localStorage.setItem("xueban.desktop.refresh_token", "refresh");
    mockedApi.me.mockResolvedValue({
      id: "u1",
      phone: "13900000000",
      role: "student",
      nickname: "小明",
      is_k12: true,
      created_at: "2026-09-16T00:00:00Z",
    });
    renderLayout();
    await waitFor(() => expect(screen.getByTestId("current-user").textContent).toBe("小明"));
    expect(screen.getByText("K12 保护")).toBeTruthy();
    expect(screen.getByTestId("sync-indicator").textContent).toContain("今日 0/0");

    fireEvent.click(screen.getByTestId("theme-toggle"));
    expect(document.documentElement.classList.contains("dark")).toBe(true);
    window.localStorage.clear();
  });
});
