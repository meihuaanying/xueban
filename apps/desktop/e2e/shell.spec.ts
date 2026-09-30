import { expect, test } from "@playwright/test";

import { expectNoBlockingA11y, signInAsLearner, signInWithProgress } from "./journey-helpers";

/** T5.6 复盘 → 旅程第 6 站 */
test.describe("旅程第 6 站 · 复盘", () => {
  test("展示本周指标并可完成今日学习", async ({ page, request }) => {
    await signInWithProgress(page, request, "review");
    await page.goto("/journey/review");

    await expect(page.getByTestId("stage-review")).toBeVisible();
    await page.getByTestId("review-finish").click();
    await expect(page.getByTestId("review-finish")).toBeVisible();
  });
});

/** P0 双主题与可访问性门禁 */
test.describe("P0 双主题与可访问性", () => {
  test("主题切换在两套皮肤间生效（kids ⇄ focus）", async ({ page, request }) => {
    await signInAsLearner(page, request);
    await page.goto("/journey/today");

    const toggle = page.getByTestId("theme-toggle");
    await expect
      .poll(async () => page.evaluate(() => document.documentElement.dataset.theme))
      .toBe("kids");
    await toggle.click();
    await expect
      .poll(async () => page.evaluate(() => document.documentElement.dataset.theme))
      .toBe("focus");
  });

  test("儿童模式不提供深色（§4.1 约束）", async ({ page, request }) => {
    await signInAsLearner(page, request);
    await page.goto("/journey/today");

    const mode = page.getByTestId("mode-toggle");
    await expect(mode).toBeDisabled();
    await expect
      .poll(async () => page.evaluate(() => document.documentElement.classList.contains("dark")))
      .toBe(false);
  });

  test("专注模式可切深色", async ({ page, request }) => {
    await signInAsLearner(page, request, { stage: "today", hasProfile: true });
    await page.goto("/journey/today");

    await page.getByTestId("theme-toggle").click();
    await page.getByTestId("mode-toggle").click();
    await expect
      .poll(async () => page.evaluate(() => document.documentElement.classList.contains("dark")))
      .toBe(true);
  });

  test("登录页与旅程主布局 axe 0 critical / serious", async ({ page, request }) => {
    await page.goto("/login");
    await expectNoBlockingA11y(page);

    await signInAsLearner(page, request);
    await page.goto("/journey/today");
    await expectNoBlockingA11y(page);
  });

  test("儿童模式旅程页 axe 0 critical / serious", async ({ page, request }) => {
    await signInAsLearner(page, request, { stage: "today", hasProfile: true });
    await page.goto("/journey/today");
    await expectNoBlockingA11y(page);
  });
});
