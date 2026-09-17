import { expect, test } from "@playwright/test";

import { API_ORIGIN, authHeaders, bindChild, completeParentTask, registerAccount, seedTokens } from "./parents-helpers";

test.describe("T7.1 家长端", () => {
  test("家长绑定孩子 → 看板 / 防沉迷 / 亲子任务 / 免登录链接", async ({ page, request }) => {
    const parent = await registerAccount(request, { role: "parent" });
    const child = await registerAccount(request, { role: "student" });
    await bindChild(request, parent, child.phone);

    // 孩子先完成一条系统任务（亲子任务闭环的前半段）
    const tasksResponse = await request.get(
      `${API_ORIGIN}/v1/parents/tasks?child_id=${child.id}`,
      { headers: authHeaders(parent) },
    );
    const tasks = (await tasksResponse.json()) as { tasks: { id: string; status: string }[] };
    expect(tasks.tasks.length).toBeGreaterThanOrEqual(2);
    await completeParentTask(request, child, tasks.tasks[0]!.id);

    await seedTokens(page, parent);
    await page.goto("/parents");

    await expect(page.getByTestId("parents-page")).toBeVisible();
    await expect(page.getByTestId("parent-dashboard")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText("连续打卡")).toBeVisible();

    // 防沉迷：保存设置（需家长密码）
    await page.getByTestId("parent-password").fill(parent.password);
    await page.getByTestId("save-controls").click();
    await expect(page.getByText("已保存，服务端即时生效。")).toBeVisible();

    // 安全报告区块可见
    await expect(page.getByTestId("parent-safety")).toBeVisible();

    // 亲子任务：待确认 → 确认完成
    await expect(page.getByTestId("parent-task").first()).toBeVisible();
    await page.getByRole("button", { name: "确认完成" }).first().click();
    await expect(page.getByText("已确认").first()).toBeVisible();

    // 免登录链接：生成 → 打开 → 吊销
    await page.getByRole("button", { name: "生成免登录链接" }).click();
    const linkText = await page.getByTestId("share-link").textContent();
    expect(linkText).toContain("/parents/view/");

    const sharedPage = await page.context().newPage();
    await sharedPage.goto(linkText!);
    await expect(sharedPage.getByTestId("shared-dashboard")).toBeVisible();
    await expect(sharedPage.getByText("掌握度分布")).toBeVisible();
    await sharedPage.close();

    await page.getByRole("button", { name: "吊销链接" }).click();
    await expect(page.getByTestId("share-link")).toHaveCount(0);
  });

  test("RBAC：家长不可查看他人孩子数据（接口 403）", async ({ request }) => {
    const parentA = await registerAccount(request, { role: "parent" });
    const parentB = await registerAccount(request, { role: "parent" });
    const childB = await registerAccount(request, { role: "student" });
    await bindChild(request, parentB, childB.phone);

    const response = await request.get(`${API_ORIGIN}/v1/parents/children/${childB.id}/dashboard`, {
      headers: authHeaders(parentA),
    });
    expect(response.status()).toBe(403);
    expect(((await response.json()) as { code: string }).code).toBe("PARENT_CHILD_FORBIDDEN");
  });

  test("未登录访问家长端引导注册", async ({ page }) => {
    await page.goto("/parents");
    await expect(page.getByText("请先登录家长账号")).toBeVisible();
    await expect(page.getByRole("link", { name: "注册家长账号" })).toBeVisible();
  });
});
