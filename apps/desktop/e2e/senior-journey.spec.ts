import { expect, test } from "@playwright/test";

import {
  API_BASE_URL_STORAGE_KEY,
  API_ORIGIN,
  answerQuestionCard,
  createAccount,
  seedTokens,
} from "./journey-helpers";

/**
 * 高中（女友）旅程端到端：注册 → onboarding 选高中/高一 → 诊断 → 规划 →
 * 学习单元 → 错题。
 *
 * 与 kids-journey.spec.ts 的差异：
 * - 不注入 `xueban.journey` / `xueban.gradeBand`：旅程从真实注册后的默认状态
 *   起步，学段与主题都由 onboarding 自己写入，避免测试预置掩盖切换缺陷。
 * - 不用 `seedJourneyData`：它固定 `stage=junior`，会把诊断/规划拉回初中题库。
 *
 * 题库实况（2026-10 dev 库实测）：senior/grade10 有 17 个知识点、647 道
 * PUBLISHED 题（choice/fill/judge 都有 options），诊断 20 题与练习 5 题都有
 * 余量，所以诊断与出题不做「题库建设中」的空态兜底断言。
 */
test.describe("高中（女友）旅程 · 高一全流程", () => {
  test("注册 → 选高中/高一 → 诊断 → 规划 → 学习单元 → 错题", async ({ page, request }) => {
    // 注册真实账号；只注入令牌与运行时 API 基址（VITE_API_BASE_URL 是 build 期
    // 内联的，不注入会打错端口），旅程状态保持空白，让 onboarding 成为第一步。
    const account = await createAccount(request);
    await seedTokens(page, account);
    await page.addInitScript(
      (injected: { key: string; origin: string }) => {
        window.localStorage.setItem(injected.key, injected.origin);
      },
      { key: API_BASE_URL_STORAGE_KEY, origin: API_ORIGIN },
    );

    // ---- 第 1 步：onboarding 选「高中」→「高一」----
    await page.goto("/onboarding");
    await expect(page.getByTestId("onboarding")).toBeVisible();
    await page.getByTestId("onboarding-choose-senior").click();
    await expect(page.getByTestId("onboarding-grades")).toBeVisible();
    await page.getByTestId("onboarding-choose-grade10").click();

    await expect(page).toHaveURL(/\/journey\/diagnosis$/);
    await expect(page.getByTestId("stage-diagnosis")).toBeVisible();
    // 高中走学院派皮肤：主题必须落成 focus，不能落到小学的 kids
    await expect(page.locator("html")).toHaveAttribute("data-theme", "focus");

    // ---- 第 2 步：真跑 20 题诊断（多留 5 轮余量）----
    await page.getByTestId("diagnosis-start").click();
    const done = page.getByTestId("diagnosis-done");
    for (let round = 0; round < 25; round += 1) {
      if (await done.isVisible()) break;
      // 选择题点选项、填空题填 17；作答往返期间会短暂没有可作答控件
      await answerQuestionCard(page, { required: false });
      await page.waitForTimeout(150);
    }
    await expect(done).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("diagnosis-to-plan")).toBeVisible();
    await page.getByTestId("diagnosis-to-plan").click();
    await expect(page).toHaveURL(/\/journey\/plan$/);

    // ---- 第 3 步：规划。有路径时断言阶段列表；后端只给空态时至少断言
    // 「还没有学习规划」卡片可见（两者都是产品定义的合法状态，不允许白屏）。
    await expect(page.getByTestId("stage-plan")).toBeVisible();
    const phases = page.getByTestId("plan-phases");
    const emptyPlan = page.getByText("还没有学习规划", { exact: true });
    await expect(phases.or(emptyPlan)).toBeVisible({ timeout: 30_000 });

    // ---- 第 4 步：学习单元。有路径时点状态机按钮（planReady 由它写入）；
    // 空态下没有该按钮，直接进单元页（路由层不做前置拦截）。
    if (await phases.isVisible()) {
      await page.getByTestId("plan-to-unit").click();
    } else {
      await page.goto("/journey/unit");
    }
    await expect(page).toHaveURL(/\/journey\/unit$/);
    await expect(page.getByTestId("stage-unit")).toBeVisible();

    await page.getByTestId("unit-generate").click();
    await expect(page.getByTestId("unit-question")).toBeVisible({ timeout: 30_000 });
    const acted = await answerQuestionCard(page, { required: false });
    expect(acted, "出题后应能识别到选项或填空控件").not.toBe("none");
    await expect(page.getByTestId("unit-feedback")).toBeVisible({ timeout: 20_000 });

    // ---- 第 5 步：错题本主区可达（列表是否为空取决于上一题对错，不断言）----
    await page.goto("/journey/mistakes");
    await expect(page.getByTestId("stage-mistakes")).toBeVisible();
  });
});
