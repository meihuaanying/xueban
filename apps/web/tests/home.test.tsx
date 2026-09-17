import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import HomePage from "@/app/page";

describe("官网首页", () => {
  it("渲染价值主张与注册入口", () => {
    render(<HomePage />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("把每一道题");
    expect(screen.getByRole("link", { name: "免费开始学习" })).toHaveAttribute("href", "/register");
  });

  it("渲染六大核心能力卡片", () => {
    render(<HomePage />);
    expect(screen.getByText("自适应诊断")).toBeTruthy();
    expect(screen.getByText("BKT 学情画像")).toBeTruthy();
    expect(screen.getByText("规划引擎")).toBeTruthy();
    expect(screen.getByText("守护型讲解")).toBeTruthy();
    expect(screen.getByText("智能练习与错题本")).toBeTruthy();
    expect(screen.getByText("批改与无辅助测评")).toBeTruthy();
  });

  it("渲染五步学情闭环", () => {
    render(<HomePage />);
    for (const step of ["诊断", "规划", "讲解", "练习", "复盘"]) {
      expect(screen.getByText(step)).toBeTruthy();
    }
  });

  it("输出结构化数据（JSON-LD）", () => {
    const { container } = render(<HomePage />);
    const script = container.querySelector('script[type="application/ld+json"]');
    expect(script).not.toBeNull();
    const data = JSON.parse(script?.textContent ?? "{}") as { "@graph"?: unknown[] };
    expect(Array.isArray(data["@graph"])).toBe(true);
  });
});
