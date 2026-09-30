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
    for (let index = 0; index < 25 && (await done.count()) === 0; index += 1) {
      // 诊断页的题卡容器是 diagnosis-progress（练习页才是 unit-question）
      const how = await answerQuestionCard(page, { cardTestId: "diagnosis-progress" });
      expect(how, "题卡应提供选项或填空输入").not.toBe("none");
      await page.waitForTimeout(150);
    }
    await expect(done).toBeVisible({ timeout: 30_000 });

    await page.getByRole("button", { name: "生成学习规划" }).click();
    await expect(page).toHaveURL(/\/journey\/plan$/);

    const exams = await apiGet<{ exams: { exam_id: string; status: string }[] }>(
      request,
      account,
      "/v1/diagnosis/exams?limit=5",
    );
    expect(exams.exams.length).toBeGreaterThan(0);
  });
});
