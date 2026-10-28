import { expect, test } from "@playwright/test";

import { signInWithProgress } from "./journey-helpers";

/**
 * 新高考数学 19 题模考（P3 交付面）。
 *
 * 只验证组卷 → 作答 → 交卷 → 报告这一段确定性链路：
 * 解答题批改依赖真实 LLM，E2E 的 mock provider 不覆盖（由后端单测钉住）。
 * 组卷依赖 dev 题库已有多选/解答题，见 scripts/backfill_qtypes.py。
 */
test.describe("高中专项 · 19 题结构模考", () => {
  test("复盘页进入模考，按 19 题组卷并交卷出客观分", async ({ page, request }) => {
    await signInWithProgress(page, request, "review", "senior");

    await page.goto("/journey/review");
    await expect(page.getByTestId("review-mock-exam-card")).toBeVisible();
    await page.getByTestId("review-mock-exam").click();
    await expect(page).toHaveURL(/\/journey\/mock-exam$/);

    await page.getByTestId("mock-exam-start").click();
    await expect(page.getByTestId("mock-exam-runner")).toBeVisible({ timeout: 30_000 });

    // 8 单选 + 3 多选 + 3 填空 + 5 解答
    for (let order = 1; order <= 19; order += 1) {
      await expect(page.getByTestId(`mock-exam-jump-${order}`)).toBeVisible();
    }

    // 第 1 题是单选：选 A 后交卷
    await page.getByTestId("option-A").click();
    await expect(page.getByTestId("mock-exam-progress")).toContainText("已答 1");
    await page.getByTestId("mock-exam-submit").click();

    await expect(page.getByTestId("mock-exam-report")).toBeVisible({ timeout: 30_000 });
    // 解答题未批改前不冒充 150 制总分
    await expect(page.getByTestId("mock-exam-pending")).toBeVisible();
    await expect(page.getByTestId("mock-exam-objective-diagnoses")).toBeVisible();
    // 解答题保持卷面全局题号（15~19），与作答页题号一致
    await expect(page.getByTestId("subjective-15")).toBeVisible();
  });
});
