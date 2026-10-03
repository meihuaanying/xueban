/**
 * 讲解卡 UI 测试（P1 / §5.4）。
 *
 * 四态各有明确出口：待生成 / 失败可重试 / 图文降级 / 就绪看沙箱。
 * 重点是「任何状态都不白屏」——§5.4 的硬要求。
 */
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { ExplainerContent } from "../../lib/api";
import { ExplainerCard } from "./explainer-blocks";

function content(overrides: Partial<ExplainerContent> = {}): ExplainerContent {
  return {
    id: "c1",
    knowledge_id: "g1m-add-within-10",
    stage: "grade1_2",
    title: "10 以内加法",
    status: "ready",
    html: "<p>讲解</p>",
    degraded: false,
    byte_size: 1000,
    script: {},
    render_timeout_seconds: 60,
    ...overrides,
  };
}

const noop = (): void => {};

describe("ExplainerCard 四态", () => {
  it("空闲态给出「看讲解」入口（§5.1 自动建议）", () => {
    render(
      <ExplainerCard
        status="idle"
        content={null}
        error={null}
        speakable={false}
        busy={false}
        onOpen={noop}
        onRetry={noop}
        onClose={noop}
        onFeedback={noop}
      />,
    );
    expect(screen.getByTestId("explainer-idle")).toBeTruthy();
    expect(screen.getByTestId("explainer-open")).toBeTruthy();
  });

  it("生成中显示进度，不出现空白区", () => {
    render(
      <ExplainerCard
        status="pending"
        content={null}
        error={null}
        speakable={false}
        busy={false}
        onOpen={noop}
        onRetry={noop}
        onClose={noop}
        onFeedback={noop}
      />,
    );
    expect(screen.getByTestId("explainer-pending")).toBeTruthy();
    expect(screen.getByText(/正在给你准备讲解/)).toBeTruthy();
  });

  it("失败态给出错误原因与重试入口", () => {
    const onRetry = vi.fn();
    render(
      <ExplainerCard
        status="failed"
        content={null}
        error="今天的讲解次数用完啦"
        speakable={false}
        busy={false}
        onOpen={noop}
        onRetry={onRetry}
        onClose={noop}
        onFeedback={noop}
      />,
    );
    expect(screen.getByTestId("explainer-failed")).toBeTruthy();
    expect(screen.getByText("今天的讲解次数用完啦")).toBeTruthy();
    fireEvent.click(screen.getByTestId("explainer-retry"));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("就绪态把消毒后的 HTML 交给沙箱内嵌框", () => {
    render(
      <ExplainerCard
        status="ready"
        content={content()}
        error={null}
        speakable={false}
        busy={false}
        onOpen={noop}
        onRetry={noop}
        onClose={noop}
        onFeedback={noop}
      />,
    );
    const frame = screen.getByTitle("10 以内加法");
    expect(frame.tagName).toBe("IFRAME");
    expect(frame.getAttribute("sandbox")).toBe("allow-scripts");
  });

  it("降级产物走图文分步，而不是渲染交互页", () => {
    render(
      <ExplainerCard
        status="ready"
        content={content({
          degraded: true,
          script: {
            title: "凑十法",
            acts: [
              { name: "拆解", narration: "9 凑成 10" },
              { name: "收束", narration: "9 加 1 得 10" },
            ],
          },
        })}
        error={null}
        speakable={false}
        busy={false}
        onOpen={noop}
        onRetry={noop}
        onClose={noop}
        onFeedback={noop}
      />,
    );
    expect(screen.queryByRole("iframe")).toBeNull();
    const steps = screen.getByTestId("explainer-steps");
    expect(steps.textContent).toContain("9 凑成 10");
    expect(steps.textContent).toContain("9 加 1 得 10");
  });

  it("脚本为空时仍给一句人话，而不是空白", () => {
    render(
      <ExplainerCard
        status="ready"
        content={content({ degraded: true, script: {} })}
        error={null}
        speakable={false}
        busy={false}
        onOpen={noop}
        onRetry={noop}
        onClose={noop}
        onFeedback={noop}
      />,
    );
    expect(screen.getByTestId("explainer-steps")).toBeTruthy();
    expect(screen.getByText(/这段讲解暂时放不出来/)).toBeTruthy();
  });

  it("沙箱降级也算「还是不懂」回流画像", () => {
    const onFeedback = vi.fn();
    render(
      <ExplainerCard
        status="ready"
        content={content()}
        error={null}
        speakable={false}
        busy={false}
        onOpen={noop}
        onRetry={noop}
        onClose={noop}
        onFeedback={onFeedback}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "看懂了" }));
    expect(onFeedback).toHaveBeenCalledWith(true);
    fireEvent.click(screen.getByRole("button", { name: "还是不懂" }));
    expect(onFeedback).toHaveBeenCalledWith(false);
  });

  it("关闭按钮会收起讲解", () => {
    const onClose = vi.fn();
    render(
      <ExplainerCard
        status="ready"
        content={content()}
        error={null}
        speakable={false}
        busy={false}
        onOpen={noop}
        onRetry={noop}
        onClose={onClose}
        onFeedback={noop}
      />,
    );
    fireEvent.click(screen.getByTestId("explainer-close"));
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
