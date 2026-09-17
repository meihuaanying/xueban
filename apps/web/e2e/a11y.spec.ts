import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const TARGETS = [
  { path: "/", name: "首页" },
  { path: "/pricing", name: "定价页" },
  { path: "/download", name: "下载页" },
  { path: "/help", name: "帮助中心" },
  { path: "/privacy", name: "隐私政策" },
  { path: "/minor-protection", name: "未成年人保护声明" },
  { path: "/register", name: "注册页" },
  { path: "/app", name: "学习中心（未登录态）" },
];

test.describe("无障碍扫描（T4.2，axe-core）", () => {
  for (const target of TARGETS) {
    test(`${target.name} 无 critical / serious 违规`, async ({ page }) => {
      await page.goto(target.path);
      const results = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
        .analyze();
      const blocking = results.violations.filter(
        (violation) => violation.impact === "critical" || violation.impact === "serious",
      );
      expect(
        blocking.map((violation) => ({
          id: violation.id,
          impact: violation.impact,
          nodes: violation.nodes.length,
          help: violation.help,
        })),
      ).toEqual([]);
    });
  }
});
