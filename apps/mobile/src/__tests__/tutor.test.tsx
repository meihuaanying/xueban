import { fireEvent, render, screen, waitFor } from "@testing-library/react-native";

import { api as mockedApi, streamTutorHint as mockedStream } from "../lib/api";
import { TutorScreen } from "../screens/tutor";

jest.mock("../lib/api", () => {
  const actual = jest.requireActual("../lib/api");
  return {
    ...actual,
    api: {
      generatePractice: jest.fn(),
      createTutorSession: jest.fn(),
      tutorHint: jest.fn(),
    },
    streamTutorHint: jest.fn(),
  };
});

const api = mockedApi as unknown as {
  generatePractice: jest.Mock;
  createTutorSession: jest.Mock;
  tutorHint: jest.Mock;
};
const streamTutorHint = mockedStream as unknown as jest.Mock;

describe("讲解 Tab（T6.3）", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    api.generatePractice.mockResolvedValue({
      questions: [{ id: "q1", stem: "解方程 x + 1 = 2", qtype: "fill", options: null, difficulty: 1, reason: "" }],
      weak_ratio: 0.8,
    });
    api.createTutorSession.mockResolvedValue({
      session_id: "s1",
      question: { id: "q1", stem: "解方程 x + 1 = 2", difficulty: 1, knowledge_points: ["k1"] },
      hint_level: 0,
      hint_level_name: "未开始",
    });
  });

  it("三层提示逐层解锁，流式输出渲染公式", async () => {
    streamTutorHint.mockImplementation(
      async (_sessionId: string, level: number, handlers: { onStart?: (p: { level: number; level_name: string }) => void; onDelta?: (text: string) => void; onDone?: (p: { level: number; level_name: string; content: string }) => void }) => {
        handlers.onStart?.({ level, level_name: "思路提示" });
        handlers.onDelta?.("先观察 $x + 1 = 2$ ");
        handlers.onDone?.({ level, level_name: "思路提示", content: "先观察 $x + 1 = 2$ 的移项方向。" });
      },
    );
    render(<TutorScreen />);
    fireEvent.press(screen.getByTestId("pick-question"));
    await waitFor(() => expect(screen.getByTestId("tutor-stem")).toBeTruthy());
    fireEvent.press(screen.getByTestId("start-tutor"));
    await waitFor(() => expect(screen.getByText(/当前层级：未开始/)).toBeTruthy());

    // 只能先解锁第一层
    expect(screen.getByTestId("hint-2").props.accessibilityState?.disabled).toBe(true);
    fireEvent.press(screen.getByTestId("hint-1"));
    await waitFor(() => expect(screen.getByText(/移项方向/)).toBeTruthy());
    expect(streamTutorHint).toHaveBeenCalledWith("s1", 1, expect.any(Object));
    await waitFor(() => expect(screen.getByText(/当前层级：1 \/ 3/)).toBeTruthy());
  });

  it("流式失败时回退非流式接口", async () => {
    streamTutorHint.mockRejectedValue(new Error("stream unsupported"));
    api.tutorHint.mockResolvedValue({ session_id: "s1", level: 1, level_name: "思路提示", content: "回退内容：先移项。", next_level: 2 });
    render(<TutorScreen />);
    fireEvent.press(screen.getByTestId("pick-question"));
    await waitFor(() => expect(screen.getByTestId("tutor-stem")).toBeTruthy());
    fireEvent.press(screen.getByTestId("start-tutor"));
    await waitFor(() => expect(screen.getByTestId("hint-1")).toBeTruthy());
    fireEvent.press(screen.getByTestId("hint-1"));
    await waitFor(() => expect(screen.getByText(/回退内容：先移项。/)).toBeTruthy());
  });
});
