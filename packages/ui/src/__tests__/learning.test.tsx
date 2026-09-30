/**
 * 学习域组件测试（§4.3）。
 * 覆盖：掌握度条、题卡、三层提示红���、连续打卡、成就徽标、TTS 朗读降级、Explainer 沙箱降级。
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AchievementBadge } from "../learning/achievement-badge";
import { AudioButton } from "../learning/audio-button";
import { ExplainerFrame } from "../learning/explainer-frame";
import { HintStack } from "../learning/hint-stack";
import { KnowledgeMap } from "../learning/knowledge-map";
import { MasteryBar, toneForValue } from "../learning/mastery-bar";
import { QuestionCard } from "../learning/question-card";
import { StreakFlame } from "../learning/streak-flame";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("MasteryBar", () => {
  it("按 0~1 输出可访问的百分比", () => {
    render(<MasteryBar value={0.42} label="10 以内加减" />);
    const bar = screen.getByRole("progressbar", { name: "10 以内加减" });
    expect(bar).toHaveAttribute("aria-valuenow", "42");
  });

  it("越界值被裁剪到 0~1", () => {
    const { rerender } = render(<MasteryBar value={5} label="x" />);
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "100");
    rerender(<MasteryBar value={-3} label="x" />);
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "0");
  });

  it("toneForValue 随掌握度升档", () => {
    expect(toneForValue(0)).toBe("var(--mastery-1)");
    expect(toneForValue(0.5)).toBe("var(--mastery-3)");
    expect(toneForValue(1)).toBe("var(--mastery-5)");
  });
});

describe("KnowledgeMap", () => {
  const nodes = [
    { id: "n1", label: "数", level: 5 as const },
    { id: "n2", label: "形", level: 3 as const },
    { id: "n3", label: "钟", level: 1 as const },
  ];

  it("渲染标题与全部节点，并用 sr-only 文案标注掌握度", () => {
    render(<KnowledgeMap title="数学" nodes={nodes} />);
    expect(screen.getByRole("region", { name: "数学" })).toBeInTheDocument();
    expect(screen.getByText("数，掌握度精通")).toBeInTheDocument();
    expect(screen.getByText("钟，掌握度未接触")).toBeInTheDocument();
  });

  it("locked 节点降透明度", () => {
    const { container } = render(
      <KnowledgeMap nodes={[{ id: "x", label: "字", level: 2, locked: true }]} />,
    );
    expect(container.querySelector(".opacity-60")).not.toBeNull();
  });
});

describe("QuestionCard", () => {
  it("选项点击回传 key", () => {
    const onSelect = vi.fn();
    render(
      <QuestionCard stem="3 + 14 = ？" options={[{ key: "A", label: "15" }, { key: "B", label: "16" }]} onSelect={onSelect} />,
    );
    fireEvent.click(screen.getByText("16"));
    expect(onSelect).toHaveBeenCalledWith("B");
  });

  it("已选项标记 aria-pressed", () => {
    render(
      <QuestionCard
        stem="选出正确的字"
        value="A"
        options={[
          { key: "A", label: "天" },
          { key: "B", label: "地" },
        ]}
      />,
    );
    expect(screen.getByRole("button", { name: /A\./ })).toHaveAttribute("aria-pressed", "true");
  });

  it("disabled 时选项不可点", () => {
    render(<QuestionCard stem="x" options={[{ key: "A", label: "1" }]} disabled />);
    expect(screen.getByRole("button", { name: /A\./ })).toBeDisabled();
  });

  it("拼音与公式都能渲染", () => {
    const { container } = render(
      <QuestionCard stem="看图选字" pinyin="kàn tú" formula="1+1=2" />,
    );
    expect(screen.getByLabelText("拼音 kàn tú")).toBeInTheDocument();
    expect(container.querySelector(".katex")).not.toBeNull();
  });
});

describe("HintStack（守护型红线）", () => {
  const hints = [
    { level: 1 as const, text: "先看看图" },
    { level: 2 as const, text: "想想加法" },
    { level: 3 as const, text: "伸出手指数一数" },
  ];

  it("默认只解锁第一层，并给出去下层的按钮", () => {
    render(<HintStack hints={hints} onReveal={() => {}} />);
    expect(screen.getByText("先看看图")).toBeInTheDocument();
    expect(screen.queryByText("想想加法")).toBeNull();
    expect(screen.getByRole("button", { name: "给我第 2 层提示" })).toBeInTheDocument();
  });

  it("解锁到第三层后仍声明不给答案，并展示出口", () => {
    render(<HintStack hints={hints} revealed={3} fallback={<button type="button">看动画讲解</button>} />);
    expect(screen.getByText("伸出手指数一数")).toBeInTheDocument();
    expect(screen.getByText(/仍不提供完整答案/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "看动画讲解" })).toBeInTheDocument();
  });

  it("点击解锁按钮回调对应层级", () => {
    const onReveal = vi.fn();
    render(<HintStack hints={hints} onReveal={onReveal} />);
    fireEvent.click(screen.getByRole("button", { name: "给我第 2 层提示" }));
    expect(onReveal).toHaveBeenCalledWith(2);
  });
});

describe("StreakFlame", () => {
  it("未达目标时提示今天未完成", () => {
    render(<StreakFlame days={3} goal={7} />);
    expect(screen.getByRole("status")).toHaveAttribute(
      "aria-label",
      expect.stringContaining("今天还没完成"),
    );
  });

  it("达标后显示目标达成", () => {
    render(<StreakFlame days={7} goal={7} doneToday />);
    expect(screen.getByText("目标达成")).toBeInTheDocument();
  });
});

describe("AchievementBadge", () => {
  it("未解锁与已解锁语义不同", () => {
    const { rerender } = render(<AchievementBadge achievement={{ id: "streak", label: "七日坚持" }} />);
    expect(screen.getByRole("img")).toHaveAttribute("aria-label", "七日坚持（未解锁）");
    rerender(<AchievementBadge achievement={{ id: "streak", label: "七日坚持", unlocked: true }} />);
    expect(screen.getByRole("img")).toHaveAttribute("aria-label", "七日坚持（已解锁）");
  });
});

describe("AudioButton", () => {
  it("无 speechSynthesis 时不渲染（降级不报错）", () => {
    const original = window.speechSynthesis;
    // @ts-expect-error 模拟不支持的环境
    delete window.speechSynthesis;
    const { container } = render(<AudioButton text="读我" />);
    expect(container.firstChild).toBeNull();
    window.speechSynthesis = original;
  });

  it("点击时用 Web Speech API 朗读传入文本", () => {
    const speak = vi.fn();
    const utterance = vi.fn(function FakeUtterance(this: { text: string; lang: string; rate: number }, text: string) {
      this.text = text;
      this.lang = "";
      this.rate = 1;
    });
    Object.defineProperty(window, "speechSynthesis", {
      configurable: true,
      value: { speak, cancel: vi.fn() },
    });
    Object.defineProperty(window, "SpeechSynthesisUtterance", { configurable: true, value: utterance });
    render(<AudioButton text="看图选字" />);
    fireEvent.click(screen.getByRole("button", { name: "朗读" }));
    expect(speak).toHaveBeenCalledTimes(1);
    expect(speak.mock.calls[0]?.[0]).toMatchObject({ text: "看图选字", lang: "zh-CN" });
  });
});

describe("ExplainerFrame（沙箱安全）", () => {
  const html = "<p>讲解</p>";

  it("HTML 走 sandbox iframe，且不放行 same-origin", () => {
    render(<ExplainerFrame title="10 以内加法" html={html} />);
    const frame = screen.getByTitle("10 以内加法");
    expect(frame.tagName).toBe("IFRAME");
    expect(frame.getAttribute("sandbox")).toBe("allow-scripts");
    expect(frame.getAttribute("sandbox")).not.toContain("allow-same-origin");
    expect(frame.getAttribute("referrerpolicy")).toBe("no-referrer");
  });

  it("超时后降级为图文讲解并回调 onFallback", async () => {
    const onFallback = vi.fn();
    render(<ExplainerFrame title="讲解" html={html} timeoutMs={30} onFallback={onFallback} />);
    // 真实等待超过 timeoutMs，验证 useEffect 定时器触发降级
    await waitFor(() => {
      expect(screen.getByText(/已切换为图文分步讲解/)).toBeInTheDocument();
    }, { timeout: 1000 });
    expect(onFallback).toHaveBeenCalledWith("timeout");
  });

  it("视频模式用 video 元素", () => {
    const { container } = render(<ExplainerFrame title="讲解" videoUrl="https://cdn/x.mp4" />);
    expect(container.querySelector("video")).not.toBeNull();
  });

  it("无内容时提示生成中，不白屏", () => {
    render(<ExplainerFrame title="讲解" />);
    expect(screen.getByText(/讲解内容生成中/)).toBeInTheDocument();
  });

  it("反馈按钮回传理解状态", () => {
    const onFeedback = vi.fn();
    render(<ExplainerFrame title="讲解" html={html} onFeedback={onFeedback} />);
    fireEvent.click(screen.getByRole("button", { name: "看懂了" }));
    expect(onFeedback).toHaveBeenCalledWith(true);
  });
});
