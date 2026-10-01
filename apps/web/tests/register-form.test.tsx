import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { RegisterForm } from "@/components/register-form";
import { ApiError } from "@/lib/api";

const push = vi.fn();
const registerAccount = vi.fn();
const startTrial = vi.fn();
const saveTokens = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    registerAccount: (...args: unknown[]) => registerAccount(...args),
    startTrial: (...args: unknown[]) => startTrial(...args),
  };
});

vi.mock("@/lib/auth-storage", () => ({
  saveTokens: (...args: unknown[]) => saveTokens(...args),
}));

const TOKENS = { access_token: "access-1", refresh_token: "refresh-1", token_type: "bearer" };

function fill({ phone = "13900000000", password = "E2e-pass-1234" } = {}) {
  fireEvent.change(screen.getByLabelText("手机号"), { target: { value: phone } });
  fireEvent.change(screen.getByLabelText("密码"), { target: { value: password } });
}

function agree() {
  fireEvent.click(screen.getByText(/我已阅读并同意/));
}

function submit() {
  // 走真实点击路径（按钮 type="submit"），比 fireEvent.submit 更贴近用户行为
  fireEvent.click(screen.getByRole("button", { name: /注册并开通试用|正在创建账号|正在开通试用/ }));
}

beforeEach(() => {
  push.mockReset();
  registerAccount.mockReset();
  startTrial.mockReset();
  saveTokens.mockReset();
  registerAccount.mockResolvedValue(TOKENS);
  startTrial.mockResolvedValue({ ok: true });
});

describe("注册表单校验（P0 页面拆分后仍逐字保持 E2E 契约）", () => {
  it("渲染字段 id/name 与 role-select testid", () => {
    render(<RegisterForm />);
    expect(screen.getByLabelText("手机号")).toHaveAttribute("id", "phone");
    expect(screen.getByLabelText("密码")).toHaveAttribute("name", "password");
    expect(screen.getByLabelText("昵称（选填）")).toHaveAttribute("id", "nickname");
    expect(screen.getByTestId("role-select")).toHaveAttribute("id", "role");
  });

  it("手机号非法时给出提示且不调用注册", () => {
    render(<RegisterForm />);
    fill({ phone: "12345" });
    agree();
    submit();
    expect(screen.getByRole("alert")).toHaveTextContent("请输入有效的中国大陆手机号。");
    expect(registerAccount).not.toHaveBeenCalled();
  });

  it("密码不足 8 位时给出提示", () => {
    render(<RegisterForm />);
    fill({ password: "short" });
    agree();
    submit();
    expect(screen.getByRole("alert")).toHaveTextContent("密码至少 8 位。");
    expect(registerAccount).not.toHaveBeenCalled();
  });

  it("未同意隐私政策时拒绝提交", () => {
    render(<RegisterForm />);
    fill();
    submit();
    expect(screen.getByRole("alert")).toHaveTextContent("请先阅读并同意隐私政策与未成年人保护声明。");
    expect(registerAccount).not.toHaveBeenCalled();
  });
});

describe("注册成功路径（D4：学生注册后引导下载客户端）", () => {
  it("学生角色：注册 → 存 token → 开通试用 → 跳转 /download", async () => {
    render(<RegisterForm />);
    fill();
    fireEvent.change(screen.getByLabelText("昵称（选填）"), { target: { value: "小伴" } });
    agree();
    submit();

    await waitFor(() => expect(push).toHaveBeenCalledWith("/download"));
    expect(registerAccount).toHaveBeenCalledWith({
      phone: "13900000000",
      password: "E2e-pass-1234",
      nickname: "小伴",
      is_k12: false,
      role: "student",
    });
    expect(saveTokens).toHaveBeenCalledWith(TOKENS);
    expect(startTrial).toHaveBeenCalledWith("access-1");
  });

  it("昵称留空时传 undefined，不开试用（家长角色）", async () => {
    render(<RegisterForm />);
    fill();
    fireEvent.change(screen.getByTestId("role-select"), { target: { value: "parent" } });
    agree();
    submit();

    await waitFor(() => expect(push).toHaveBeenCalledWith("/download"));
    expect(registerAccount).toHaveBeenCalledWith(
      expect.objectContaining({ nickname: undefined, role: "parent" }),
    );
    expect(startTrial).not.toHaveBeenCalled();
  });
});

describe("注册失败路径", () => {
  it("ApiError 展示后端文案", async () => {
    registerAccount.mockRejectedValue(
      new ApiError(409, { code: "PHONE_TAKEN", message: "手机号已注册", trace_id: null }),
    );
    render(<RegisterForm />);
    fill();
    agree();
    submit();
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("手机号已注册"));
    expect(push).not.toHaveBeenCalled();
  });

  it("非 ApiError 走网络兜底文案且按钮恢复可用", async () => {
    registerAccount.mockRejectedValue(new Error("boom"));
    render(<RegisterForm />);
    fill();
    agree();
    submit();
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("无法连接服务器，请稍后重试。"),
    );
    expect(screen.getByRole("button", { name: "注册并开通试用" })).toBeEnabled();
  });
});
