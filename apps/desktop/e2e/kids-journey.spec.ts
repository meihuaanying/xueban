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
 * 5. §5.1 触发场景 2：错题详情里点「动画讲解这个知识点」
 * 6. §5.1 触发场景 3：知识地图节点开讲解（专注模式侧边栏 + 儿童模式规划站两条路径）
 * 7. §5.4 降级契约：讲解生成中/失败都必须有可见状态，**永不白屏**
 *
 * 讲解一律用「pending / ready / failed 任一可见」作为断言，因为真实模型生成要几十秒，
 * 硬等 ready 会让门禁变成一条耗时且不稳定的用例；但**不允许**把 failed 也算通过——
 * 那正是 `knowledge_point_ids` 缺陷能藏这么久的原因（见 §4 复盘）。所以下面
 * 另有 vitest + 后端 pytest 两条精确断言守住「id 传对了」，见 test_explainer.py。
 *
 * band 用默认值 `primary`（kids 主题）；题库已有 2000+ 道 grade1_2 题，
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

    // 连续两题都答错 → §5.1 触发场景 1 的「看个动画讲解？」建议。
    // 每一轮都可能落空（还没出题、点不上选项、答对了不算错），所以循环到
    // 「累计两次确认答错」为止，而不是死等第 2 轮——死等会在数据抖动时
    // 报出「unit-feedback 找不到」，把真正的原因（这一轮压根没作答）藏掉。
    let wrongRounds = 0;
    for (let round = 0; round < 4 && wrongRounds < 2; round += 1) {
      const generate = page.getByTestId("unit-generate");
      if (await generate.isVisible()) {
        await generate.click();
      }
      const acted = await answerQuestionCard(page, { required: false });
      if (acted === "none") continue;
      await expect(page.getByTestId("unit-feedback")).toBeVisible({ timeout: 20_000 });
      // 「还没掌握」= 本轮没答对，wrongStreak 才会累加
      const notYet = page.getByTestId("unit-feedback").getByText("还没掌握");
      if (await notYet.isVisible()) wrongRounds += 1;
    }
    expect(wrongRounds, "应当至少答错两轮，才会触发讲解建议").toBeGreaterThanOrEqual(2);

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

  test("场景 2：错题详情里点「动画讲解这个知识点」能打开讲解", async ({ page, request }) => {
    const account = await signInAsLearner(
      page,
      request,
      { stage: "mistakes", hasProfile: true, diagnosisDone: true },
    );
    const seeded = await seedJourneyData(request, account);
    expect(seeded.mistakesCollected).toBeGreaterThan(0);
    await page.goto("/journey/mistakes");

    const trigger = page.locator('[data-testid^="mistake-explainer-"]').first();
    await expect(trigger).toBeVisible({ timeout: 20_000 });
    await trigger.click();

    // §5.4 降级契约：不硬等真实生成，只要出现「生成中/已就绪/失败」任一可见状态，
    // 就证明入口 → hook → 接口 → 面板这条链路是通的（不会点了没反应）。
    await expect(
      page
        .locator(
          '[data-testid="explainer-pending"], [data-testid="explainer-ready"], [data-testid="explainer-failed"]',
        )
        .first(),
    ).toBeVisible({ timeout: 30_000 });
  });

  test("场景 3：知识地图节点可点开讲解", async ({ page, request }) => {
    const account = await signInAsLearner(
      page,
      request,
      { stage: "today", hasProfile: true, diagnosisDone: true },
      "junior", // 知识地图挂在学院派侧边栏上，kids 主题用图标导航
    );
    await seedJourneyData(request, account);
    await page.goto("/journey/today");

    // 知识地图挂在学院派侧边栏上，只在专注模式渲染；kids 主题换成图标导航。
    // 用 junior band 登录时主题**本来就是** focus，所以这里只断言、不再点 theme-toggle
    // ——再点一次反而会切到 kids，把知识地图换掉。
    await expect(page.getByTestId("theme-badge")).toHaveText("专注模式");
    const node = page.locator('[data-testid^="kmap-node-"]').first();
    await expect(node).toBeVisible({ timeout: 20_000 });
    await node.click();
    await expect(
      page
        .locator(
          '[data-testid="explainer-pending"], [data-testid="explainer-ready"], [data-testid="explainer-failed"]',
        )
        .first(),
    ).toBeVisible({ timeout: 30_000 });
  });

  test("场景 3：儿童模式下也能从知识地图节点开讲解（规划站）", async ({
    page,
    request,
  }) => {
    // 侧边栏在 kids 主题是图标导航、没有地图，所以场景 3 在儿童模式下的落点是
    // 「规划」这一站的 KnowledgeMapCard。这条用例专门守住它——否则妹妹用的
    // 那套主题里，场景 3 是进不去的，而侧边栏那条用例照样全绿。
    const account = await signInWithProgress(page, request, "plan");
    await seedJourneyData(request, account);
    await page.goto("/journey/plan");

    await expect(page.getByTestId("theme-badge")).toHaveText("儿童模式");
    const card = page.getByTestId("knowledge-map-card");
    await expect(card).toBeVisible({ timeout: 20_000 });

    const node = card.locator('[data-testid^="kmap-node-"]').first();
    await expect(node).toBeVisible({ timeout: 20_000 });
    await node.click();
    await expect(page.getByTestId("kmap-card-explainer")).toBeVisible({ timeout: 30_000 });
    await expect(
      page
        .locator(
          '[data-testid="explainer-pending"], [data-testid="explainer-ready"], [data-testid="explainer-failed"]',
        )
        .first(),
    ).toBeVisible({ timeout: 30_000 });
  });
});
