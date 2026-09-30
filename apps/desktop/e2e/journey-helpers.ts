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

/** 注入登录态 + 旅程进度，让用例直接从指定阶段开始 */
export async function signInAsLearner(
  page: Page,
  request: APIRequestContext,
  flags?: JourneyFlags,
): Promise<TestAccount> {
  const account = await createAccount(request);
  await seedTokens(page, account);
  const state: JourneyFlags = flags ?? { stage: "today", hasProfile: true };
  await page.addInitScript((injected: { journey: JourneyFlags; theme: string }) => {
    window.localStorage.setItem("xueban.journey", JSON.stringify(injected.journey));
    window.localStorage.setItem("xueban.gradeBand", "primary");
    window.localStorage.setItem("xueban.theme", injected.theme);
    window.localStorage.setItem("xueban.mode", "light");
  }, { journey: state, theme: "kids" });
  return account;
}

/** 以已完成的旅程状态进入（除首站外都解锁） */
export async function signInWithProgress(
  page: Page,
  request: APIRequestContext,
  stage: JourneyFlags["stage"],
): Promise<TestAccount> {
  return signInAsLearner(page, request, {
    stage,
    hasProfile: true,
    diagnosisDone: true,
    planReady: true,
    unitVisited: true,
    mistakesLogged: true,
    reviewDone: true,
  });
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
