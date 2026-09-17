import { fireEvent, render, screen, waitFor } from "@testing-library/react-native";

import { AuthProvider, useAuth } from "../lib/auth";
import { LoginScreen } from "../screens/login";
import { Text, View } from "react-native";

jest.mock("../lib/api", () => {
  const actual = jest.requireActual("../lib/api");
  return {
    ...actual,
    api: { me: jest.fn(), login: jest.fn(), register: jest.fn() },
    setAccessToken: jest.fn(),
  };
});

jest.mock("expo-secure-store", () => ({
  getItemAsync: jest.fn(),
  setItemAsync: jest.fn(),
  deleteItemAsync: jest.fn(),
}));

// eslint-disable-next-line @typescript-eslint/no-require-imports
const { api: mockedApi } = require("../lib/api") as {
  api: { me: jest.Mock; login: jest.Mock; register: jest.Mock };
};
// eslint-disable-next-line @typescript-eslint/no-require-imports
const SecureStore = require("expo-secure-store") as {
  getItemAsync: jest.Mock;
  setItemAsync: jest.Mock;
  deleteItemAsync: jest.Mock;
};

const TOKENS = {
  access_token: "access-1",
  refresh_token: "refresh-1",
  token_type: "bearer",
  expires_in: 900,
};

const PROFILE = {
  id: "u1",
  phone: "13900000000",
  nickname: "小明",
  role: "student",
  is_k12: false,
  created_at: "2026-09-16T00:00:00Z",
};

function Probe() {
  const { status, user, logout } = useAuth();
  return (
    <View>
      <Text testID="status">{status}</Text>
      <Text testID="user">{user?.phone ?? "-"}</Text>
      <Text testID="logout" onPress={() => void logout()}>
        退出
      </Text>
    </View>
  );
}

beforeEach(() => {
  jest.clearAllMocks();
  SecureStore.getItemAsync.mockResolvedValue(null);
  SecureStore.setItemAsync.mockResolvedValue(undefined);
  SecureStore.deleteItemAsync.mockResolvedValue(undefined);
});

describe("移动端登录态（T6.1）", () => {
  it("SecureStore 有令牌 → 拉取用户进入 authenticated", async () => {
    SecureStore.getItemAsync.mockImplementation(async (key: string) =>
      key.includes("access") ? "access-1" : "refresh-1",
    );
    mockedApi.me.mockResolvedValue(PROFILE);
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("authenticated"));
    expect(screen.getByTestId("user")).toHaveTextContent("13900000000");
  });

  it("令牌失效 → 清理并匿名", async () => {
    SecureStore.getItemAsync.mockImplementation(async (key: string) =>
      key.includes("access") ? "stale" : "refresh-1",
    );
    const { ApiError } = jest.requireActual("../lib/api");
    mockedApi.me.mockRejectedValue(new ApiError(401, { code: "AUTH_UNAUTHORIZED", message: "未认证" }));
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("anonymous"));
    expect(SecureStore.deleteItemAsync).toHaveBeenCalled();
  });

  it("退出登录清理令牌", async () => {
    SecureStore.getItemAsync.mockResolvedValue("access-1");
    mockedApi.me.mockResolvedValue(PROFILE);
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("authenticated"));
    fireEvent.press(screen.getByTestId("logout"));
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("anonymous"));
    expect(SecureStore.deleteItemAsync).toHaveBeenCalledTimes(2);
  });
});

describe("移动端登录/注册页", () => {
  it("校验手机号并提示错误", async () => {
    render(
      <AuthProvider>
        <LoginScreen />
      </AuthProvider>,
    );
    fireEvent.changeText(screen.getByTestId("phone-input"), "123");
    fireEvent.changeText(screen.getByTestId("password-input"), "password123");
    fireEvent.press(screen.getByTestId("submit-auth"));
    await waitFor(() =>
      expect(screen.getByText("请输入有效的中国大陆手机号。")).toBeTruthy(),
    );
  });

  it("注册成功调用 register 并进入登录态", async () => {
    mockedApi.register.mockResolvedValue(TOKENS);
    mockedApi.me.mockResolvedValue(PROFILE);
    render(
      <AuthProvider>
        <LoginScreen />
        <Probe />
      </AuthProvider>,
    );
    // 切到注册模式
    fireEvent.press(screen.getByText("注册"));
    fireEvent.changeText(screen.getByTestId("phone-input"), "13900000001");
    fireEvent.changeText(screen.getByTestId("password-input"), "password1234");
    fireEvent.changeText(screen.getByTestId("nickname-input"), "测试");
    fireEvent.press(screen.getByTestId("submit-auth"));
    await waitFor(() => expect(mockedApi.register).toHaveBeenCalled());
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("authenticated"));
  });

  it("密码过短提示错误", async () => {
    render(
      <AuthProvider>
        <LoginScreen />
      </AuthProvider>,
    );
    fireEvent.press(screen.getByText("注册"));
    fireEvent.changeText(screen.getByTestId("phone-input"), "13900000002");
    fireEvent.changeText(screen.getByTestId("password-input"), "short");
    fireEvent.press(screen.getByTestId("submit-auth"));
    await waitFor(() => expect(screen.getByText("密码至少 8 位。")).toBeTruthy());
  });
});
