import { fireEvent, render, screen, waitFor } from "@testing-library/react-native";

import App from "./App";

jest.mock("./src/lib/api", () => ({
  ApiError: class ApiError extends Error {},
  api: {
    me: jest.fn().mockRejectedValue(new Error("no token")),
    login: jest.fn(),
    register: jest.fn(),
  },
  setAccessToken: jest.fn(),
}));

jest.mock("expo-secure-store", () => ({
  getItemAsync: jest.fn().mockResolvedValue(null),
  setItemAsync: jest.fn().mockResolvedValue(undefined),
  deleteItemAsync: jest.fn().mockResolvedValue(undefined),
}));

describe("移动端登录守卫（T6.1）", () => {
  it("未登录时展示登录/注册入口", async () => {
    render(<App />);
    await waitFor(() => {
      expect(screen.getByTestId("submit-auth")).toBeTruthy();
    });
    const tabs = screen.getAllByRole("tab");
    expect(tabs.map((tab) => tab.props.accessibilityState?.selected)).toEqual([true, false]);
    expect(screen.getByTestId("phone-input")).toBeTruthy();
    expect(screen.getByTestId("password-input")).toBeTruthy();
  });

  it("手机号校验失败时给出错误提示", async () => {
    render(<App />);
    await waitFor(() => expect(screen.getByTestId("submit-auth")).toBeTruthy());
    fireEvent.changeText(screen.getByTestId("phone-input"), "123");
    fireEvent.press(screen.getByTestId("submit-auth"));
    await waitFor(() => expect(screen.getByTestId("login-error")).toBeTruthy());
    expect(screen.getByText("请输入有效的中国大陆手机号。")).toBeTruthy();
  });
});
