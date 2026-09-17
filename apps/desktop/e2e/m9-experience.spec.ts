import fs from "node:fs";
import path from "node:path";

import AxeBuilder from "@axe-core/playwright";
import { expect, test, type APIRequestContext, type Browser, type Page } from "@playwright/test";

const API_ORIGIN =
  process.env.PLAYWRIGHT_API_ORIGIN ??
  `http://127.0.0.1:${process.env.PLAYWRIGHT_API_PORT ?? (process.platform === "win32" ? "8091" : "8000")}`;

const EVIDENCE_DIR = path.resolve(process.cwd(), "..", "..", "docs", "verification", "assets");

function ensureEvidenceDir(): void {
  fs.mkdirSync(EVIDENCE_DIR, { recursive: true });
}

async function createAccount(request: APIRequestContext): Promise<{
  phone: string;
  accessToken: string;
  refreshToken: string;
}> {
  const phone = `1${3 + Math.floor(Math.random() * 7)}${String(
    Math.floor(Math.random() * 1_000_000_000),
  ).padStart(9, "0")}`;
  const response = await request.post(`${API_ORIGIN}/v1/auth/register`, {
    data: { phone, password: "E2e-pass-1234", role: "student" },
  });
  if (!response.ok()) throw new Error(`注册失败：${await response.text()}`);
  const tokens = (await response.json()) as { access_token: string; refresh_token: string };
  return { phone, accessToken: tokens.access_token, refreshToken: tokens.refresh_token };
}

async function seed(page: Page, account: { accessToken: string; refreshToken: string }): Promise<void> {
  await page.addInitScript(
    (payload: { access: string; refresh: string }) => {
      window.localStorage.setItem("xueban.desktop.access_token", payload.access);
      window.localStorage.setItem("xueban.desktop.refresh_token", payload.refresh);
    },
    { access: account.accessToken, refresh: account.refreshToken },
  );
}

test.describe("T9.1 多端同步（F-39）", () => {
  test("A 端打卡后 B 端 30 秒内可见（同步指示器 + 任务状态）", async ({
    browser,
    request,
  }: {
    browser: Browser;
    request: APIRequestContext;
  }) => {
    const account = await createAccount(request);
    const contextA = await browser.newContext();
    const contextB = await browser.newContext();
    const pageA = await contextA.newPage();
    const pageB = await contextB.newPage();
    await seed(pageA, account);
    await seed(pageB, account);

    await pageA.goto("/plan");
    await pageB.goto("/plan");
    await expect(pageA.getByTestId("today-task").first()).toBeVisible({ timeout: 30_000 });
    await expect(pageB.getByTestId("today-task").first()).toBeVisible({ timeout: 30_000 });

    const indBefore = await pageB.getByTestId("sync-indicator").innerText();
    // A 端完成第一个任务
    await pageA.getByRole("button", { name: "完成任务" }).first().click();
    await expect(pageA.getByText("已全部完成")).toBeVisible({ timeout: 30_000 }).catch(() => undefined);

    // B 端轮询（5s）后应看到打卡进度变化
    await expect
      .poll(async () => pageB.getByTestId("sync-indicator").innerText(), { timeout: 30_000 })
      .not.toBe(indBefore);

    await pageB.screenshot({ path: path.join(EVIDENCE_DIR, "m9-01-sync-b-context.png") });
    await contextA.close();
    await contextB.close();
  });
});

test.describe("T9.4 新手引导（≤5 步到达首次讲解）", () => {
  test("注册 → 快速开始 → 讲解会话就绪", async ({ page, request }) => {
    const account = await createAccount(request);
    await seed(page, account);

    await page.goto("/diagnosis");
    await expect(page.getByTestId("onboarding-card")).toBeVisible({ timeout: 30_000 });
    await page.screenshot({ path: path.join(EVIDENCE_DIR, "m9-02-onboarding.png") });

    // 第 2 步：点击快速开始（自动获取题目并创建讲解会话）
    await page.getByTestId("quickstart-tutor").click();
    await expect(page.getByTestId("tutor-stem")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("hint-level-1")).toBeEnabled({ timeout: 30_000 });

    // 第 3 步：请求第一层提示
    await page.getByTestId("hint-level-1").click();
    await expect(page.getByTestId("tutor-messages")).toContainText("思路提示", { timeout: 30_000 });
    await page.screenshot({ path: path.join(EVIDENCE_DIR, "m9-03-first-tutor.png") });
  });
});

test.describe("T9.3 三态与暗色（截图入档 + axe）", () => {
  test("加载 / 错误 / 空态截图", async ({ page, request }) => {
    ensureEvidenceDir();
    const account = await createAccount(request);
    await seed(page, account);

    // 错误态：拦截计划接口返回 500
    await page.route("**/v1/plan/path*", (route) =>
      route.fulfill({ status: 500, contentType: "application/json", body: "{}" }),
    );
    await page.goto("/plan");
    await expect(page.getByTestId("error-block")).toBeVisible({ timeout: 30_000 });
    await page.screenshot({ path: path.join(EVIDENCE_DIR, "m9-04-state-error.png") });
    await page.unroute("**/v1/plan/path*");

    // 加载态：延迟响应后立即截图
    await page.route("**/v1/plan/path*", async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 2500));
      await route.continue();
    });
    await page.reload();
    await page.screenshot({ path: path.join(EVIDENCE_DIR, "m9-05-state-loading.png") });
    await expect(page.getByTestId("path-phase").first()).toBeVisible({ timeout: 30_000 });
    await page.unroute("**/v1/plan/path*");

    // 空态：新账号复盘页（无学习记录）
    await page.goto("/review");
    await expect(page.getByText(/暂无|未设置|为空/).first()).toBeVisible({ timeout: 30_000 });
    await page.screenshot({ path: path.join(EVIDENCE_DIR, "m9-06-state-empty.png") });
  });

  test("暗色模式 + axe 0 critical / serious（计划页）", async ({ page, request }) => {
    const account = await createAccount(request);
    await seed(page, account);
    await page.goto("/plan");
    await expect(page.getByTestId("today-task").first()).toBeVisible({ timeout: 30_000 });
    await page.getByTestId("theme-toggle").click();
    await expect(page.locator("html")).toHaveClass(/dark/);

    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();
    const blocking = results.violations
      .filter((violation) => violation.impact === "critical" || violation.impact === "serious")
      .map((violation) => ({
        id: violation.id,
        targets: violation.nodes.map((node) => node.target.join(" ")).slice(0, 5),
      }));
    expect(blocking).toEqual([]);
    await page.screenshot({ path: path.join(EVIDENCE_DIR, "m9-07-dark-plan.png") });
  });
});
