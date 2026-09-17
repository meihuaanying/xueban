import { fireEvent, render, screen, waitFor } from "@testing-library/react-native";

import { CoachScreen } from "../screens/coach";

jest.mock("../lib/api", () => {
  const actual = jest.requireActual("../lib/api");
  return {
    ...actual,
    coachApi: { companion: jest.fn(), roleplay: jest.fn() },
  };
});

// eslint-disable-next-line @typescript-eslint/no-require-imports
const { coachApi } = require("../lib/api") as { coachApi: { companion: jest.Mock; roleplay: jest.Mock } };

describe("移动端陪练（T8.6 / F-34）", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("危机表述展示求助引导与热线", async () => {
    coachApi.companion.mockResolvedValue({
      session_id: "s1",
      scene: "companion",
      reply: "我很在意你现在的感受……请拨打热线。",
      corrections: [],
      followups: [],
      crisis: true,
      crisis_resources: ["全国 24 小时心理援助热线：12356"],
    });
    render(<CoachScreen />);
    fireEvent.changeText(screen.getByTestId("coach-input"), "我不想活了");
    fireEvent.press(screen.getByTestId("coach-send"));
    await waitFor(() => expect(screen.getByTestId("coach-crisis")).toBeTruthy());
    expect(screen.getByText(/12356/)).toBeTruthy();
    expect(coachApi.companion).toHaveBeenCalledWith(
      expect.objectContaining({ message: "我不想活了" }),
    );
  });

  it("普通陪伴对话渲染回复", async () => {
    coachApi.companion.mockResolvedValue({
      session_id: "s2",
      scene: "companion",
      reply: "先做最小启动：完成 1 道最简单题。",
      corrections: [],
      followups: [],
      crisis: false,
      crisis_resources: [],
    });
    render(<CoachScreen />);
    fireEvent.changeText(screen.getByTestId("coach-input"), "有点厌学");
    fireEvent.press(screen.getByTestId("coach-send"));
    await waitFor(() => expect(screen.getByText(/最小启动/)).toBeTruthy());
    expect(screen.queryByTestId("coach-crisis")).toBeNull();
  });
});
