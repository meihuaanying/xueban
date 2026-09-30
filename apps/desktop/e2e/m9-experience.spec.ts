import { expect, test } from "@playwright/test";

import { signInAsLearner, signInWithProgress } from "./journey-helpers";

/**
 * T9.1 多端同步 / T9.3 三态 / T9.4 新手引导 → 旅程化重写。
 * 原用例针对已归档的旧功能页（陪练中心、拍照搜题），
 * 对应能力在 P1 交付（E5：一年级用语音输入+点选式作答替代拍照搜题），此处不再覆盖。
 */
test.describe("旅程三态与加载反馈", () => {
  test("今日任务加载后展示任务列表或空态", async ({ page, request }) => {
    await signInAsLearner(page, request);
    await page.goto("/journey/today");

    const stage = page.getByTestId("stage-today");
    await expect(stage).toBeVisible();
    // 三态：加载中 → 列表/空态，最终必须脱离骨架屏
    await expect(page.getByTestId("today-tasks").or(page.getByText("暂无"))).toBeVisible({
      timeout: 20_000,
    });
  });

  test("错题复习页加载后展示错题本或空态", async ({ page, request }) => {
    await signInWithProgress(page, request, "mistakes");
    await page.goto("/journey/mistakes");
    await expect(page.getByTestId("mistake-list")).toBeVisible({ timeout: 20_000 });
  });
});

/** T9.4 新手引导：选学段 → 自动切主题 → 首次诊断（≤3 步） */
test.describe("新手引导到首次诊断", () => {
  test("选学段后自动切主题并落在诊断页", async ({ page, request }) => {
    await signInAsLearner(page, request, { stage: "today" });
    await page.goto("/onboarding");

    await page.getByTestId("onboarding-choose-primary").click();
    await expect(page).toHaveURL(/\/journey\/diagnosis$/);
    await expect(page.getByTestId("stage-diagnosis")).toBeVisible();
    await expect(page.getByTestId("diagnosis-start")).toBeVisible();
  });
});
