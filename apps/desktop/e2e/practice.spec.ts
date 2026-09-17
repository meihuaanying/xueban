import { expect, test } from "@playwright/test";

import { apiGet, apiPost, createAccount, seedTokens, type TestAccount } from "./helpers";

interface GenerateBody {
  questions: { id: string; options: Record<string, string> | null }[];
  weak_count: number;
  weak_ratio: number;
}

interface ObjectiveBody {
  is_correct: boolean;
  correct_answer: string;
}

interface MistakeBody {
  active_count: number;
  mastered_count: number;
  entries: { id: string; state: string; question: { id: string } }[];
}

interface RepracticeBody {
  questions: { id: string; options: Record<string, string> | null }[];
}

function otherOption(correct: string): string {
  return ["A", "B", "C", "D"].find((key) => key !== correct) ?? "B";
}

test.describe("T5.5 练习与错题本闭环", () => {
  test("答错 → 入错题本 → 重练答对 → 移出错题本", async ({ page, request }) => {
    const account: TestAccount = await createAccount(request);
    await seedTokens(page, account);
    await page.goto("/practice");

    const generatePromise = page.waitForResponse((response) =>
      response.url().includes("/v1/practice/generate"),
    );
    await page.getByTestId("generate-practice").click();
    const generated = (await (await generatePromise).json()) as GenerateBody;
    const question = generated.questions[0];
    if (!question) throw new Error("练习生成未返回题目");
    await expect(page.getByTestId("practice-question")).toBeVisible();

    // 用批改接口取得正确答案，再故意答错（保证错题入本确定性）
    const graded = await apiPost<ObjectiveBody>(request, account, "/v1/grading/objective", {
      question_id: question.id,
      answer: "__deliberately_wrong__",
    });
    expect(graded.is_correct).toBe(false);

    if (question.options) {
      await page.getByTestId(`practice-option-${otherOption(graded.correct_answer)}`).click();
    } else {
      await page.getByTestId("practice-answer-input").fill("__wrong_answer__");
    }
    await page.getByRole("button", { name: "提交答案" }).click();

    await expect(page.getByTestId("practice-feedback")).toContainText("回答错误");
    await expect(page.getByTestId("practice-feedback")).toContainText("已加入错题本");
    await expect(page.getByTestId("mistake-entry").first()).toBeVisible();

    const mistakes = await apiGet<MistakeBody>(request, account, "/v1/mistakes?limit=20");
    expect(mistakes.entries.some((entry) => entry.question.id === question.id)).toBe(true);

    // 重练并答对 → 移出错题本
    const repracticePromise = page.waitForResponse((response) =>
      response.url().includes("/v1/mistakes/repractice"),
    );
    await page.getByRole("button", { name: "错题重练" }).click();
    const repractice = (await (await repracticePromise).json()) as RepracticeBody;
    const retryQuestion = repractice.questions[0];
    if (!retryQuestion) throw new Error("错题重练未返回题目");
    await expect(page.getByTestId("repractice-panel")).toBeVisible();

    const retryGraded = await apiPost<ObjectiveBody>(request, account, "/v1/grading/objective", {
      question_id: retryQuestion.id,
      answer: "__probe__",
    });
    if (retryQuestion.options) {
      await page.getByTestId(`repractice-option-${retryGraded.correct_answer}`).click();
    } else {
      await page.getByTestId("repractice-answer-input").fill(retryGraded.correct_answer);
    }
    await page.getByRole("button", { name: "提交重练" }).click();
    await expect(page.getByTestId("repractice-panel")).toContainText("回答正确", {
      timeout: 30_000,
    });

    const after = await apiGet<MistakeBody>(request, account, "/v1/mistakes?limit=20");
    expect(after.mastered_count).toBeGreaterThanOrEqual(1);
    const retriedEntryId = mistakes.entries.find((entry) => entry.question.id === retryQuestion.id)?.id;
    if (retriedEntryId) {
      const stillActive = after.entries.find((entry) => entry.id === retriedEntryId);
      expect(stillActive?.state ?? "mastered").not.toBe("active");
    }
  });

  test("生成练习的薄弱题占比不低于 60%（F-17）", async ({ request }) => {
    const account = await createAccount(request);
    const generated = await apiPost<GenerateBody>(request, account, "/v1/practice/generate", {
      subject: "math",
      count: 10,
    });
    expect(generated.questions.length).toBeGreaterThan(0);
    expect(generated.weak_ratio).toBeGreaterThanOrEqual(0.6);
  });
});
