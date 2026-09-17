import { expect, test } from "@playwright/test";

import { randomPhone } from "./helpers";

test.describe("T5.1 应用骨架与路由守卫", () => {
  test("未登录访问受限页跳转登录页", async ({ page }) => {
    await page.goto("/tutor");
    await expect(page).toHaveURL(/\/login$/);
    await expect(page.getByRole("heading", { name: "登录" })).toBeVisible();
  });

  test("注册新账号 → 进入主布局（侧边栏 8 项 + 当前用户）", async ({ page }) => {
    const phone = randomPhone();
    await page.goto("/login");
    await page.getByRole("tab", { name: "注册" }).click();
    await page.getByLabel("手机号").fill(phone);
    await page.getByLabel("密码").fill("E2e-pass-1234");
    await page.getByLabel("昵称（选填）").fill("桌面端 E2E");
    await page.getByRole("button", { name: "注册并登录" }).click();

    await expect(page).toHaveURL(/\/diagnosis$/);
    const nav = page.getByRole("navigation", { name: "功能导航" });
    await expect(nav).toBeVisible();
    for (const label of ["诊断", "规划", "讲解", "练习", "批改", "复盘", "工具", "设置"]) {
      await expect(nav.getByRole("link", { name: new RegExp(label) })).toBeVisible();
    }
    await expect(page.getByTestId("current-user")).toHaveText("桌面端 E2E");
  });

  test("侧边栏可切换页面", async ({ page }) => {
    await page.goto("/login");
    const phone = randomPhone();
    await page.getByRole("tab", { name: "注册" }).click();
    await page.getByLabel("手机号").fill(phone);
    await page.getByLabel("密码").fill("E2e-pass-1234");
    await page.getByRole("button", { name: "注册并登录" }).click();
    await expect(page).toHaveURL(/\/diagnosis$/);

    await page.getByRole("navigation", { name: "功能导航" }).getByRole("link", { name: /规划/ }).click();
    await expect(page).toHaveURL(/\/plan$/);
    await expect(page.getByRole("heading", { name: "学习规划" })).toBeVisible();

    await page.getByRole("navigation", { name: "功能导航" }).getByRole("link", { name: /设置/ }).click();
    await expect(page).toHaveURL(/\/settings$/);
    await expect(page.getByTestId("subscription-card")).toBeVisible();
  });
});
