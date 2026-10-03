import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { PracticeQuestion } from "@/lib/api";

import { FeedbackCard, QuestionSection } from "./unit-blocks";

/**
 * 练习题的前端视图。标准答案后端不会下发（作答后才有反馈），
 * 所以这里只在造用例时填 `answer`，用来标记「这道题本该选什么」。
 */
type TestQuestion = PracticeQuestion & { answer?: string };

function question(overrides: Partial<TestQuestion> = {}): TestQuestion {
  return {
    id: "q1",
    stem: "1 + 1 等于几？",
    qtype: "choice",
    options: { A: "2", B: "3" },
    difficulty: 1,
    reason: "",
    knowledge_points: ["g1m-add-within-10"],
    ...overrides,
  };
}

describe("FeedbackCard 正反馈动效（§4.1）", () => {
  it("答对时撒花", () => {
    render(
      <FeedbackCard
        isCorrect
        explanation="对啦"
        mistakeCollected={false}
        onOpenTutor={() => {}}
        onNext={() => {}}
      />,
    );
    expect(screen.getByTestId("unit-celebrate")).toBeDefined();
    expect(screen.getByText("回答正确")).toBeDefined();
  });

  it("答错时不撒花，但错题本标记仍在", () => {
    render(
      <FeedbackCard
        isCorrect={false}
        explanation="再想想"
        mistakeCollected
        onOpenTutor={() => {}}
        onNext={() => {}}
      />,
    );
    expect(screen.queryByTestId("unit-celebrate")).toBeNull();
    expect(screen.getByText("已加入错题本")).toBeDefined();
  });

  it("两个出口都可点", () => {
    const onNext = vi.fn();
    const onOpenTutor = vi.fn();
    render(
      <FeedbackCard
        isCorrect
        explanation="好"
        mistakeCollected={false}
        onOpenTutor={onOpenTutor}
        onNext={onNext}
      />,
    );
    fireEvent.click(screen.getByTestId("unit-open-tutor"));
    fireEvent.click(screen.getByTestId("unit-next"));
    expect(onOpenTutor).toHaveBeenCalledTimes(1);
    expect(onNext).toHaveBeenCalledTimes(1);
  });
});

describe("QuestionSection 按题型派发（§6.1）", () => {
  it("选择题走选项列表", () => {
    render(
      <QuestionSection
        question={question()}
        index={0}
        total={3}
        busy={false}
        speakable={false}
        onAnswer={() => {}}
      />,
    );
    expect(screen.getByTestId("unit-question")).toBeDefined();
    expect(screen.getByText("2")).toBeDefined();
  });

  it("判断题没有 options 时自动补两个大按钮", () => {
    render(
      <QuestionSection
        question={question({ qtype: "judge", options: null, answer: "对" })}
        index={0}
        total={1}
        busy={false}
        speakable={false}
        onAnswer={() => {}}
      />,
    );
    // 用完整文案定位，避免题干里也含「对/错」时匹配到多个元素
    expect(screen.getByText("√ 对")).toBeDefined();
    expect(screen.getByText("× 错")).toBeDefined();
  });

  it("连线题渲染配对台并把配对结果序列化成 JSON 提交", () => {
    const onAnswer = vi.fn();
    render(
      <QuestionSection
        question={question({
          qtype: "match",
          stem: "把物品和形状连起来：铅笔盒、魔方。",
          options: { A: "长方形", B: "正方形" },
          answer: "{}",
        })}
        index={0}
        total={1}
        busy={false}
        speakable={false}
        onAnswer={onAnswer}
      />,
    );
    expect(screen.getByTestId("link-matcher")).toBeDefined();
    fireEvent.click(screen.getByTestId("link-left-铅笔盒"));
    fireEvent.click(screen.getByTestId("link-right-长方形"));
    fireEvent.click(screen.getByTestId("link-left-魔方"));
    fireEvent.click(screen.getByTestId("link-right-正方形"));
    expect(onAnswer).toHaveBeenCalledTimes(1);
    const submitted = onAnswer.mock.calls[0]?.[0];
    expect(typeof submitted).toBe("string");
    expect(JSON.parse(String(submitted))).toEqual({
      铅笔盒: "长方形",
      魔方: "正方形",
    });
  });

  it("题干取不到左项的连线题降级成选择题，而不是给一个空的配对台", () => {
    render(
      <QuestionSection
        question={question({ qtype: "match", stem: "看图连线。", options: { A: "圆" } })}
        index={0}
        total={1}
        busy={false}
        speakable={false}
        onAnswer={() => {}}
      />,
    );
    expect(screen.queryByTestId("link-matcher")).toBeNull();
    expect(screen.getByText("圆")).toBeDefined();
  });

  it("识字题渲染大字卡且不显示 ABCD 序号", () => {
    render(
      <QuestionSection
        question={question({
          qtype: "pick_hanzi",
          stem: "选出「田」字",
          options: { A: "田", B: "由" },
          answer: "田",
        })}
        index={0}
        total={1}
        busy={false}
        speakable={false}
        onAnswer={() => {}}
      />,
    );
    expect(screen.getByText("田")).toBeDefined();
    expect(screen.getByText("由")).toBeDefined();
    expect(screen.queryByText("A.")).toBeNull();
  });

  it("答题进度按 1 起算", () => {
    render(
      <QuestionSection
        question={question()}
        index={1}
        total={5}
        busy={false}
        speakable={false}
        onAnswer={() => {}}
      />,
    );
    expect(screen.getByText(/第 2 \/ 5 题/)).toBeDefined();
  });
});
