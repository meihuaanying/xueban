import { expect, test } from "@playwright/test";

import { API_ORIGIN, apiPost, createAccount, seedTokens } from "./helpers";

interface GenerateBody {
  questions: { id: string }[];
}

interface SessionBody {
  session_id: string;
  hint_level: number;
}

test.describe("T5.4 守护型讲解", () => {
  test("三层提示逐层解锁 + SSE 流式输出", async ({ page, request }) => {
    const account = await createAccount(request);
    await seedTokens(page, account);
    await page.goto("/tutor");

    await page.getByRole("button", { name: "获取一道题" }).click();
    await expect(page.getByTestId("tutor-stem")).toBeVisible({ timeout: 30_000 });
    await page.getByRole("button", { name: "开始守护型讲解" }).click();
    await expect(page.getByText("当前层级：未开始")).toBeVisible({ timeout: 30_000 });

    // 未开始前只能解锁第一层，第二、三层按钮不可用（前端防护）
    await expect(page.getByTestId("hint-level-1")).toBeEnabled();
    await expect(page.getByTestId("hint-level-2")).toBeDisabled();
    await expect(page.getByTestId("hint-level-3")).toBeDisabled();

    await page.getByTestId("hint-level-1").click();
    const first = page.getByTestId("tutor-messages").locator("div").filter({ hasText: "思路提示" }).first();
    await expect(first).toContainText("思路提示", { timeout: 30_000 });
    await expect(first).not.toContainText("完整解答");
    await expect(page.getByTestId("hint-level-2")).toBeEnabled();

    await page.getByTestId("hint-level-2").click();
    await expect(page.getByTestId("tutor-messages")).toContainText("关键步骤", { timeout: 30_000 });
    await expect(page.getByTestId("tutor-messages")).not.toContainText("完整解答");
    await expect(page.getByTestId("hint-level-3")).toBeEnabled();

    await page.getByTestId("hint-level-3").click();
    await expect(page.getByTestId("tutor-messages")).toContainText("完整解答", { timeout: 30_000 });
    await expect(page.getByText("当前层级：3 / 3")).toBeVisible();
  });

  test("服务端拒绝跳层（TUTOR_LEVEL_SKIPPED 400）", async ({ request }) => {
    const account = await createAccount(request);
    const generated = await apiPost<GenerateBody>(request, account, "/v1/practice/generate", {
      subject: "math",
      count: 1,
    });
    const questionId = generated.questions[0]?.id;
    expect(questionId).toBeTruthy();

    const session = await apiPost<SessionBody>(request, account, "/v1/tutor/session", {
      question_id: questionId,
    });
    const response = await request.post(
      `${API_ORIGIN}/v1/tutor/${session.session_id}/hint`,
      {
        headers: { Authorization: `Bearer ${account.accessToken}` },
        data: { level: 2 },
      },
    );
    expect(response.status()).toBe(400);
    const body = (await response.json()) as { code: string };
    expect(body.code).toBe("TUTOR_LEVEL_SKIPPED");
  });
});
