import { expect, test } from "@playwright/test";

import {
  SEEDED_BAND,
  answerQuestionCard,
  apiGet,
  signInAsLearner,
} from "./journey-helpers";

test.describe("旅程第 2 站 · 诊断", () => {
  test("完成诊断后展示诊断结果并可进入规划", async ({ page, request }) => {
    // 诊断链路要真跑 20 题（后端 MIN_TARGET_COUNT=20），且题库仅有 math/junior，
    // 因此用 SEEDED_BAND 登录；旅程状态停在「未完成诊断」，由用例在 UI 上推进。
    const account = await signInAsLearner(
      page,
      request,
      { stage: "diagnosis", hasProfile: true, diagnosisDone: false },
      SEEDED_BAND,
    );

    await page.goto("/journey/diagnosis");
    await page.getByTestId("diagnosis-start").click();
    await expect(page.getByTestId("diagnosis-progress")).toBeVisible();

    const done = page.getByTestId("diagnosis-done");
    for (let index = 0; index < 25; index += 1) {
      if ((await done.count()) > 0) break;
      // required:false —— 最后一题提交后题卡会卸载（无题可答）＝卷面结束，由下方 done 断言兜底
      const how = await answerQuestionCard(page, { required: false });
      if (how === "none") break;
      await page.waitForTimeout(150);
    }
    await expect(done).toBeVisible({ timeout: 30_000 });

    await page.getByRole("button", { name: "生成学习规划" }).click();
    await expect(page).toHaveURL(/\/journey\/plan$/);

    // 与后端交叉校验：诊断结果已落库（掌握度从 has_data=false 变为 true）
    // 注意：不存在「诊断列表」端点（/v1/exams 是 POST 创建限时模考），
    // 诊断 exam_id 只在 React state 内，故用 profile/mastery 做落库校验。
    const mastery = await apiGet<{ has_data: boolean; points: unknown[] }>(
      request,
      account,
      "/v1/profile/mastery?subject=math",
    );
    expect(mastery.has_data).toBe(true);
    expect(mastery.points.length).toBeGreaterThan(0);
  });
});
