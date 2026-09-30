import { expect, test } from "@playwright/test";

import { apiGet, signInWithProgress } from "./journey-helpers";

/** T5.2 诊断与画像 → 旅程第 2 站（守护型诊断，选项来自后端契约） */
test.describe("旅程第 2 站 · 诊断", () => {
  test("完成诊断后展示诊断结果并可进入规划", async ({ page, request }) => {
    const account = await signInWithProgress(page, request, "diagnosis");
    await page.goto("/journey/diagnosis");

    await page.getByTestId("diagnosis-start").click();
    await expect(page.getByTestId("diagnosis-progress")).toBeVisible();

    // 逐题作答：选项按后端返回的键值渲染，答对或答错都推进进度
    for (let index = 0; index < 10; index += 1) {
      const option = page.locator('[data-testid^="option-"]').first();
      if ((await option.count()) === 0) break;
      await option.click();
      await expect(page.getByTestId("diagnosis-done")).toBeVisible({ timeout: 15_000 }).catch(() => {});
      if ((await page.getByTestId("diagnosis-done").count()) > 0) break;
    }

    await expect(page.getByTestId("diagnosis-done")).toBeVisible({ timeout: 30_000 });
    await page.getByRole("button", { name: "生成学习规划" }).click();
    await expect(page).toHaveURL(/\/journey\/plan$/);

    // 与后端交叉校验：诊断记录已落库
    const report = await apiGet<{ exams: { exam_id: string; status: string }[] }>(
      request,
      account,
      "/v1/diagnosis/exams?limit=5",
    );
    expect(report.exams.length).toBeGreaterThan(0);
  });
});
