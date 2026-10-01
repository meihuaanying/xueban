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
  test("首页 → 注册 → 试用开通 → 引导下载客户端", async ({ page }) => {
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

    // P0 / D4：Web 收缩为官网 + 下载页，注册成功后引导下载桌面客户端
    await expect(page).toHaveURL(/\/download$/, { timeout: 30_000 });
    await expect(page.getByRole("heading", { level: 1 })).toContainText("下载学伴");
    // 下载卡片里的链接可访问名是「前往 Release 下载」，文件名只是卡片正文，
    // 因此按 href 断言 Release 资产接线（这才是转化链路的实质）。
    await expect(page.locator('a[href*="XueBan-Setup-x64.exe"]')).toBeVisible();
    await page.screenshot({
      path: path.join(EVIDENCE_DIR, "m4-04-download-after-register.png"),
      fullPage: false,
    });
  });

  test("下载页提供 Web 版注册入口（未登录亦可浏览）", async ({ page }) => {
    await page.goto("/download");
    await expect(page.getByRole("link", { name: "使用 Web 版学习" })).toHaveAttribute(
      "href",
      "/register",
    );
    // 四张平台卡的下载链接都指向 GitHub Release 稳定资产名
    await expect(page.locator('a[href*="XueBan-"]')).toHaveCount(3);
    await expect(page.locator('a[href*="xueban-release.apk"]')).toHaveCount(1);
  });
});
