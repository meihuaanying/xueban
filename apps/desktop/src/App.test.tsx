import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import App from "./App";

function renderApp(initialPath = "/") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[initialPath]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("桌面端路由守卫（T5.1）", () => {
  it("未登录访问受限页跳转登录页", async () => {
    window.localStorage.clear();
    renderApp("/diagnosis");
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "登录" })).toBeTruthy();
    });
  });

  it("登录页提供登录与注册两个入口", async () => {
    window.localStorage.clear();
    renderApp("/login");
    await waitFor(() => {
      expect(screen.getByRole("tab", { name: "登录" })).toBeTruthy();
    });
    expect(screen.getByRole("tab", { name: "注册" })).toBeTruthy();
    expect(screen.getByLabelText("手机号")).toBeTruthy();
    expect(screen.getByLabelText("密码")).toBeTruthy();
  });
});
