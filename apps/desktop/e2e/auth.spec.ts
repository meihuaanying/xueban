import { expect, test } from "@playwright/test";

import { signInAsLearner, signInWithProgress } from "./journey-helpers";

/** T5.1 应用骨架与路由守卫 → 旅程制骨架 */
test.describe("P0 旅程骨架与路由守卫", () => {
  test("未登录访问旅程页跳转登录页", async ({ page }) => {
    await page.goto("/journey/today");
    await expect(page).toHaveURL(/\/login$/);
  });

  test("注册后进入旅程首站（6 站导航 + 当前用户）", async ({ page, request }) => {
    await signInAsLearner(page, request);
    await page.goto("/journey/today");

    const nav = page.getByRole("navigation", { name: "学习旅程" });
    await expect(nav).toBeVisible();
    for (const label of ["今日任务", "诊断", "规划", "学习单元", "错题复习", "复盘"]) {
      await expect(nav.getByText(label, { exact: true })).toBeVisible();
    }
    await expect(page.getByTestId("current-user")).toBeVisible();
    await expect(page.getByTestId("stage-today")).toBeVisible();
  });

  test("旅程导航按状态机推进：今日任务 → 诊断 → 规划", async ({ page, request }) => {
    await signInWithProgress(page, request, "today");
    await page.goto("/journey/today");

    await page.getByTestId("journey-advance").click();
    await expect(page.getByTestId("stage-diagnosis")).toBeVisible();

    await page.getByTestId("journey-advance").click();
    await expect(page.getByTestId("stage-plan")).toBeVisible();
  });

  test("未满足前置条件的阶段被禁用（禁止孤立跳转）", async ({ page, request }) => {
    await signInAsLearner(page, request, { stage: "today", hasProfile: true });
    await page.goto("/journey/today");

    const nav = page.getByRole("navigation", { name: "学习旅程" });
    await expect(nav.getByText("需先完成：完成首次诊断")).toBeVisible();
  });
});

/** P0 onboarding：选学段 → 自动切主题 → 首次诊断 */
test.describe("P0 onboarding 选学段", () => {
  test("选择小学学段自动切到儿童模式并进入诊断", async ({ page, request }) => {
    await signInAsLearner(page, request, { stage: "today" });
    await page.goto("/onboarding");

    await expect(page.getByTestId("onboarding")).toBeVisible();
    await page.getByTestId("onboarding-choose-primary").click();

    await expect(page.getByTestId("onboarding-theme")).toHaveText("儿童模式");
    await expect(page).toHaveURL(/\/journey\/diagnosis$/);
    expect(await page.evaluate(() => document.documentElement.dataset.theme)).toBe("kids");
  });

  test("选择高中学段保持专注模式", async ({ page, request }) => {
    await signInAsLearner(page, request, { stage: "today" });
    await page.goto("/onboarding");

    await page.getByTestId("onboarding-choose-senior").click();
    await expect(page.getByTestId("onboarding-theme")).toHaveText("专注模式");
    expect(await page.evaluate(() => document.documentElement.dataset.theme)).toBe("focus");
  });
});
