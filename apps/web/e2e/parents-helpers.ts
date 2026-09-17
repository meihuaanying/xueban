import type { APIRequestContext, Page } from "@playwright/test";

const API_ORIGIN =
  process.env.PLAYWRIGHT_API_ORIGIN ??
  `http://127.0.0.1:${process.env.PLAYWRIGHT_API_PORT ?? (process.platform === "win32" ? "8090" : "8000")}`;

const ADMIN_PHONE = process.env.E2E_ADMIN_PHONE ?? "13900000000";
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? "admin-dev-123";

export interface Account {
  phone: string;
  password: string;
  accessToken: string;
  refreshToken: string;
  id: string;
}

export function randomPhone(): string {
  const second = String(3 + Math.floor(Math.random() * 7));
  const tail = String(Math.floor(Math.random() * 1_000_000_000)).padStart(9, "0");
  return `1${second}${tail}`;
}

export async function registerAccount(
  request: APIRequestContext,
  options: { role: "student" | "parent" } = { role: "student" },
): Promise<Account> {
  const phone = randomPhone();
  const password = "E2e-pass-1234";
  const response = await request.post(`${API_ORIGIN}/v1/auth/register`, {
    data: { phone, password, role: options.role },
  });
  if (!response.ok()) throw new Error(`注册失败：${response.status()} ${await response.text()}`);
  const tokens = (await response.json()) as { access_token: string; refresh_token: string };
  const me = await request.get(`${API_ORIGIN}/v1/auth/me`, {
    headers: { Authorization: `Bearer ${tokens.access_token}` },
  });
  const profile = (await me.json()) as { id: string };
  return {
    phone,
    password,
    id: profile.id,
    accessToken: tokens.access_token,
    refreshToken: tokens.refresh_token,
  };
}

export function authHeaders(account: Account): Record<string, string> {
  return { Authorization: `Bearer ${account.accessToken}` };
}

export async function bindChild(
  request: APIRequestContext,
  parent: Account,
  childPhone: string,
): Promise<void> {
  const response = await request.post(`${API_ORIGIN}/v1/auth/parents/children`, {
    headers: authHeaders(parent),
    data: { child_phone: childPhone },
  });
  if (!response.ok()) throw new Error(`绑定失败：${response.status()} ${await response.text()}`);
}

/** 与官网 localStorage 键名一致（auth-storage）。 */
export async function seedTokens(page: Page, account: Account): Promise<void> {
  await page.addInitScript(
    (tokens: { access: string; refresh: string }) => {
      window.localStorage.setItem("xueban.access_token", tokens.access);
      window.localStorage.setItem("xueban.refresh_token", tokens.refresh);
    },
    { access: account.accessToken, refresh: account.refreshToken },
  );
}

export async function completeParentTask(
  request: APIRequestContext,
  child: Account,
  taskId: string,
): Promise<void> {
  const response = await request.post(`${API_ORIGIN}/v1/parents/tasks/${taskId}/done`, {
    headers: authHeaders(child),
  });
  if (!response.ok()) throw new Error(`孩子完成任务失败：${response.status()} ${await response.text()}`);
}

export const ADMIN = { phone: ADMIN_PHONE, password: ADMIN_PASSWORD };
export { API_ORIGIN };
