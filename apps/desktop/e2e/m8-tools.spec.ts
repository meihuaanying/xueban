import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const API_ORIGIN =
  process.env.PLAYWRIGHT_API_ORIGIN ??
  `http://127.0.0.1:${process.env.PLAYWRIGHT_API_PORT ?? (process.platform === "win32" ? "8091" : "8000")}`;

function randomPhone(): string {
  const second = String(3 + Math.floor(Math.random() * 7));
  const tail = String(Math.floor(Math.random() * 1_000_000_000)).padStart(9, "0");
  return `1${second}${tail}`;
}

async function seedAccount(page: Page, request: APIRequestContext): Promise<void> {
  const phone = randomPhone();
  const response = await request.post(`${API_ORIGIN}/v1/auth/register`, {
    data: { phone, password: "E2e-pass-1234", role: "student" },
  });
  expect(response.ok()).toBe(true);
  const tokens = (await response.json()) as { access_token: string; refresh_token: string };
  await page.addInitScript(
    (payload: { access: string; refresh: string }) => {
      window.localStorage.setItem("xueban.desktop.access_token", payload.access);
      window.localStorage.setItem("xueban.desktop.refresh_token", payload.refresh);
    },
    { access: tokens.access_token, refresh: tokens.refresh_token },
  );
}

test.describe("T8.6 陪练中心（F-34 红线 / F-32 情景口语）", () => {
  test("危机表述触发求助引导（含热线）", async ({ page, request }) => {
    await seedAccount(page, request);
    await page.goto("/coach");
    await page.getByTestId("coach-input").fill("我不想活了，感觉撑不下去");
    await page.getByTestId("coach-send").click();
    await expect(page.getByText("我们很在意你的安全")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText(/12356/)).toBeVisible();
    await expect(page.getByText(/120\/110/)).toBeVisible();
  });

  test("普通陪伴与情景口语纠错", async ({ page, request }) => {
    await seedAccount(page, request);
    await page.goto("/coach");
    await page.getByTestId("coach-input").fill("最近有点厌学，不想学习");
    await page.getByTestId("coach-send").click();
    await expect(page.getByText(/最小启动|情绪/).first()).toBeVisible({ timeout: 30_000 });

    await page.getByRole("tab", { name: "情景口语" }).click();
    await page.getByTestId("coach-input").fill("I very like this city.");
    await page.getByTestId("coach-send").click();
    await expect(page.getByText(/really like/).first()).toBeVisible({ timeout: 30_000 });
  });
});

test.describe("T8.1/T8.5/T8.7 V3 学习工具", () => {
  test("拍照搜题只给引导入口（红线段）", async ({ page, request }) => {
    await seedAccount(page, request);
    await page.goto("/tools");
    await page.getByTestId("photo-text").fill("计算 18 乘以 5 等于多少");
    await page.getByTestId("photo-search").click();
    await expect(page.getByTestId("photo-result")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("photo-result").getByRole("button", { name: "开始引导学习" })).toBeVisible();
    await expect(page.getByTestId("photo-result")).not.toContainText("正确选项");
  });

  test("编程判题沙箱：正确代码通过 + 恶意代码被拦", async ({ page, request }) => {
    await seedAccount(page, request);
    await page.goto("/tools");
    await page.getByRole("tab", { name: "编程判题" }).click();
    await page.getByTestId("judge-run").click();
    await expect(page.getByTestId("judge-result")).toContainText("accepted", { timeout: 30_000 });

    await page.getByTestId("judge-code").fill("import socket\nprint('net')");
    await page.getByTestId("judge-run").click();
    await expect(page.getByTestId("judge-result")).toContainText("blocked", { timeout: 30_000 });
  });
});
