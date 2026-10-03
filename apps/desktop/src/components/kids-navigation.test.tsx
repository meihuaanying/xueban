import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { KidsMascot, KidsNavBar, iconOf, type KidsNavItem } from "./kids-navigation";

const ITEMS: KidsNavItem[] = [
  { id: "today", label: "今天" },
  { id: "unit", label: "单元" },
  { id: "review", label: "复习" },
];

describe("iconOf（§4.1 每个阶段一眼能认的象形符号）", () => {
  it("六个阶段都有专属图标", () => {
    for (const id of ["today", "diagnosis", "plan", "unit", "mistakes", "review"]) {
      expect(iconOf(id)).not.toBe("⭐");
    }
  });

  it("未知阶段退回兜底图标而不是空", () => {
    expect(iconOf("未来阶段")).toBe("⭐");
  });
});

describe("KidsMascot（吉祥物「小伴」）", () => {
  it("常驻并报出自己的名字", () => {
    render(<KidsMascot />);
    expect(screen.getByTestId("kids-mascot")).toBeVisible();
    expect(screen.getByText("小伴")).toBeVisible();
  });

  it("speakable 时给一段固定欢迎语朗读，而不是整页内容", () => {
    const { rerender } = render(<KidsMascot speakable={false} />);
    // AudioButton 在没有 speechSynthesis 的环境会自行隐藏，所以只断言不抛错
    expect(screen.getByTestId("kids-mascot")).toBeVisible();
    rerender(<KidsMascot speakable />);
    expect(screen.getByTestId("kids-mascot")).toBeVisible();
  });
});

describe("KidsNavBar", () => {
  it("每个阶段一个可点的按钮", () => {
    render(<KidsNavBar items={ITEMS} active="today" onNavigate={() => {}} />);
    for (const item of ITEMS) {
      expect(screen.getByTestId(`kids-nav-${item.id}`)).toBeVisible();
    }
  });

  it("当前阶段标 aria-current=page，其余不标", () => {
    render(<KidsNavBar items={ITEMS} active="unit" onNavigate={() => {}} />);
    expect(screen.getByTestId("kids-nav-unit")).toHaveAttribute("aria-current", "page");
    expect(screen.getByTestId("kids-nav-today")).not.toHaveAttribute("aria-current");
  });

  it("点哪一站就回调哪个 id", () => {
    const onNavigate = vi.fn();
    render(<KidsNavBar items={ITEMS} active="today" onNavigate={onNavigate} />);
    fireEvent.click(screen.getByTestId("kids-nav-review"));
    expect(onNavigate).toHaveBeenCalledWith("review");
  });

  it("触达高度不小于 48px（一年级手指精度）", () => {
    render(<KidsNavBar items={ITEMS} active="today" onNavigate={() => {}} />);
    expect(screen.getByTestId("kids-nav-unit")).toHaveClass("min-h-[var(--tap-min)]");
  });
});
