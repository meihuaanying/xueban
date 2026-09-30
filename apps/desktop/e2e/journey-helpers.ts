/**
 * 旅程 E2E 共享辅助（§7 P0 出口门禁）。
 * 职责：注册测试账号、注入登录态与旅程状态、直接查后端接口做交叉校验。
 * 原则：E2E 覆盖真实用户旅程（UI 操作），后端契约仍用 API 断言，不在测试里造 mock。
 */
import type { APIRequestContext, Page } from "@playwright/test";
import { expect } from "@playwright/test";

import { API_ORIGIN, apiGet, apiPost, createAccount, randomPhone, seedTokens } from "./helpers";

export { API_ORIGIN, apiGet, apiPost, createAccount, randomPhone, seedTokens };

export interface TestAccount {
  phone: string;
  password: string;
  accessToken: string;
  refreshToken: string;
}

export interface JourneyFlags {
  stage: "today" | "diagnosis" | "plan" | "unit" | "mistakes" | "review";
  hasProfile?: boolean;
  diagnosisDone?: boolean;
  planReady?: boolean;
  unitVisited?: boolean;
  mistakesLogged?: boolean;
  reviewDone?: boolean;
}

/**
 * 测试用学段。当前题库实况（psql 实测 questions 表）只有 `math/junior` 有 PUBLISHED 题，
 * `primary` / `senior` 会命中 409 DIAGNOSIS_NO_QUESTIONS（走题库建设中空态）。
 * 需要「诊断/规划」真实跑通链路的用例必须用 `junior`。
 */
export type LearnerBand = "primary" | "junior" | "senior";

const BAND_THEME: Record<LearnerBand, string> = {
  primary: "kids",
  junior: "focus",
  senior: "focus",
};

/** 有题库的学段：诊断与规划链路用它 */
export const SEEDED_BAND: LearnerBand = "junior";
/** 诊断题量，与后端 diagnosis_service.MIN_TARGET_COUNT 下限一致 */
const DIAGNOSIS_TARGET = 20;

/** 注入登录态 + 旅程进度，让用例直接从指定阶段开始 */
export async function signInAsLearner(
  page: Page,
  request: APIRequestContext,
  flags?: JourneyFlags,
  band?: LearnerBand,
): Promise<TestAccount> {
  const account = await createAccount(request);
  await seedTokens(page, account);
  const state: JourneyFlags = flags ?? { stage: "today", hasProfile: true };
  const skin = band ?? "primary";
  await page.addInitScript(
    (injected: { journey: JourneyFlags; band: string; theme: string }) => {
      window.localStorage.setItem("xueban.journey", JSON.stringify(injected.journey));
      window.localStorage.setItem("xueban.gradeBand", injected.band);
      window.localStorage.setItem("xueban.theme", injected.theme);
      window.localStorage.setItem("xueban.mode", "light");
    },
    { journey: state, band: skin, theme: BAND_THEME[skin] },
  );
  return account;
}

/** 以已完成的旅程状态进入（除首站外都解锁） */
export async function signInWithProgress(
  page: Page,
  request: APIRequestContext,
  stage: JourneyFlags["stage"],
  band?: LearnerBand,
): Promise<TestAccount> {
  return signInAsLearner(
    page,
    request,
    {
      stage,
      hasProfile: true,
      diagnosisDone: true,
      planReady: true,
      unitVisited: true,
      mistakesLogged: true,
      reviewDone: true,
    },
    band,
  );
}

/**
 * 在题卡上作答一题（兼容选择题与填空题）。
 *
 * 后端 seed 的题库 choice 与 fill 混排（`practice/generate` 实测第 2 题起 `options: null`），
 * 因此用例不能只找 `[data-testid^="option-"]`：遇到填空题必须走 `fill-input` + `fill-submit`。
 * 返回实际作答方式，供用例断言分支。
 */
export async function answerQuestionCard(
  page: Page,
  fillText = "17",
): Promise<"option" | "fill" | "none"> {
  const option = page.locator('[data-testid^="option-"]').first();
  if ((await option.count()) > 0 && (await option.isVisible().catch(() => false))) {
    await option.click();
    return "option";
  }

  const fillInput = page.getByTestId("fill-input");
  if ((await fillInput.count()) > 0 && (await fillInput.isVisible().catch(() => false))) {
    await fillInput.fill(fillText);
    await page.getByTestId("fill-submit").click();
    return "fill";
  }

  return "none";
}

/**
 * 造真实学习数据（方案 A）：调真实 API 跑通诊断与练习，让 UI 断言有真实数据可断言。
 * 不用 mock，也不写死返回；数据全部由后端产生，再与页面交叉校验。
 *
 * 注意：错题产生的 FSRS 卡按 `Again` 档设 `due_at = now + 10 分钟`（fsrs_service.AGAIN_MINUTES），
 * 因此**刚答错后 `/v1/review/due` 必然为 0**，到期复习卡的交互无法用造数得到；
 * 用例应对 `review-due` 断言「空态 + 容器存在」，到期卡评分交互另行覆盖。
 */
export interface SeededData {
  examId: string;
  diagnosisFinished: boolean;
  answered: number;
  mistakesCollected: number;
}

export async function seedJourneyData(
  request: APIRequestContext,
  account: TestAccount,
): Promise<SeededData> {
  let examId = "";
  let answered = 0;
  let diagnosisFinished = false;

  const start = await apiPost<DiagnosisStartBody>(
    request,
    account,
    "/v1/diagnosis/start",
    { subject: "math", stage: "junior", target_count: DIAGNOSIS_TARGET },
  );
  examId = start.exam_id;
  let question = start.question ?? null;

  while (question && answered < DIAGNOSIS_TARGET + 5) {
    const answer = pickAnswer(question.options, question.qtype, answered);
    const result = await apiPost<DiagnosisAnswerBody>(
      request,
      account,
      `/v1/diagnosis/${examId}/answer`,
      { question_id: question.id, answer },
    );
    answered += 1;
    diagnosisFinished = Boolean(result.finished);
    question = result.next_question ?? null;
    if (diagnosisFinished) break;
  }

  // 练习：故意选最后一个选项 / 填空填 0，制造错题供错题本断言
  let mistakesCollected = 0;
  for (let round = 0; round < 3 && mistakesCollected === 0; round += 1) {
    const generated = await apiPost<PracticeGenerateBody>(
      request,
      account,
      "/v1/practice/generate",
      { subject: "math", count: 5 },
    );
    for (const item of generated.questions ?? []) {
      const answer = pickAnswer(item.options, item.qtype, answered);
      const result = await apiPost<PracticeAnswerBody>(
        request,
        account,
        "/v1/practice/answer",
        { question_id: item.id, answer, source: "practice" },
      );
      if (result.mistake_collected) mistakesCollected += 1;
    }
  }

  return { examId, diagnosisFinished, answered, mistakesCollected };
}

/** 选择题取最后一个选项、填空题填 0：与实测 seed 数据一致，稳定制造错题 */
function pickAnswer(
  options: Record<string, string> | null | undefined,
  qtype: string | undefined,
  salt: number,
): string {
  if (!options || Object.keys(options).length === 0) return "0";
  const keys = Object.keys(options).sort();
  return keys[(keys.length - 1 + salt) % keys.length] ?? keys[0] ?? "0";
}

interface DiagnosisStartBody {
  exam_id: string;
  question?: DiagnosisQuestionBody | null;
}

interface DiagnosisQuestionBody {
  id: string;
  qtype?: string;
  options?: Record<string, string> | null;
}

interface DiagnosisAnswerBody {
  finished: boolean;
  next_question?: DiagnosisQuestionBody | null;
}

interface PracticeGenerateBody {
  questions?: DiagnosisQuestionBody[];
}

interface PracticeAnswerBody {
  mistake_collected: boolean;
}

/** 阻断 a11y 门禁：critical / serious 视为不通过 */
export async function expectNoBlockingA11y(page: Page) {
  const { AxeBuilder } = await import("@axe-core/playwright");
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  const blocking = results.violations.filter(
    (violation) => violation.impact === "critical" || violation.impact === "serious",
  );
  expect(blocking).toEqual([]);
}
