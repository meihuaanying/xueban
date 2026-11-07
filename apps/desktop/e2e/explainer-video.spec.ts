import { expect, test } from "@playwright/test";

import { signInWithProgress } from "./journey-helpers";

/**
 * §5.3 视频讲解端到端（真实后端 + 真实 MinIO，不 mock 任何接口）。
 *
 * 前置数据：dev 库已为知识地图首个节点 `math.senior.c01`（集合与常用逻辑）预生成
 * 一支 49 秒视频（`explainer/video/e75c1a8e...mp4`）。没有这支预生成视频时本用例
 * 会走「409 → 回落互动讲解」分支，因此断言同时接受「视频就绪」这一唯一预期：
 * 预生成数据缺失时用例应失败，而不是悄悄退化成互动讲解——否则视频链路根本没被验证。
 */
test.describe("高中视频讲解 · 知识地图节点", () => {
  test("知识地图 → 互动讲解 → 切视频 → 真实播放", async ({ page, request }) => {
    await signInWithProgress(page, request, "plan", "senior");
    await page.goto("/journey/plan");
    await expect(page.getByTestId("stage-plan")).toBeVisible();

    // 侧边栏与规划页各有一份知识地图，测试要走卡片这一份
    const card = page.getByTestId("knowledge-map-card");
    const node = card.getByTestId("kmap-node-math.senior.c01");
    await expect(node).toBeVisible({ timeout: 30_000 });
    await node.click();

    const dock = page.getByTestId("kmap-card-explainer");
    await expect(dock).toBeVisible();
    // 互动讲解可能还在排队（E2E 环境没有 worker）：pending 卡也能「直接看视频讲解」。
    // 视频是命中预生成缓存，不依赖互动页是否就绪。
    await dock.getByTestId("explainer-switch-video").click();

    const video = dock.locator("video");
    await expect(video).toBeVisible({ timeout: 30_000 });
    // 真实解码：metadata 到位且时长与预生成产物一致（49s）
    await expect
      .poll(() => video.evaluate((el) => (el as HTMLVideoElement).duration), {
        timeout: 30_000,
      })
      .toBeGreaterThan(10);
    const duration = await video.evaluate((el) => (el as HTMLVideoElement).duration);
    expect(duration).toBeGreaterThan(40);
    // 视频路径不应出现「回落互动」提示
    await expect(dock.getByTestId("explainer-notice")).toHaveCount(0);
  });
});
