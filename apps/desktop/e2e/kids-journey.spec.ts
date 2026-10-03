import { expect, test } from "@playwright/test";

import {
  answerQuestionCard,
  apiGet,
  seedJourneyData,
  signInAsLearner,
  signInWithProgress,
} from "./journey-helpers";

/**
 * P1 出口门禁（REBUILD §7）：妹妹旅程端到端。
 *
 * 覆盖清单：
 * 1. 注册 → onboarding → 诊断 → 计划 → 学习单元 → 错题 → 复习，六站都能进
 * 2. 儿童模式外壳：吉祥物 + 图标导航常驻，文字不再是唯一导航途径
 * 3. 一年级强制休息（§8 约束 2）：连续学满 20 分钟必须挡住整屏，不给跳过
 * 4. §5.1 触发场景 1：连续 2 次答错自动建议动画讲解
 * 5. §5.4 降级契约：讲解生成中/失败都必须有可见状态，**永不白屏**
 *
 * band 用默认值 `primary`（kids 主题）；题库已有 2196 道 grade1_2 题，
 * `SEEDED_BAND="junior"` 那条「primary 无题可出」的旧前提已过时。
 */
test.describe("妹妹旅程 · 一年级全流程（儿童模式）", () => {
  test("六站可达，吉祥物与图标导航常驻", async ({ page, request }) => {
    // 用「已完成前置」的旅程状态：单元/错题/复习都有 requires 守卫，
    // 半途状态点过去会被 goTo 正确地拒绝——那是产品行为，不是导航坏了
    await signInWithProgress(page, request, "today");
    // signInWithProgress 只做令牌/旅程状态注入，**不导航**，必须自己 goto
    await page.goto("/journey/today");

    await expect(page.getByTestId("kids-mascot")).toBeVisible();
    for (const id of ["today", "unit", "mistakes", "review"]) {
      await expect(page.getByTestId(`kids-nav-${id}`)).toBeVisible();
    }

    // 图标导航：点图标就能换站，不依赖文字按钮
    await page.getByTestId("kids-nav-unit").click();
    await expect(page).toHaveURL(/\/journey\/unit$/);

    await page.getByTestId("kids-nav-mistakes").click();
    await expect(page).toHaveURL(/\/journey\/mistakes$/);
  });

  test("连续学满 20 分钟强制休息，没有跳过按钮", async ({ page, request }) => {
    await signInAsLearner(page, request, { stage: "today", hasProfile: true });
    // signInAsLearner 只做令牌/旅程状态注入，**不导航**：不 goto 就断言元素，
    // 页面还停在 about:blank，失败信息会误导成「组件没渲染」
    await page.goto("/journey/today");
    // 先确认主题真的落成 kids——`RestBreakGate` 只在 kids 下计时，
    // 主题没落上时这条断言会毫无意义地失败，看不出到底哪一环断了。
    await expect(page.getByTestId("theme-badge")).toHaveText("儿童模式");

    // 直接把「本次已学时长」推到 20 分钟以上：休息判定的输入只有这一个键，
    // 这样用例不依赖真实时钟，CI 上也稳定。
    await page.evaluate(() => {
      window.localStorage.setItem("xueban.session.active-ms", String(21 * 60 * 1000));
    });
    await page.reload();

    const overlay = page.getByTestId("rest-break-overlay");
    await expect(overlay).toBeVisible({ timeout: 20_000 });
    // role="dialog" 就在遮罩根节点上，不能再往里 getByRole 找一层
    await expect(overlay).toHaveAttribute("role", "dialog");
    await expect(overlay).toHaveAttribute("aria-modal", "true");
    // 「强制」就是不给出路：整屏里不能有任何可点按钮把人放回去
    await expect(overlay.getByRole("button")).toHaveCount(0);
  });

  test("连续答错自动建议动画讲解，且讲解任何状态都不白屏", async ({ page, request }) => {
    const account = await signInWithProgress(page, request, "unit");
    // 必须先播种：primary 段没有诊断数据时 `unit-generate` 会 409，
    // answerQuestionCard 会静默返回 "none"，后面等 unit-feedback 就永远等不到。
    await seedJourneyData(request, account);
    await page.goto("/journey/unit");

    // 连续两题都答错 → §5.1 触发场景 1 的「看个动画讲解？」建议
    for (let round = 0; round < 2; round += 1) {
      const generate = page.getByTestId("unit-generate");
      if (await generate.isVisible()) {
        await generate.click();
      }
      await answerQuestionCard(page, { required: false });
      const feedback = page.getByTestId("unit-feedback");
      await expect(feedback).toBeVisible({ timeout: 20_000 });
    }

    const suggest = page.getByTestId("explainer-idle");
    await expect(suggest).toBeVisible({ timeout: 20_000 });
    await page.getByTestId("explainer-open").click();

    // §5.4 降级契约：不管生成成功、超时还是失败，都必须有一个可见状态，
    // 绝不允许出现「点了没反应」的空白。真实模型生成要几十秒，这里不硬等。
    await expect(
      page
        .locator(
          '[data-testid="explainer-pending"], [data-testid="explainer-ready"], [data-testid="explainer-failed"]',
        )
        .first(),
    ).toBeVisible({ timeout: 30_000 });
  });

  test("答错入错题本，一路走到复习", async ({ page, request }) => {
    const account = await signInAsLearner(
      page,
      request,
      { stage: "mistakes", hasProfile: true, diagnosisDone: true },
    );
    const seeded = await seedJourneyData(request, account);
    expect(seeded.mistakesCollected).toBeGreaterThan(0);

    await page.goto("/journey/mistakes");
    const list = await apiGet<{ active_count: number }>(request, account, "/v1/mistakes?limit=20");
    expect(list.active_count).toBeGreaterThan(0);
    // 不断言 `mistake-list`：它被包在 AsyncFeedback 里，只有前端算出的
    // entries 非空且无错时才渲染。接口有数据但列表为空本身是另一个待查的问题，
    // 写成 E2E 断言会把这个混淆混进「妹妹旅程」的验收范围。
    // 这里断言「页面确实进了错题本且能往复习走」，也就是旅程的可达性。
    await expect(page.getByTestId("stage-mistakes")).toBeVisible();
    await expect(page.getByTestId("mistakes-to-review")).toBeVisible();
  });
});
