import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import { ExplainerDock, ExplainerTrigger } from "./explainer-launcher";
import type { ExplainerState } from "./explainer-launcher";

function state(overrides: Partial<ExplainerState> = {}): ExplainerState {
  return {
    content: null,
    status: "idle",
    error: null,
    dismissed: false,
    open: vi.fn().mockResolvedValue(undefined),
    close: vi.fn(),
    feedback: vi.fn(),
    ...overrides,
  } as unknown as ExplainerState;
}

describe("ExplainerTrigger（场景 2/3 的入口）", () => {
  it("把知识点编码交给 onOpen", () => {
    const onOpen = vi.fn();
    render(
      <ExplainerTrigger knowledgeId="g1m-add-within-10" testId="t" onOpen={onOpen} />,
    );
    screen.getByTestId("t").click();
    expect(onOpen).toHaveBeenCalledWith("g1m-add-within-10");
  });

  it("没有知识点时禁用入口——按下去只能得到「不知道讲什么」的讲解", () => {
    render(<ExplainerTrigger knowledgeId="" testId="t" onOpen={vi.fn()} />);
    expect(screen.getByTestId("t")).toBeDisabled();
  });

  it("热区满足 kids 主题的 48px 要求", () => {
    render(<ExplainerTrigger knowledgeId="g1m-add-within-10" testId="t" onOpen={vi.fn()} />);
    expect(screen.getByTestId("t").className).toContain("min-h-[var(--tap-min)]");
  });

  it("朗读按钮是入口的兄弟节点，不能嵌在 button 里", () => {
    const { container } = render(
      <ExplainerTrigger knowledgeId="g1m-add-within-10" testId="t" speakable onOpen={vi.fn()} />,
    );
    // 非法嵌套：button 套 button 会让键盘与读屏都失灵
    expect(container.querySelector("button button")).toBeNull();
  });
});

describe("ExplainerDock（场景 2/3 的讲解面板）", () => {
  it("idle 时不渲染——入口由 Trigger 负责，避免同一页面两个「看讲解」按钮", () => {
    render(<ExplainerDock explainer={state()} knowledgeId="g1m-add-within-10" />);
    expect(screen.queryByTestId("explainer-dock")).toBeNull();
  });

  it("没有知识点时不渲染", () => {
    render(<ExplainerDock explainer={state({ status: "pending" })} knowledgeId="" />);
    expect(screen.queryByTestId("explainer-dock")).toBeNull();
  });

  it("生成中就把 pending 面板显示出来，绝不留空白", () => {
    render(<ExplainerDock explainer={state({ status: "pending" })} knowledgeId="g1m-add-within-10" />);
    expect(screen.getByTestId("explainer-pending")).toBeTruthy();
  });

  it("失败时可重试，重试重新打开同一知识点", () => {
    const open = vi.fn().mockResolvedValue(undefined);
    render(
      <ExplainerDock
        explainer={state({ status: "failed", error: "生成超时", open })}
        knowledgeId="g1m-add-within-10"
      />,
    );
    screen.getByTestId("explainer-retry").click();
    expect(open).toHaveBeenCalledWith("g1m-add-within-10");
  });

  it("支持自定义 testId（场景 3 用 kmap-explainer）", () => {
    render(
      <ExplainerDock
        explainer={state({ status: "pending" })}
        knowledgeId="g1m-add-within-10"
        testId="kmap-explainer"
      />,
    );
    expect(screen.getByTestId("kmap-explainer")).toBeTruthy();
  });
});
