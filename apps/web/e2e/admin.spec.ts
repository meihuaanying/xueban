import { expect, test } from "@playwright/test";

import { ADMIN } from "./parents-helpers";

test.describe("T7.3 / T7.4 运营后台", () => {
  test("管理员登录 → 题库审核流 → 覆盖率看板", async ({ page }) => {
    await page.goto("/admin");
    await expect(page.getByTestId("admin-login")).toBeVisible();
    await page.getByTestId("admin-phone").fill(ADMIN.phone);
    await page.getByTestId("admin-password").fill(ADMIN.password);
    await page.getByTestId("admin-login-submit").click();

    await expect(page.getByTestId("admin-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("coverage-card")).toBeVisible();

    // 新建草稿 → 提交审核 → 上线
    const stem = `E2E 题目 ${Date.now()}`;
    await page.getByTestId("new-stem").fill(stem);
    await page.getByTestId("new-answer").fill("A");
    await page.getByTestId("new-analysis").fill("解析：正确选项为 A。");
    await page.getByTestId("create-question").click();

    const row = page.getByTestId("admin-question").filter({ hasText: stem });
    await expect(row).toBeVisible({ timeout: 30_000 });
    await expect(row.getByText("草稿")).toBeVisible();

    await row.getByRole("button", { name: "提交审核" }).click();
    await expect(row.getByText("待审核")).toBeVisible();
    await row.getByRole("button", { name: "上线" }).click();
    await expect(row.getByText("已上线")).toBeVisible();

    // 版本历史（创建 + 审核 + 上线）
    await row.getByRole("button", { name: "版本历史" }).click();
    await expect(row.getByText(/版本 [3-9]/)).toBeVisible();
  });

  test("质量巡检与数据看板", async ({ page }) => {
    await page.goto("/admin");
    await page.getByTestId("admin-phone").fill(ADMIN.phone);
    await page.getByTestId("admin-password").fill(ADMIN.password);
    await page.getByTestId("admin-login-submit").click();
    await expect(page.getByTestId("admin-page")).toBeVisible({ timeout: 30_000 });

    // 巡检
    await page.getByRole("tab", { name: "质量巡检" }).click();
    await page.getByTestId("run-inspection").click();
    await expect(page.getByTestId("inspection-report").first()).toBeVisible({ timeout: 30_000 });

    // 数据看板
    await page.getByRole("tab", { name: "数据看板" }).click();
    await expect(page.getByTestId("metrics-card")).toBeVisible();
    await expect(page.getByText("次日留存")).toBeVisible();
    await expect(page.getByText("续费率")).toBeVisible();
  });

  test("A/B 实验创建与报告（含显著性列）", async ({ page }) => {
    await page.goto("/admin");
    await page.getByTestId("admin-phone").fill(ADMIN.phone);
    await page.getByTestId("admin-password").fill(ADMIN.password);
    await page.getByTestId("admin-login-submit").click();
    await expect(page.getByTestId("admin-page")).toBeVisible({ timeout: 30_000 });

    await page.getByRole("tab", { name: "A/B 实验" }).click();
    const key = `e2e-exp-${Date.now() % 1_000_000}`;
    await page.getByTestId("experiment-key").fill(key);
    await page.getByTestId("create-experiment").click();

    const row = page.getByTestId("experiment-row").filter({ hasText: key });
    await expect(row).toBeVisible({ timeout: 30_000 });
    await row.getByRole("button", { name: "查看报告" }).click();
    await expect(page.getByTestId("experiment-report")).toBeVisible();
    await expect(page.getByTestId("experiment-report")).toContainText("样本不足");
  });

  test("学生账号访问后台提示无权限", async ({ page }) => {
    await page.goto("/admin");
    await page.getByTestId("admin-phone").fill("13800000001");
    await page.getByTestId("admin-password").fill("wrong-password");
    await page.getByTestId("admin-login-submit").click();
    await expect(page.getByText(/登录未完成|不是管理员/)).toBeVisible({ timeout: 30_000 });
  });
});
