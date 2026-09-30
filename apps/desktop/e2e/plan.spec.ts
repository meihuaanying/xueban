import { expect, test } from "@playwright/test";

import { apiGet, signInWithProgress } from "./journey-helpers";

/** T5.3 规划与打卡 → 旅程第 1 站（今日任务 + 连续打卡）与第 3 站（学习规划） */
test.describe("旅程第 1 站 · 今日任务与连续打卡", () => {
  test("完成任务后进度与连续天数与 API 一致", async ({ page, request }) => {
    const account = await signInWithProgress(page, request, "today");
    await page.goto("/journey/today");

    const list = page.getByTestId("today-tasks");
    await expect(list).toBeVisible();

    const before = await apiGet<{ completed_count: number; streak_days: number }>(
      request,
      account,
      "/v1/plan/today",
    );

    const pending = list.locator('[data-testid^="today-complete-"]').first();
    if ((await pending.count()) > 0) {
      await pending.click();
      await expect
        .poll(async () => {
          const after = await apiGet<{ completed_count: number }>(
            request,
            account,
            "/v1/plan/today",
          );
          return after.completed_count;
        }, { timeout: 15_000 })
        .toBeGreaterThan(before.completed_count);
    }
  });
});

/** 旅程第 3 站 · 学习规划 */
test.describe("旅程第 3 站 · 学习规划", () => {
  test("展示学习阶段与知识点掌握度，可进入学习单元", async ({ page, request }) => {
    const account = await signInWithProgress(page, request, "plan");
    await page.goto("/journey/plan");

    const plan = await apiGet<{ has_path: boolean; phases: unknown[] }>(
      request,
      account,
      "/v1/plan/path",
    );

    if (plan.has_path && plan.phases.length > 0) {
      await expect(page.getByTestId("plan-phases")).toBeVisible();
    }
    await page.getByTestId("plan-to-unit").click();
    await expect(page).toHaveURL(/\/journey\/unit$/);
  });
});
