import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { RestBreakGate, RestBreakOverlay } from "./rest-break";

/**
 * 计时逻辑在 use-rest-break.test.ts 里用假定时器验证；
 * 这里只验「拿到状态后渲染成什么样」，所以直接注入 state 绕开计时。
 */
describe("RestBreakGate（§8 约束 2）", () => {
  it("不提醒也不遮挡", () => {
    render(
      <RestBreakGate enabled={false} state={{ warning: false, resting: false }}>
        <p>学习内容</p>
      </RestBreakGate>,
    );
    expect(screen.getByText("学习内容")).toBeDefined();
    expect(screen.queryByText("快到休息时间了")).toBeNull();
    expect(screen.queryByTestId("rest-break-overlay")).toBeNull();
  });

  it("临近上限时顶部出现提醒，但内容仍可见", () => {
    render(
      <RestBreakGate
        state={{ warning: true, resting: false, elapsedMinutes: 18, remainingSeconds: 120 }}
      >
        <p>学习内容</p>
      </RestBreakGate>,
    );
    expect(screen.getByText("快到休息时间了")).toBeDefined();
    expect(screen.getByText(/已经学了 18 分钟/)).toBeDefined();
    expect(screen.getByText(/2 分 00 秒/)).toBeDefined();
    expect(screen.getByText("学习内容")).toBeDefined();
    expect(screen.queryByTestId("rest-break-overlay")).toBeNull();
  });

  it("进入休息后叠加强制遮罩，且不给跳过按钮", () => {
    render(
      <RestBreakGate state={{ resting: true, restRemainingSeconds: 180 }}>
        <p>学习内容</p>
      </RestBreakGate>,
    );
    const overlay = screen.getByTestId("rest-break-overlay");
    expect(overlay.getAttribute("role")).toBe("dialog");
    expect(overlay.getAttribute("aria-modal")).toBe("true");
    expect(screen.getByTestId("rest-break-countdown").textContent).toContain("3 分 00 秒");
    // 「强制」的含义就是不给出路：遮罩上不能有跳过/继续按钮
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("休息中不再显示提醒（避免两层提示叠在一起）", () => {
    render(
      <RestBreakGate state={{ warning: true, resting: true, restRemainingSeconds: 60 }}>
        <p>学习内容</p>
      </RestBreakGate>,
    );
    expect(screen.queryByText("快到休息时间了")).toBeNull();
    expect(screen.getByTestId("rest-break-overlay")).toBeDefined();
  });
});

describe("RestBreakOverlay", () => {
  it("倒计时按 M 分 SS 秒格式化", () => {
    render(<RestBreakOverlay restRemainingSeconds={65} />);
    expect(screen.getByTestId("rest-break-countdown").textContent).toContain("1 分 05 秒");
  });

  it("倒计时不为负", () => {
    render(<RestBreakOverlay restRemainingSeconds={-5} />);
    expect(screen.getByTestId("rest-break-countdown").textContent).toContain("0 分 00 秒");
  });
});
