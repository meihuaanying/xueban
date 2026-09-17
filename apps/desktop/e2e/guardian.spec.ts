import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const API_ORIGIN =
  process.env.PLAYWRIGHT_API_ORIGIN ??
  `http://127.0.0.1:${process.env.PLAYWRIGHT_API_PORT ?? (process.platform === "win32" ? "8091" : "8000")}`;

interface Account {
  id: string;
  phone: string;
  password: string;
  accessToken: string;
  refreshToken: string;
}

function randomPhone(): string {
  const second = String(3 + Math.floor(Math.random() * 7));
  const tail = String(Math.floor(Math.random() * 1_000_000_000)).padStart(9, "0");
  return `1${second}${tail}`;
}

async function register(
  request: APIRequestContext,
  role: "student" | "parent",
): Promise<Account> {
  const phone = randomPhone();
  const password = "E2e-pass-1234";
  const response = await request.post(`${API_ORIGIN}/v1/auth/register`, {
    data: { phone, password, role },
  });
  if (!response.ok()) throw new Error(`注册失败：${await response.text()}`);
  const tokens = (await response.json()) as { access_token: string; refresh_token: string };
  const me = await request.get(`${API_ORIGIN}/v1/auth/me`, {
    headers: { Authorization: `Bearer ${tokens.access_token}` },
  });
  const profile = (await me.json()) as { id: string };
  return {
    id: profile.id,
    phone,
    password,
    accessToken: tokens.access_token,
    refreshToken: tokens.refresh_token,
  };
}

async function setControls(
  request: APIRequestContext,
  parent: Account,
  childId: string,
  options: { limit: number; enabled: boolean },
): Promise<void> {
  const response = await request.put(`${API_ORIGIN}/v1/parents/controls`, {
    headers: { Authorization: `Bearer ${parent.accessToken}` },
    data: {
      child_id: childId,
      parent_password: parent.password,
      is_enabled: options.enabled,
      daily_limit_minutes: options.limit,
      rest_after_minutes: 40,
    },
  });
  if (!response.ok()) throw new Error(`设置防沉迷失败：${await response.text()}`);
}

async function reportUsage(request: APIRequestContext, child: Account, seconds: number): Promise<void> {
  const response = await request.post(`${API_ORIGIN}/v1/analytics/events`, {
    headers: { Authorization: `Bearer ${child.accessToken}` },
    data: { events: [{ name: "study.time", payload: { seconds } }] },
  });
  if (!response.ok()) throw new Error(`上报时长失败：${await response.text()}`);
}

async function seedTokens(page: Page, account: Account): Promise<void> {
  await page.addInitScript(
    (tokens: { access: string; refresh: string }) => {
      window.localStorage.setItem("xueban.desktop.access_token", tokens.access);
      window.localStorage.setItem("xueban.desktop.refresh_token", tokens.refresh);
    },
    { access: account.accessToken, refresh: account.refreshToken },
  );
}

test.describe("T7.2 防沉迷生效链（服务端判定 → 桌面锁屏）", () => {
  test("超过每日上限后桌面端锁屏，放宽后解锁", async ({ page, request }) => {
    const parent = await register(request, "parent");
    const child = await register(request, "student");
    const bind = await request.post(`${API_ORIGIN}/v1/auth/parents/children`, {
      headers: { Authorization: `Bearer ${parent.accessToken}` },
      data: { child_phone: child.phone },
    });
    expect(bind.ok()).toBe(true);

    await setControls(request, parent, child.id, { limit: 30, enabled: true });
    await reportUsage(request, child, 1800);

    await seedTokens(page, child);
    await page.goto("/diagnosis");
    await expect(page.getByTestId("guardian-lock")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText("今日学习时长已达上限")).toBeVisible();
    await expect(page.getByTestId("guardian-usage")).toContainText("30 分钟 / 上限 30 分钟");

    // 家长放宽上限后，客户端重新检查即解锁（服务端判定为准）
    await setControls(request, parent, child.id, { limit: 120, enabled: true });
    await page.getByRole("button", { name: "我休息好了，重新检查" }).click();
    await expect(page.getByTestId("guardian-lock")).toHaveCount(0);
    await expect(page.getByRole("heading", { name: "学情诊断" })).toBeVisible();
  });

  test("关闭防沉迷后不受时长影响", async ({ page, request }) => {
    const parent = await register(request, "parent");
    const child = await register(request, "student");
    await request.post(`${API_ORIGIN}/v1/auth/parents/children`, {
      headers: { Authorization: `Bearer ${parent.accessToken}` },
      data: { child_phone: child.phone },
    });
    await setControls(request, parent, child.id, { limit: 30, enabled: false });
    await reportUsage(request, child, 3600);

    await seedTokens(page, child);
    await page.goto("/diagnosis");
    await expect(page.getByRole("heading", { name: "学情诊断" })).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("guardian-lock")).toHaveCount(0);
  });
});
