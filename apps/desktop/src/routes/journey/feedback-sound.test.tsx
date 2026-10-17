/**
 * 答题音效接线测试（§4.1「答对撒花/音效」）。
 *
 * 单独一个文件而不是塞进 `unit-blocks.test.tsx`：这里要对 `@xueban/ui` 的
 * `playCorrectChime` 做**部分 mock**，而那个文件里的用例不应该被这层 mock 影响。
 *
 * 要钉死的是接线语义，不是音色：
 * - 答对 + 开关开 → 响一次；
 * - 答对但开关关 → 不响（设置页的开关必须真的管用）；
 * - 答错 → 不响（做错时的引导在文字里，不用声音强调失败）；
 * - 换一道题再答对 → 再响一次（`isCorrect` 从 true 到 true 不变，只靠它当依赖会漏）。
 */
import { render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const playCorrectChime = vi.fn();

vi.mock("@xueban/ui", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@xueban/ui")>();
  return { ...actual, playCorrectChime };
});

const { FeedbackCard } = await import("./unit-blocks");

function renderFeedback(overrides: {
  isCorrect: boolean;
  sound?: boolean;
  answerKey?: number;
}) {
  return render(
    <FeedbackCard
      isCorrect={overrides.isCorrect}
      explanation="解析"
      mistakeCollected={false}
      sound={overrides.sound}
      answerKey={overrides.answerKey}
      onOpenTutor={() => {}}
      onNext={() => {}}
    />,
  );
}

describe("FeedbackCard 答题音效", () => {
  it("答对且开关打开时响一次", () => {
    playCorrectChime.mockClear();
    renderFeedback({ isCorrect: true, sound: true, answerKey: 0 });
    expect(playCorrectChime).toHaveBeenCalledTimes(1);
  });

  it("答对但开关关掉时不响", () => {
    playCorrectChime.mockClear();
    renderFeedback({ isCorrect: true, sound: false, answerKey: 0 });
    expect(playCorrectChime).not.toHaveBeenCalled();
  });

  it("答错时不响——不用声音强调失败", () => {
    playCorrectChime.mockClear();
    renderFeedback({ isCorrect: false, sound: true, answerKey: 0 });
    expect(playCorrectChime).not.toHaveBeenCalled();
  });

  it("换一道题再答对会再响一次", () => {
    playCorrectChime.mockClear();
    const first = renderFeedback({ isCorrect: true, sound: true, answerKey: 0 });
    expect(playCorrectChime).toHaveBeenCalledTimes(1);

    first.rerender(
      <FeedbackCard
        isCorrect
        explanation="解析"
        mistakeCollected={false}
        sound
        answerKey={1}
        onOpenTutor={() => {}}
        onNext={() => {}}
      />,
    );
    expect(playCorrectChime).toHaveBeenCalledTimes(2);
  });
});
