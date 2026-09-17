import fs from "node:fs";
import path from "node:path";

import { expect, test } from "@playwright/test";

const EVIDENCE_DIR = path.resolve(process.cwd(), "..", "..", "docs", "verification", "assets");

function ensureEvidenceDir(): void {
  fs.mkdirSync(EVIDENCE_DIR, { recursive: true });
}

/** 生成符合 1[3-9]xxxxxxxxx 的唯一手机号（按时间戳，避免重复注册）。 */
function uniquePhone(): string {
  const suffix = String(Date.now() % 100_000_000).padStart(8, "0");
  return `131${suffix}`;
}

test.describe("官网转化链路（T4.3）", () => {
  test("首页 → 注册 → 试用开通 → 学习中心可见状态", async ({ page }) => {
    ensureEvidenceDir();

    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1 })).toContainText("把每一道题");
    await page.screenshot({ path: path.join(EVIDENCE_DIR, "m4-01-home.png"), fullPage: false });

    const primaryCta = page.locator("main").getByRole("link", { name: "免费开始学习" });
    await expect(primaryCta).toBeVisible();
    await primaryCta.screenshot({ path: path.join(EVIDENCE_DIR, "m4-02-primary-button.png") });
    await primaryCta.click();

    await expect(page).toHaveURL(/\/register$/);
    await expect(page.getByRole("heading", { level: 1 })).toContainText("免费注册");
    await page.screenshot({ path: path.join(EVIDENCE_DIR, "m4-03-register.png"), fullPage: false });

    const phone = uniquePhone();
    await page.getByLabel("手机号").fill(phone);
    await page.getByLabel("密码").fill("Test-pass-1234");
    await page.getByLabel("昵称（选填）").fill("E2E 测试同学");
    await page.getByRole("checkbox", { name: /K12 阶段学生/ }).check();
    await page.getByRole("checkbox", { name: /我已阅读并同意/ }).check();
    await page.getByRole("button", { name: "注册并开通试用" }).click();

    await expect(page).toHaveURL(/\/app$/, { timeout: 30_000 });
    await expect(page.getByText("试用中").first()).toBeVisible();
    await expect(page.getByText("到期时间")).toBeVisible();
    await expect(page.getByText("剩余天数")).toBeVisible();
    await expect(page.getByText(/^\d+ 天$/).first()).toBeVisible();
    await page.screenshot({
      path: path.join(EVIDENCE_DIR, "m4-04-app-trial.png"),
      fullPage: false,
    });
  });

  test("未登录访问学习中心引导注册", async ({ page }) => {
    await page.goto("/app");
    await expect(page.getByText("尚未登录")).toBeVisible();
    await expect(page.getByRole("link", { name: "免费注册并开通试用" })).toBeVisible();
  });
});
