/**
 * 学习域组件测试（§4.3）。
 * 覆盖：掌握度条、题卡、三层提示红���、连续打卡、成就徽标、TTS 朗读降级、Explainer 沙箱降级。
 */
import { act } from "react";
import { fireEvent, render, renderHook, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AchievementBadge } from "../learning/achievement-badge";
import { AudioButton } from "../learning/audio-button";
import { ExplainerFrame, useExplainerWatchdog } from "../learning/explainer-frame";
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

  // 填空题此前既无选项也无输入框，诊断与练习两条链会卡死（详见 REBUILD §6.2 题型清单）
  it("填空题给出输入框，输入过程不触发提交", () => {
    const onSelect = vi.fn();
    render(<QuestionCard stem="3 + 14 = ？" kind="fill" onSelect={onSelect} />);
    const input = screen.getByTestId("fill-input");
    fireEvent.change(input, { target: { value: "1" } });
    fireEvent.change(input, { target: { value: "17" } });
    expect(onSelect).not.toHaveBeenCalled();
    expect(input).toHaveValue("17");
  });

  it("填空题显式点提交才回传答案（并去空白）", () => {
    const onSelect = vi.fn();
    render(<QuestionCard stem="3 + 14 = ？" kind="fill" onSelect={onSelect} />);
    const submit = screen.getByTestId("fill-submit");
    expect(submit).toBeDisabled();
    fireEvent.change(screen.getByTestId("fill-input"), { target: { value: " 17 " } });
    fireEvent.click(submit);
    expect(onSelect).toHaveBeenCalledWith("17");
  });

  it("有选项时不渲染填空输入框", () => {
    render(<QuestionCard stem="x" options={[{ key: "A", label: "1" }]} />);
    expect(screen.queryByTestId("fill-input")).toBeNull();
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

  // 注意：超时路径不能在组件测试里断言。jsdom 会自动给 iframe 派发 load 事件，
  // 而 iframe onLoad 是「渲染完成」的解除武装信号，一旦挂上超时分支永远走不到。
  // 所以超时逻辑单独测 useExplainerWatchdog（见下方 describe），这里只测接线。
  it("默认把 iframe 的加载事件视为渲染完成", () => {
    render(<ExplainerFrame title="讲解" html={html} timeoutMs={30} />);
    fireEvent.load(screen.getByTitle("讲解"));
    // 不降级：保持 iframe（而不是降级视图里的说明文字）
    expect(screen.getByTitle("讲解").tagName).toBe("IFRAME");
    expect(screen.queryByText(/已切换为图文分步讲解/)).not.toBeInTheDocument();
  });

  it("健康状态下不渲染 fallback", () => {
    render(<ExplainerFrame title="讲解" html={html} fallback={<p>图文版在这里</p>} />);
    expect(screen.queryByText("图文版在这里")).not.toBeInTheDocument();
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

describe("useExplainerWatchdog（§5.4 渲染超时）", () => {
  const base = { armed: true, ready: false, degraded: false, timeoutMs: 60_000 };

  it("armed 且未就绪：超时后触发 onTimeout", () => {
    vi.useFakeTimers();
    const onTimeout = vi.fn();
    renderHook(() => useExplainerWatchdog({ ...base, onTimeout }));
    expect(onTimeout).not.toHaveBeenCalled();
    act(() => {
      vi.advanceTimersByTime(59_999);
    });
    expect(onTimeout).not.toHaveBeenCalled();
    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(onTimeout).toHaveBeenCalledTimes(1);
    vi.useRealTimers();
  });

  it("已就绪（ready）解除武装：跑满超时也不降级", () => {
    vi.useFakeTimers();
    const onTimeout = vi.fn();
    renderHook(() => useExplainerWatchdog({ ...base, ready: true, onTimeout }));
    act(() => {
      vi.advanceTimersByTime(120_000);
    });
    expect(onTimeout).not.toHaveBeenCalled();
    vi.useRealTimers();
  });

  it("未 armed（没有内容）不计时", () => {
    vi.useFakeTimers();
    const onTimeout = vi.fn();
    renderHook(() => useExplainerWatchdog({ ...base, armed: false, onTimeout }));
    act(() => {
      vi.advanceTimersByTime(120_000);
    });
    expect(onTimeout).not.toHaveBeenCalled();
    vi.useRealTimers();
  });

  it("已降级时不重复触发", () => {
    vi.useFakeTimers();
    const onTimeout = vi.fn();
    renderHook(() => useExplainerWatchdog({ ...base, degraded: true, onTimeout }));
    act(() => {
      vi.advanceTimersByTime(120_000);
    });
    expect(onTimeout).not.toHaveBeenCalled();
    vi.useRealTimers();
  });

  it("切换到就绪状态会清掉在跑的定时器", () => {
    vi.useFakeTimers();
    const onTimeout = vi.fn();
    const { rerender } = renderHook(
      (ready: boolean) => useExplainerWatchdog({ ...base, ready, onTimeout }),
      { initialProps: false },
    );
    act(() => {
      vi.advanceTimersByTime(30_000);
    });
    rerender(true);
    act(() => {
      vi.advanceTimersByTime(120_000);
    });
    expect(onTimeout).not.toHaveBeenCalled();
    vi.useRealTimers();
  });
});
