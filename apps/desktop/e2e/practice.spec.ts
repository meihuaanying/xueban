import { expect, test } from "@playwright/test";

import { apiGet, signInWithProgress } from "./journey-helpers";

/** 旅程第 4 站 · 学习单元：出题 → 作答 → 即时反馈 */
test.describe("旅程第 4 站 · 练习作答", () => {
  test("出题后可作答并显示即时反馈", async ({ page, request }) => {
    await signInWithProgress(page, request, "unit");
    await page.goto("/journey/unit");

    // 前置动作：必须先出题，否则题卡与选项不会出现
    await page.getByTestId("unit-generate").click();

    const option = page.locator('[data-testid^="option-"]').first();
    await expect(option).toBeVisible({ timeout: 20_000 });
    await option.click();

    const feedback = page.getByTestId("unit-feedback");
    await expect(feedback).toBeVisible({ timeout: 20_000 });
    await expect(feedback).toContainText(/答对了|还没掌握/);
  });
});

/** 旅程第 5 站 · 错题复习（FSRS 到期卡） */
test.describe("旅程第 5 站 · 错题复习", () => {
  test("错题本与 API 一致，可完成复习进入复盘", async ({ page, request }) => {
    const account = await signInWithProgress(page, request, "mistakes");
    await page.goto("/journey/mistakes");

    const list = await apiGet<{ active_count: number }>(request, account, "/v1/mistakes?limit=20");
    await expect(page.getByTestId("mistake-list")).toBeVisible();
    await expect(page.getByTestId("mistake-list")).toContainText(
      list.active_count > 0 ? "复习" : "空",
    );

    await page.getByTestId("mistakes-to-review").click();
    await expect(page).toHaveURL(/\/journey\/review$/);
  });

  test("复习评分后记录下次复习时间", async ({ page, request }) => {
    await signInWithProgress(page, request, "mistakes");
    await page.goto("/journey/mistakes");

    const grade = page.locator('[data-testid^="review-grade-"]').first();
    if ((await grade.count()) === 0) return; // 无到期卡时无可评分内容
    await grade.click();
    await expect(page.getByText(/下次 .* 天后复习/)).toBeVisible({ timeout: 15_000 });
  });
});
