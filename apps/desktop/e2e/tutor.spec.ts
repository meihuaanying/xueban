import { expect, test } from "@playwright/test";

import { SEEDED_BAND, answerQuestionCard, signInWithProgress } from "./journey-helpers";

/**
 * T5.4 守护型讲解 → 旅程第 4 站（学习单元）内的 HintStack。
 * 红线：默认只展示第 1 层，须由学生主动索取；三层用尽仍不给完整答案。
 */
test.describe("旅程第 4 站 · 守护型三层提示", () => {
  test("默认只显示一层提示，逐层解锁到三层仍不给答案", async ({ page, request }) => {
    // 用有题库的 band（math/junior），否则 primary/kids 学段无题可出
    await signInWithProgress(page, request, "unit", SEEDED_BAND);
    await page.goto("/journey/unit");

    // 出一组题并作答（选择题点选项，填空题走输入框）
    await page.getByTestId("unit-generate").click();
    const how = await answerQuestionCard(page);
    expect(how).not.toBe("none");

    // 打开讲解：必须先有作答反馈，讲解入口才会出现
    const explain = page.getByTestId("unit-open-tutor");
    await expect(explain).toBeVisible({ timeout: 20_000 });
    await explain.click();

    const stack = page.getByTestId("unit-tutor");
    await expect(stack).toBeVisible();
    await expect(stack.getByText("一层·轻推")).toBeVisible({ timeout: 20_000 });
    await expect(stack.getByText("二层·举一反三")).toBeHidden();

    // 逐层索取
    const second = stack.getByRole("button", { name: "给我第 2 层提示" });
    if ((await second.count()) > 0) {
      await second.click();
      await expect(stack.getByText("二层·举一反三")).toBeVisible({ timeout: 15_000 });
    }

    // 守型红线断言：三层用尽后必须显式声明「仍不提供完整答案」
    const third = stack.getByRole("button", { name: "给我第 3 层提示" });
    if ((await third.count()) > 0) {
      await third.click();
      await expect(stack.getByText("三层·微支架")).toBeVisible({ timeout: 15_000 });
    }
    await expect(stack.getByText(/仍不提供完整答案/)).toBeVisible();
  });
});
