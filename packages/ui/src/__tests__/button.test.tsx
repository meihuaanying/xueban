import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Button } from "../button";

describe("Button", () => {
  it("渲染文本并默认使用主色变体", () => {
    render(<Button>开始学习</Button>);
    const button = screen.getByRole("button", { name: "开始学习" });
    expect(button.className).toContain("bg-primary");
  });

  it("支持 secondary 变体与点击事件", () => {
    const onClick = vi.fn();
    render(
      <Button variant="secondary" onClick={onClick}>
        查看计划
      </Button>,
    );
    const button = screen.getByRole("button", { name: "查看计划" });
    expect(button.className).toContain("bg-secondary");
    button.click();
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("默认 type 为 button，避免误触发表单提交", () => {
    render(<Button>提交</Button>);
    expect(screen.getByRole("button", { name: "提交" })).toHaveProperty("type", "button");
  });
});
