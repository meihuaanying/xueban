import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Accordion, Breadcrumb, Pagination, Tabs } from "../navigation";
import { Dialog, Tooltip } from "../overlay";

describe("Tabs / Accordion", () => {
  it("标签页可切换", () => {
    render(
      <Tabs
        tabs={[
          { key: "a", label: "第一页", content: <p>内容甲</p> },
          { key: "b", label: "第二页", content: <p>内容乙</p> },
        ]}
      />,
    );
    expect(screen.getByText("内容甲")).toBeTruthy();
    fireEvent.click(screen.getByRole("tab", { name: "第二页" }));
    expect(screen.getByText("内容乙")).toBeTruthy();
    expect(screen.getByRole("tab", { name: "第二页" })).toHaveAttribute("aria-selected", "true");
  });

  it("标签页切换触发 onChange 回调", () => {
    const onChange = vi.fn();
    render(
      <Tabs
        onChange={onChange}
        tabs={[
          { key: "a", label: "登录", content: <p>甲</p> },
          { key: "b", label: "注册", content: <p>乙</p> },
        ]}
      />,
    );
    fireEvent.click(screen.getByRole("tab", { name: "注册" }));
    expect(onChange).toHaveBeenCalledWith("b");
  });

  it("折叠面板渲染条目", () => {
    render(
      <Accordion
        items={[
          { key: "1", title: "什么是学情闭环？", content: <p>诊断到复盘的五步循环</p> },
          { key: "2", title: "如何计费？", content: <p>订阅制</p> },
        ]}
      />,
    );
    expect(screen.getByText("什么是学情闭环？")).toBeTruthy();
    expect(screen.getByText("订阅制")).toBeTruthy();
  });
});

describe("Breadcrumb / Pagination", () => {
  it("面包屑标记当前页", () => {
    render(
      <Breadcrumb items={[{ label: "首页", href: "/" }, { label: "帮助中心" }]} />,
    );
    expect(screen.getByText("帮助中心")).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "首页" })).toHaveAttribute("href", "/");
  });

  it("分页可翻页", () => {
    const onChange = vi.fn();
    render(<Pagination page={2} pageCount={3} onChange={onChange} />);
    fireEvent.click(screen.getByRole("button", { name: "下一页" }));
    expect(onChange).toHaveBeenCalledWith(3);
    fireEvent.click(screen.getByRole("button", { name: "1" }));
    expect(onChange).toHaveBeenCalledWith(1);
  });
});

describe("Dialog / Tooltip", () => {
  it("对话框可打开并关闭", () => {
    const onClose = vi.fn();
    const { rerender } = render(
      <Dialog open title="确认开通" onClose={onClose}>
        开通后立即可用
      </Dialog>,
    );
    expect(screen.getByRole("dialog")).toHaveTextContent("开通后立即可用");
    fireEvent.click(screen.getByLabelText("关闭"));
    expect(onClose).toHaveBeenCalledTimes(1);
    rerender(<Dialog open={false} title="确认开通" />);
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("悬浮提示带 title 兜底", () => {
    render(<Tooltip content="掌握度=正确率加权">掌握度</Tooltip>);
    expect(screen.getByRole("tooltip")).toHaveTextContent("掌握度=正确率加权");
  });
});
