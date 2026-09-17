import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

import { registerAccount, seedTokens } from "./parents-helpers";

function blockingViolations(results: Awaited<ReturnType<AxeBuilder["analyze"]>>) {
  return results.violations
    .filter((violation) => violation.impact === "critical" || violation.impact === "serious")
    .map((violation) => ({
      id: violation.id,
      targets: violation.nodes.map((node) => node.target.join(" ")).slice(0, 6),
    }));
}

test.describe("T9.3 暗色模式与无障碍收口", () => {
  test("暗色模式切换并保持（localStorage 持久化）", async ({ page }) => {
    await page.goto("/");
    const html = page.locator("html");
    // 等待 React 水合后点击（水合前点击不会触发处理器）
    await expect(async () => {
      await page.getByTestId("theme-toggle").click();
      await expect(html).toHaveClass(/dark/, { timeout: 1000 });
    }).toPass({ timeout: 15_000 });

    await page.reload();
    await expect(html).toHaveClass(/dark/);

    await page.getByTestId("theme-toggle").click();
    await expect(html).not.toHaveClass(/dark/);
  });

  test("家长端与后台页暗色下 axe 0 critical / serious", async ({ page, request }) => {
    const parent = await registerAccount(request, { role: "parent" });
    await seedTokens(page, parent);
    await page.goto("/parents");
    await expect(async () => {
      await page.getByTestId("theme-toggle").click();
      await expect(page.locator("html")).toHaveClass(/dark/, { timeout: 1000 });
    }).toPass({ timeout: 15_000 });
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();
    expect(blockingViolations(results)).toEqual([]);
  });

  test("注册页与帮助页暗色下 axe 0 critical / serious", async ({ page }) => {
    for (const path of ["/register", "/help"]) {
      await page.goto(path);
      await expect(async () => {
        await page.getByTestId("theme-toggle").click();
        await expect(page.locator("html")).toHaveClass(/dark/, { timeout: 1000 });
      }).toPass({ timeout: 15_000 });
      const results = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
        .analyze();
      expect(blockingViolations(results), `${path} 存在对比度/结构问题`).toEqual([]);
    }
  });
});
