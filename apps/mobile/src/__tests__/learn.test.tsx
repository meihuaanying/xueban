import { fireEvent, render, screen, waitFor } from "@testing-library/react-native";

import { api as mockedApi } from "../lib/api";
import { DiagnosisScreen, LearnHomeScreen, PlanScreen } from "../screens/learn";

jest.mock("@react-navigation/native", () => ({
  ...jest.requireActual("@react-navigation/native"),
  useNavigation: () => ({ navigate: jest.fn() }),
}));

const today = {
  date: "2026-09-16",
  tasks: [
    { id: "t1", title: "复习：有理数加法", task_type: "review", status: "pending" },
    { id: "t2", title: "练习：绝对值", task_type: "practice", status: "pending" },
  ],
  completed_count: 0,
  total: 2,
  all_completed: false,
  streak_days: 0,
};

const mastery = {
  has_data: true,
  points: [{ knowledge_point_id: "k1", name: "有理数加法", mastery: 0.42, level: "red" }],
};

jest.mock("../lib/api", () => {
  const actual = jest.requireActual("../lib/api");
  return {
    ...actual,
    api: {
      today: jest.fn(),
      mastery: jest.fn(),
      completeTask: jest.fn(),
      startDiagnosis: jest.fn(),
      answerDiagnosis: jest.fn(),
      diagnosisReport: jest.fn(),
      path: jest.fn(),
    },
  };
});

const api = mockedApi as unknown as {
  today: jest.Mock;
  mastery: jest.Mock;
  completeTask: jest.Mock;
  startDiagnosis: jest.Mock;
  answerDiagnosis: jest.Mock;
  diagnosisReport: jest.Mock;
  path: jest.Mock;
};

describe("学习 Tab（T6.2）", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    api.today.mockResolvedValue(today);
    api.mastery.mockResolvedValue(mastery);
    api.path.mockResolvedValue({ has_path: false, phases: [] });
  });

  it("展示今日任务与学情画像", async () => {
    render(<LearnHomeScreen />);
    await waitFor(() => expect(screen.getByText("今日任务")).toBeTruthy());
    expect(screen.getAllByText("打卡")).toHaveLength(2);
    expect(screen.getByText(/有理数加法 · 42%/)).toBeTruthy();
  });

  it("打卡后连续天数更新", async () => {
    api.completeTask.mockResolvedValue({
      today: { ...today, completed_count: 1, streak_days: 1, tasks: today.tasks.map((task) => (task.id === "t1" ? { ...task, status: "done" } : task)) },
    });
    render(<LearnHomeScreen />);
    await waitFor(() => expect(screen.getAllByText("打卡")).toHaveLength(2));
    fireEvent.press(screen.getAllByText("打卡")[0]!);
    await waitFor(() => expect(screen.getByText(/连续 1 天/)).toBeTruthy());
    expect(screen.getByText("已完成")).toBeTruthy();
  });

  it("规划页展示路径阶段", async () => {
    api.path.mockResolvedValue({
      has_path: true,
      phases: [{ name: "base", title: "第一阶段 · 补前置", knowledge_points: [{ id: "k1", name: "有理数加法", mastery: 0.42 }] }],
    });
    render(<PlanScreen />);
    await waitFor(() => expect(screen.getByText("第一阶段 · 补前置")).toBeTruthy());
  });

  it("诊断作答后展示反馈", async () => {
    api.startDiagnosis.mockResolvedValue({
      exam_id: "exam-1",
      progress: { answered: 0, total: 20 },
      question: {
        id: "q1",
        stem: "计算 18 × 5 = ？",
        qtype: "choice",
        options: { A: "90", B: "88" },
        difficulty: 2,
        knowledge_points: ["k1"],
      },
    });
    api.answerDiagnosis.mockResolvedValue({
      is_correct: false,
      correct_answer: "A",
      progress: { answered: 1, total: 20 },
      finished: false,
      next_question: {
        id: "q2",
        stem: "计算 1 + 1 = ？",
        qtype: "choice",
        options: { A: "2", B: "3" },
        difficulty: 1,
        knowledge_points: ["k1"],
      },
    });
    render(<DiagnosisScreen />);
    fireEvent.press(screen.getByTestId("start-diagnosis"));
    await waitFor(() => expect(screen.getByText("计算 18 × 5 = ？")).toBeTruthy());
    fireEvent.press(screen.getByTestId("option-A"));
    fireEvent.press(screen.getByTestId("submit-answer"));
    await waitFor(() => expect(screen.getByText(/回答错误 · 正确答案 A/)).toBeTruthy());
  });
});
