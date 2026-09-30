import { expect, test } from "@playwright/test";

import { SEEDED_BAND, signInAsLearner } from "./journey-helpers";

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

  test("旅程导航按状态机推进：今日任务 → 诊断", async ({ page, request }) => {
    // 只置「已建立档案」，diagnosisDone 仍为 false ⇒ nextStage 返回 diagnosis。
    // 若用 signInWithProgress（6 个布尔全 true），today 的下一站是 unit 而非 diagnosis。
    await signInAsLearner(page, request, { stage: "today", hasProfile: true });
    await page.goto("/journey/today");

    await page.getByTestId("journey-advance").click();
    await expect(page.getByTestId("stage-diagnosis")).toBeVisible();
    await expect(page).toHaveURL(/\/journey\/diagnosis$/);
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
    // 初始学段显式用 focus 主题（SEEDED_BAND），否则 helper 缺省 primary 会预置 kids，
    // 「选择前是专注模式」就无从验证——这条用例要证明的是「切换」而不是「恰好已是」。
    await signInAsLearner(page, request, { stage: "today" }, SEEDED_BAND);
    await page.goto("/onboarding");

    await expect(page.getByTestId("onboarding")).toBeVisible();
    // 选择前：专注模式
    await expect(page.getByTestId("onboarding-theme")).toContainText("专注模式");

    await page.getByTestId("onboarding-choose-primary").click();

    // 选学段即自动切主题并进入首站诊断（旅程状态机驱动跳转）
    await expect(page).toHaveURL(/\/journey\/diagnosis$/);
    await expect(page.getByTestId("stage-diagnosis")).toBeVisible();
    await expect
      .poll(() => page.evaluate(() => document.documentElement.dataset.theme))
      .toBe("kids");
    await expect(page.getByTestId("theme-badge")).toHaveText("儿童模式");
  });

  test("选择高中学段保持专注模式", async ({ page, request }) => {
    // 同样从 focus 主题起步，验证选高中学段不会切走
    await signInAsLearner(page, request, { stage: "today" }, SEEDED_BAND);
    await page.goto("/onboarding");

    await page.getByTestId("onboarding-choose-senior").click();

    await expect(page).toHaveURL(/\/journey\/diagnosis$/);
    await expect
      .poll(() => page.evaluate(() => document.documentElement.dataset.theme))
      .toBe("focus");
    await expect(page.getByTestId("theme-badge")).toHaveText("专注模式");
  });
});
