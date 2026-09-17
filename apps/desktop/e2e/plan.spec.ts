import { expect, test } from "@playwright/test";

import { apiGet, createAccount, seedTokens } from "./helpers";

interface TodayBody {
  tasks: { id: string; title: string; status: string }[];
  completed_count: number;
  total: number;
  all_completed: boolean;
  streak_days: number;
}

interface PathBody {
  has_path: boolean;
  phases: { name: string; title: string; knowledge_points: { id: string; name: string }[] }[];
}

test.describe("T5.3 规划与打卡", () => {
  test("完成任务 → 打卡 → 连续天数更新（与 API 一致）", async ({ page, request }) => {
    const account = await createAccount(request);
    await seedTokens(page, account);

    await page.goto("/plan");
    await expect(page.getByTestId("path-phase").first()).toBeVisible({ timeout: 30_000 });

    const before = await apiGet<TodayBody>(request, account, "/v1/plan/today");
    expect(before.all_completed).toBe(false);

    for (let guard = 0; guard < 10; guard += 1) {
      const completeButton = page.getByRole("button", { name: "完成任务" }).first();
      if ((await completeButton.count()) === 0) break;
      await completeButton.click();
      await expect(page.getByRole("button", { name: "完成任务" })).toHaveCount(
        Math.max(0, before.total - 1 - guard),
      );
    }

    const after = await apiGet<TodayBody>(request, account, "/v1/plan/today");
    expect(after.all_completed).toBe(true);
    expect(after.streak_days).toBeGreaterThanOrEqual(1);

    await expect(page.getByText(`${after.streak_days} 天`).first()).toBeVisible();
    await expect(page.getByText("已全部完成").first()).toBeVisible();

    const path = await apiGet<PathBody>(request, account, "/v1/plan/path");
    expect(path.has_path).toBe(true);
    await expect(page.getByTestId("path-phase")).toHaveCount(path.phases.length);
  });

  test("考期倒排生成三阶段计划", async ({ page, request }) => {
    const account = await createAccount(request);
    await seedTokens(page, account);

    await page.goto("/plan");
    const future = new Date();
    future.setDate(future.getDate() + 90);
    const examDate = future.toISOString().slice(0, 10);
    await page.locator("#exam-date").fill(examDate);
    await page.getByRole("button", { name: "生成倒排计划" }).click();
    await expect(page.getByTestId("countdown-result")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("countdown-result").getByRole("listitem")).toHaveCount(3);
    await expect(page.getByText("共 90 天")).toBeVisible();
  });
});
