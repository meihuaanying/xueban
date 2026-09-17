import { fireEvent, render, screen, waitFor } from "@testing-library/react-native";

import { api as mockedApi } from "../lib/api";
import { PracticeScreen } from "../screens/practice";

jest.mock("../lib/api", () => {
  const actual = jest.requireActual("../lib/api");
  return {
    ...actual,
    api: {
      mistakes: jest.fn(),
      generatePractice: jest.fn(),
      answerPractice: jest.fn(),
      repractice: jest.fn(),
    },
  };
});

const api = mockedApi as unknown as {
  mistakes: jest.Mock;
  generatePractice: jest.Mock;
  answerPractice: jest.Mock;
  repractice: jest.Mock;
};

const questions = [
  {
    id: "q1",
    stem: "计算 18 × 5 = ？",
    qtype: "choice",
    options: { A: "90", B: "88" },
    difficulty: 2,
    reason: "薄弱知识点优先",
  },
];

describe("练习 Tab（T6.4）", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    api.mistakes.mockResolvedValue({ active_count: 0, entries: [] });
  });

  it("答错后提示加入错题本并刷新错题列表", async () => {
    api.generatePractice.mockResolvedValue({ questions, weak_ratio: 0.8 });
    api.answerPractice.mockResolvedValue({
      is_correct: false,
      correct_answer: "A",
      mistake_collected: true,
      mistake_removed: false,
      explanation: "乘法口诀。",
    });
    render(<PracticeScreen />);
    fireEvent.press(screen.getByTestId("generate-practice"));
    await waitFor(() => expect(screen.getByText("计算 18 × 5 = ？")).toBeTruthy());
    fireEvent.press(screen.getByTestId("option-B"));
    fireEvent.press(screen.getByTestId("submit-practice"));
    await waitFor(() => expect(screen.getByText(/已加入错题本/)).toBeTruthy());
    expect(api.mistakes).toHaveBeenCalled();
  });

  it("重练答对后从错题本移除", async () => {
    api.mistakes.mockResolvedValue({
      active_count: 1,
      entries: [{ id: "m1", question: { id: "q1", stem: "计算 18 × 5 = ？" }, error_reason_label: "概念不清", state: "active", review_count: 1 }],
    });
    api.repractice.mockResolvedValue({
      questions: [{ id: "q1", stem: "计算 18 × 5 = ？", options: { A: "90", B: "88" } }],
    });
    api.answerPractice.mockResolvedValue({
      is_correct: true,
      correct_answer: "A",
      mistake_collected: false,
      mistake_removed: true,
      explanation: null,
    });
    render(<PracticeScreen />);
    await waitFor(() => expect(screen.getByText(/错题本（1）/)).toBeTruthy());
    fireEvent.press(screen.getByText("错题重练"));
    await waitFor(() => expect(screen.getByTestId("repractice-panel")).toBeTruthy());
    fireEvent.press(screen.getByTestId("repractice-A"));
    await waitFor(() =>
      expect(api.answerPractice).toHaveBeenCalledWith(
        expect.objectContaining({ question_id: "q1", source: "repractice" }),
      ),
    );
  });
});
