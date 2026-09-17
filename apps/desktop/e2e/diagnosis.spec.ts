import { expect, test, type APIRequestContext } from "@playwright/test";

import { apiGet, createAccount, seedTokens, type TestAccount } from "./helpers";

interface DiagnosisStartBody {
  exam_id: string;
  progress: { answered: number; total: number };
}

interface DiagnosisReportBody {
  has_data: boolean;
  points: { name: string; mastery: number }[];
}

test.describe("T5.2 诊断与画像", () => {
  test("完成 20 题诊断 → 报告雷达图与 API 数据一致", async ({ page, request }) => {
    const account: TestAccount = await createAccount(request);
    await seedTokens(page, account);

    await page.goto("/diagnosis");
    const startPromise = page.waitForResponse((response) =>
      response.url().includes("/v1/diagnosis/start"),
    );
    await page.getByRole("button", { name: "开始诊断" }).click();
    const startBody = (await (await startPromise).json()) as DiagnosisStartBody;
    const total = startBody.progress.total;
    expect(total).toBe(20);

    for (let index = 0; index < total; index += 1) {
      const optionA = page.getByTestId("diagnosis-option-A");
      if ((await optionA.count()) > 0) {
        await optionA.click();
      } else {
        await page.locator("#answer").fill("1");
      }
      await page.getByRole("button", { name: "提交答案" }).click();
      if (index < total - 1) {
        // 非最后一题：提交后展示对错反馈，再进入下一题
        await expect(page.getByTestId("diagnosis-feedback")).toBeVisible();
        await page.getByRole("button", { name: "下一题" }).click();
        await expect(page.getByTestId("diagnosis-feedback")).toBeHidden();
      }
      // 最后一题提交后直接进入报告阶段（下方断言雷达图）
    }

    await expect(page.getByTestId("diagnosis-radar")).toBeVisible({ timeout: 30_000 });
    const report = await apiGet<DiagnosisReportBody>(
      request as APIRequestContext,
      account,
      `/v1/diagnosis/${startBody.exam_id}/report`,
    );
    expect(report.has_data).toBe(true);
    expect(report.points.length).toBeGreaterThan(0);

    // 雷达图与明细表均来自同一份 API 数据：逐项核对知识点名称
    for (const point of report.points.slice(0, 8)) {
      await expect(page.getByText(point.name).first()).toBeVisible();
    }
    const rows = page.getByTestId("mastery-row");
    await expect(rows).toHaveCount(report.points.length);

    await page.getByRole("link", { name: "去规划页生成学习路径" }).click();
    await expect(page).toHaveURL(/\/plan$/);
  });
});
