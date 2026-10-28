import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import LoginPage from "./login";

const mocks = vi.hoisted(() => ({ login: vi.fn(), register: vi.fn() }));

vi.mock("@/lib/auth", () => ({
  useAuth: () => mocks,
}));

function renderLogin() {
  return render(
    <MemoryRouter initialEntries={["/login"]}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/journey/today" element={<p>今日页</p>} />
        <Route path="/onboarding" element={<p>引导页</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

function submitLogin() {
  fireEvent.change(screen.getByLabelText("手机号"), {
    target: { value: "13900000000" },
  });
  fireEvent.change(screen.getByLabelText("密码"), { target: { value: "Test-1234" } });
  fireEvent.click(screen.getByRole("button", { name: "登录" }));
}

beforeEach(() => {
  window.localStorage.clear();
  mocks.login.mockReset().mockResolvedValue(undefined);
  mocks.register.mockReset().mockResolvedValue(undefined);
});

describe("登录后的落点", () => {
  it("新用户没有学段时进入 onboarding", async () => {
    renderLogin();
    submitLogin();
    await waitFor(() => expect(mocks.login).toHaveBeenCalledTimes(1));
    expect(await screen.findByText("引导页")).toBeInTheDocument();
  });

  it("已选学段的老用户直接回今日页", async () => {
    window.localStorage.setItem("xueban.gradeBand", "senior");
    renderLogin();
    submitLogin();
    await waitFor(() => expect(mocks.login).toHaveBeenCalledTimes(1));
    expect(await screen.findByText("今日页")).toBeInTheDocument();
  });
});
