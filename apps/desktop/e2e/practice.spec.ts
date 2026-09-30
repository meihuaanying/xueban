import { expect, test } from "@playwright/test";

import { apiGet, signInWithProgress } from "./journey-helpers";

/** T5.5 练习与错题本闭环 → 旅程第 4 站出题 + 第 5 站错题复习 */
test.describe("旅程第 4 站 · 练习作答", () => {
  test("作答后展示判定反馈与错题收录", async ({ page, request }) => {
    await signInWithProgress(page, request, "unit");
    await page.goto("/journey/unit");

    const generate = page.getByRole("button", { name: /出题|生成/ });
    if ((await generate.count()) > 0) await generate.first().click();

    const option = page.locator('[data-testid^="option-"]').first();
    await expect(option).toBeVisible({ timeout: 20_000 });
    await option.click();

    const feedback = page.getByTestId("unit-feedback");
    await expect(feedback).toBeVisible({ timeout: 20_000 });
    await expect(feedback).toContainText(/答对了|还没掌握/);
  });
});

/** 旅程第 5 站 · 错题复习（含 FSRS 到期卡评分） */
test.describe("旅程第 5 站 · 错题复习", () => {
  test("错题本与 API 一致，可完成复习进入复盘", async ({ page, request }) => {
    const account = await signInWithProgress(page, request, "mistakes");
    await page.goto("/journey/mistakes");

    const list = await apiGet<{ active_count: number }>(request, account, "/v1/mistakes?limit=20");
    await expect(page.getByTestId("mistake-list")).toBeVisible();
    await expect(page.getByTestId("mistake-list")).toContainText(
      list.active_count > 0 ? "错题" : "暂无",
    );

    await page.getByTestId("mistakes-to-review").click();
    await expect(page).toHaveURL(/\/journey\/review$/);
  });

  test("复习卡评分后写入下次复习时间", async ({ page, request }) => {
    await signInWithProgress(page, request, "mistakes");
    await page.goto("/journey/mistakes");

    const grade = page.locator('[data-testid^="review-grade-"]').first();
    if ((await grade.count()) === 0) return; // 无到期卡时无可评分项
    await grade.click();
    await expect(page.getByText(/下次 .* 天后复习/)).toBeVisible({ timeout: 15_000 });
  });
});
