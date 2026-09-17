/** 桌面端 E2E 公共工具：账号创建、token 注入、API 直连断言。 */

import type { APIRequestContext, Page } from "@playwright/test";

const API_ORIGIN =
  process.env.PLAYWRIGHT_API_ORIGIN ??
  `http://127.0.0.1:${process.env.PLAYWRIGHT_API_PORT ?? (process.platform === "win32" ? "8091" : "8000")}`;

export { API_ORIGIN };

export interface TestAccount {
  phone: string;
  password: string;
  accessToken: string;
  refreshToken: string;
}

/** 通过 API 直接创建账号（E2E 提速；UI 注册链路由 journey 1 覆盖）。 */
/** 生成 1[3-9]xxxxxxxxx 的随机手机号（11 位，并行用例之间不冲突）。 */
export function randomPhone(): string {
  const second = String(3 + Math.floor(Math.random() * 7));
  const tail = String(Math.floor(Math.random() * 1_000_000_000)).padStart(9, "0");
  return `1${second}${tail}`;
}

/** 通过 API 直接创建账号（E2E 提速；UI 注册链路由 journey 1 覆盖）。 */
export async function createAccount(request: APIRequestContext): Promise<TestAccount> {
  const password = "E2e-pass-1234";
  let lastError = "";
  for (let attempt = 0; attempt < 5; attempt += 1) {
    const phone = randomPhone();
    const response = await request.post(`${API_ORIGIN}/v1/auth/register`, {
      data: { phone, password, role: "student" },
    });
    if (response.ok()) {
      const tokens = (await response.json()) as { access_token: string; refresh_token: string };
      return { phone, password, accessToken: tokens.access_token, refreshToken: tokens.refresh_token };
    }
    lastError = `${response.status()} ${await response.text()}`;
  }
  throw new Error(`注册测试账号失败：${lastError}`);
}

/** 把登录态写入 localStorage（与 token-store 的键名一致），再访问页面即视为已登录。 */
export async function seedTokens(page: Page, account: TestAccount): Promise<void> {
  await page.addInitScript(
    (tokens: { access: string; refresh: string }) => {
      window.localStorage.setItem("xueban.desktop.access_token", tokens.access);
      window.localStorage.setItem("xueban.desktop.refresh_token", tokens.refresh);
    },
    { access: account.accessToken, refresh: account.refreshToken },
  );
}

/** 带鉴权的 API 请求（用于与 UI 做数据一致性断言）。 */
export async function apiGet<T>(
  request: APIRequestContext,
  account: TestAccount,
  path: string,
): Promise<T> {
  const response = await request.get(`${API_ORIGIN}${path}`, {
    headers: { Authorization: `Bearer ${account.accessToken}` },
  });
  if (!response.ok()) {
    throw new Error(`GET ${path} 失败：${response.status()} ${await response.text()}`);
  }
  return (await response.json()) as T;
}

export async function apiPost<T>(
  request: APIRequestContext,
  account: TestAccount,
  path: string,
  data: unknown,
): Promise<T> {
  const response = await request.post(`${API_ORIGIN}${path}`, {
    headers: { Authorization: `Bearer ${account.accessToken}` },
    data,
  });
  return (await response.json()) as T;
}
