import { render, screen, waitFor } from "@testing-library/react-native";

import { GuardianGate } from "../components/guardian-gate";

jest.mock("../lib/api", () => {
  const actual = jest.requireActual("../lib/api");
  return {
    ...actual,
    api: { guardianStatus: jest.fn() },
  };
});

// eslint-disable-next-line @typescript-eslint/no-require-imports
const { api } = require("../lib/api") as { api: { guardianStatus: jest.Mock } };

describe("移动端防沉迷闸门（T7.2）", () => {
  it("达到上限时展示锁屏页与用量", async () => {
    api.guardianStatus.mockResolvedValue({
      locked: true,
      reasons: ["daily_limit"],
      used_minutes: 30,
      limit_minutes: 30,
      available_from: null,
    });
    render(
      <GuardianGate>
        <></>
      </GuardianGate>,
    );
    await waitFor(() => expect(screen.getByTestId("guardian-lock")).toBeTruthy());
    expect(screen.getByText("今日学习时长已达上限")).toBeTruthy();
    expect(screen.getByText("今日已学习 30 分钟 / 上限 30 分钟")).toBeTruthy();
  });

  it("未锁定时正常渲染内容", async () => {
    api.guardianStatus.mockResolvedValue({
      locked: false,
      reasons: [],
      used_minutes: 10,
      limit_minutes: 60,
      available_from: null,
    });
    render(
      <GuardianGate>
        <></>
      </GuardianGate>,
    );
    await waitFor(() => expect(api.guardianStatus).toHaveBeenCalled());
    expect(screen.queryByTestId("guardian-lock")).toBeNull();
  });
});
