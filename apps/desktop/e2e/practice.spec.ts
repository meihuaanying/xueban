import { expect, test } from "@playwright/test";

import {
  SEEDED_BAND,
  answerQuestionCard,
  apiGet,
  seedJourneyData,
  signInAsLearner,
  signInWithProgress,
} from "./journey-helpers";

/** 旅程第 4 站 · 学习单元：出题 → 作答 → 即时反馈 */
test.describe("旅程第 4 站 · 练习作答", () => {
  test("出题后可作答并显示即时反馈", async ({ page, request }) => {
    await signInWithProgress(page, request, "unit");
    await page.goto("/journey/unit");

    // 前置动作：必须先出题，否则题卡与选项不会出现
    await page.getByTestId("unit-generate").click();

    // 题目可能是选择题（options）或填空题（options 为 null），两者都要能作答
    const how = await answerQuestionCard(page);
    expect(how).not.toBe("none");

    const feedback = page.getByTestId("unit-feedback");
    await expect(feedback).toBeVisible({ timeout: 20_000 });
    await expect(feedback).toContainText(/答对了|还没掌握/);
  });
});

/** 旅程第 5 站 · 错题复习（FSRS 到期卡） */
test.describe("旅程第 5 站 · 错题复习", () => {
  test("错题本与 API 一致，可完成复习进入复盘", async ({ page, request }) => {
    // 造数：真实跑一遍诊断与练习（故意答错）产出错题，验证数据链路而不是空态
    const account = await signInAsLearner(
      page,
      request,
      { stage: "mistakes", hasProfile: true, diagnosisDone: true },
      SEEDED_BAND,
    );
    const seeded = await seedJourneyData(request, account);
    expect(seeded.mistakesCollected).toBeGreaterThan(0);

    await page.goto("/journey/mistakes");

    const list = await apiGet<{ active_count: number }>(request, account, "/v1/mistakes?limit=20");
    expect(list.active_count).toBeGreaterThan(0);

    const mistakeList = page.getByTestId("mistake-list");
    await expect(mistakeList).toBeVisible();
    await expect(mistakeList).toContainText("复习");

    await page.getByTestId("mistakes-to-review").click();
    await expect(page).toHaveURL(/\/journey\/review$/);
  });

  test("到期复习区常驻可见（有卡时可评分）", async ({ page, request }) => {
    await signInWithProgress(page, request, "mistakes");
    await page.goto("/journey/mistakes");

    // review-due 是常驻区块：有到期卡时列出可评分项，无卡时给出冷却提示
    await expect(page.getByTestId("review-due")).toBeVisible();

    const grade = page.locator('[data-testid^="review-grade-"]').first();
    if ((await grade.count()) === 0) return; // FSRS 再次评分有 10 分钟冷却，无卡即无可评分内容
    await grade.click();
    await expect(page.getByText(/下次 .* 天后复习/)).toBeVisible({ timeout: 15_000 });
  });
});
