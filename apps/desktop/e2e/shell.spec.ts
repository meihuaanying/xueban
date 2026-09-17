import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

import { apiGet, createAccount, seedTokens } from "./helpers";

interface SubscriptionBody {
  plan: string;
  trial_used: boolean;
}

interface CalendarBody {
  year: number;
  month: number;
  days: { day: string }[];
}

function blockingViolations(results: Awaited<ReturnType<AxeBuilder["analyze"]>>) {
  return results.violations
    .filter((violation) => violation.impact === "critical" || violation.impact === "serious")
    .map((violation) => ({
      id: violation.id,
      targets: violation.nodes.map((node) => node.target.join(" ")).slice(0, 6),
    }));
}

test.describe("T5.6 / T5.7 复盘与设置", () => {
  test("设置页订阅状态与 API 一致（含试用开通）", async ({ page, request }) => {
    const account = await createAccount(request);
    await seedTokens(page, account);
    await page.goto("/settings");

    await expect(page.getByTestId("account-phone")).toHaveText(account.phone);
    await expect(page.getByTestId("subscription-plan")).toHaveText("免费版");

    await page.getByRole("button", { name: "开通 7 天试用" }).click();
    await expect(page.getByTestId("subscription-plan")).toHaveText("试用中");

    const subscription = await apiGet<SubscriptionBody>(
      request,
      account,
      "/v1/billing/subscription",
    );
    expect(subscription.plan).toBe("trial");
    expect(subscription.trial_used).toBe(true);
  });

  test("复盘页日历与 API 月份一致", async ({ page, request }) => {
    const account = await createAccount(request);
    await seedTokens(page, account);
    await page.goto("/review");

    const now = new Date();
    await expect(page.getByTestId("calendar-month")).toHaveText(
      `${now.getFullYear()} 年 ${now.getMonth() + 1} 月`,
    );
    const calendar = await apiGet<CalendarBody>(
      request,
      account,
      `/v1/stats/calendar?year=${now.getFullYear()}&month=${now.getMonth() + 1}`,
    );
    await expect(page.getByTestId("calendar-grid").locator("> div")).toHaveCount(
      calendar.days.length,
    );
  });

  test("批改页与工具页可访问（含 V3 占位）", async ({ page, request }) => {
    const account = await createAccount(request);
    await seedTokens(page, account);

    await page.goto("/grading");
    await expect(page.getByRole("heading", { name: "批改中心" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "作文批阅" })).toBeVisible();

    await page.goto("/tools");
    await expect(page.getByRole("heading", { name: "学习工具" }).first()).toBeVisible();
    await expect(page.getByRole("tab", { name: "拍照搜题" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "编程判题" })).toBeVisible();
  });

  test("登录页与主布局 axe 扫描 0 critical / serious", async ({ page, request }) => {
    await page.goto("/login");
    const loginResults = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();
    expect(blockingViolations(loginResults)).toEqual([]);

    const account = await createAccount(request);
    await seedTokens(page, account);
    await page.goto("/settings");
    await expect(page.getByTestId("subscription-card")).toBeVisible();
    const appResults = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();
    expect(blockingViolations(appResults)).toEqual([]);
  });
});
