import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { JsonLd } from "@/components/json-ld";
import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";
import { ThemeToggle } from "@/components/theme-toggle";

function mockMatchMedia(matches: boolean) {
  vi.stubGlobal(
    "matchMedia",
    vi.fn().mockReturnValue({
      matches,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }),
  );
}

beforeEach(() => {
  window.localStorage.clear();
  document.documentElement.classList.remove("dark");
  mockMatchMedia(false);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("主题切换（T9.3）", () => {
  it("点击切换暗色并持久化", () => {
    render(<ThemeToggle />);
    const toggle = screen.getByTestId("theme-toggle");
    fireEvent.click(toggle);
    expect(document.documentElement.classList.contains("dark")).toBe(true);
    expect(window.localStorage.getItem("xueban.theme")).toBe("dark");

    fireEvent.click(toggle);
    expect(document.documentElement.classList.contains("dark")).toBe(false);
    expect(window.localStorage.getItem("xueban.theme")).toBe("light");
  });

  it("优先读取 localStorage，其次跟随系统", () => {
    window.localStorage.setItem("xueban.theme", "dark");
    render(<ThemeToggle />);
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });

  it("无本地偏好时跟随系统暗色", () => {
    mockMatchMedia(true);
    render(<ThemeToggle />);
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });
});

describe("官网页眉/页脚/结构化数据", () => {
  it("页眉包含主导航与转化入口", () => {
    render(<SiteHeader />);
    expect(screen.getByRole("navigation", { name: "主导航" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "定价" })).toHaveAttribute("href", "/pricing");
    expect(screen.getByRole("link", { name: "免费注册" })).toHaveAttribute("href", "/register");
  });

  it("页脚包含合规与资源分组", () => {
    render(<SiteFooter />);
    expect(screen.getByRole("navigation", { name: "法律与保护" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "隐私政策" })).toBeTruthy();
    expect(screen.getByText(/保留所有权利/)).toBeTruthy();
  });

  it("JsonLd 输出结构化脚本", () => {
    const { container } = render(<JsonLd data={{ "@type": "Organization", name: "学伴" }} />);
    const script = container.querySelector('script[type="application/ld+json"]');
    expect(script?.textContent).toContain("Organization");
  });
});
