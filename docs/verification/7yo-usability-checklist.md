# 7 岁可用性检查单（学伴 XueBan · 一二年级儿童模式）

- **被测对象**：7 岁左右的一年级女生，用真人试用的那套产品
- **对应规格**：`REBUILD.md` §4.1（儿童主题）+ §6.1（题型 P1）+ §7（P1 出口门禁）
- **检查日期**：2026-10-03
- **检查方式**：逐条对**代码与设计 token**取证，不靠印象。凡是「看起来做了」的，一律以 `文件:行号` + 实测值为准；取不到证据的直接判 ❌ 并写明后果。
- **姊妹文档**：`RB_P1_2026-10-03.md`（P1 验证报告）。本单是那份报告 §6「7 岁可用性检查单」那一行的展开。

> 纪律：本单里每一条 ✅ 都必须有取证位置。历史上出现过「凭未验证的推断把 ✅ 写进报告」的事，
> 所以宁可留 ⬜ 也不写没有出处的 ✅。

---

## 总览

| # | 检查项 | 规格出处 | 结论 |
|---|---|---|---|
| 1 | 正文基准字号 ≥18px | §4.1 | ✅ 18px |
| 2 | 辅助文字不小于 15px | §4.1（推导） | ✅ 最小 15.4px |
| 3 | 点击热区 ≥48px | §4.1 / §7 | ✅ 48px |
| 4 | 圆角 ≥12px | §4.1 | ✅ 19.2px |
| 5 | 主色为明黄 / 天蓝 / 草绿 | §4.1 | ✅ |
| 6 | 吉祥物「小伴」在场 | §4.1 | ✅ 🐼 |
| 7 | 所有正文支持 TTS 朗读 | §4.1 | ⚠️ 主体已覆盖，导航提示未覆盖 |
| 8 | 答对有正反馈动效 | §4.1 / §7 | ✅ 撒花 |
| 9 | 不提供深色模式 | §4.1 | ✅ E2E 有守卫 |
| 10 | 导航不依赖文字识别 | §7 | ✅ emoji 图标为主视觉 |
| 11 | 一年级全部题干可朗读 | §6.1 | ✅ |
| 12 | 一年级 20 分钟强制休息 | §8 约束 2 | ✅ 无跳过按钮 |
| 13 | 关键内容对比度达 WCAG AA | §4.1（推导） | ✅ E2E axe 0 critical/serious |

**13 项中 11 项 ✅、1 项 ⚠️、0 项 ❌。** 唯一待补的是第 7 项的导航提示（见下）。

---

## 1. 正文基准字号 ≥18px —— ✅

| 项 | 值 | 取证 |
|---|---|---|
| kids 档正文基准 | **18px** | `packages/config/tokens/theme.css:396` `--type-base: 1.125rem` |
| 主题旋钮 | `--font-scale: 1.2857`（14px × 1.2857 = 18px） | 同上 `:387` |
| 行高 | `--leading: 1.7`（儿童档放宽） | 同上 `:390` |
| 组件用法 | 统一 `text-app` / `text-app-md` / `text-app-lg`，不写死 px | `packages/config/tokens/theme.css:293-308`（`--text-app-*` 组） |

字号只在 token 里定义一处，主题切换靠 `--font-scale` 统一放大，所以「kids 下变 18px」是**结构性保证**，不是逐个组件手改的。

## 2. 辅助文字不小于 15px —— ✅

kids 档最小字阶 `--type-xs: 0.96rem` = **15.4px**（`theme.css:394`）。逐档：

| 字阶 | kids 值 | 对应类 |
|---|---|---|
| xs | 15.4px | `text-app-xs` |
| sm | 16.7px | `text-app-sm` |
| **base** | **18px** | `text-app` |
| md | 19.3px | `text-app-md` |
| lg | 23.1px | `text-app-lg` |
| xl | 28.3px | `text-app-xl` |
| 2xl | 36px | `text-app-2xl` |
| 3xl | 46.4px | `text-app-3xl` |

⚠️ **本轮修的一处**：`journey-blocks.tsx` 的 `JourneyStepper` 里「当前：第 N 站」「下一站：X」原先在 kids 下仍用 `text-app-xs`（15.4px）。这是**导航状态信息**，7 岁孩子读它本就吃力，小字更读不清。已改成 kids 下用 `text-app`（18px）、其余档保持 `text-app-xs`，不牺牲专注模式的紧凑感。

## 3. 点击热区 ≥48px —— ✅

| 项 | 值 | 取证 |
|---|---|---|
| kids 档最小热区 | **48px** | `theme.css:547` `--tap-min: 48px` |
| 默认档 | 32px（成人档刻意更紧凑） | `theme.css:323` |
| 组件写法 | 所有可点元素带 `min-h-[var(--tap-min)]` | 见下方清单 |

kids 档逐个可点元素的 `min-h-[var(--tap-min)]` 使用点（全部经 grep 核对）：
- `packages/ui/src/learning/explainer-frame.tsx:79`、`:86`（「看懂了 / 还是不懂」）
- `packages/ui/src/learning/question-card.tsx`（选项按钮）
- `apps/desktop/src/components/journey-nav.tsx`（阶段导航）
- `apps/desktop/src/components/kids-navigation.tsx`（kids 图标导航）
- `apps/desktop/src/components/rest-break.tsx`（休息提示区）

**为什么用 token 而不是写死 48px**：写死会在专注模式也强制 48px，把桌面端的信息密度拉垮；用 `--tap-min` 则「儿童 48 / 成人 32」由主题一处决定。

## 4. 圆角 ≥12px —— ✅

| 项 | 值 | 取证 |
|---|---|---|
| kids 档卡片圆角 | **19.2px** | `theme.css:410` `--r-card: 1.2rem` |
| kids 档控件圆角 | 12.8px | `theme.css:411` `--r-control: 0.8rem` |
| 主题旋钮 | `--radius-scale: 1.6` | `theme.css:388` |

## 5. 主色为明黄 / 天蓝 / 草绿 —— ✅

kids 档（`theme.css:425-445`）：

| 语义 | 值 | 观感 |
|---|---|---|
| `--primary` | `#ffc53d` | **明黄** |
| `--secondary` | `#e8f5ff` / 前景 `#0b5a96` | **天蓝** |
| `--success` | `#22c55e` | **草绿** |
| `--muted` | `#fff4d6` | 暖米底 |

对比度是算过的，不是拍脑袋：`--muted-foreground: #7f6334` 上有注释（`:432`）说明暖棕次要文字在 sunken 底（`#fbe9bd`）上必须 ≥4.5:1，`#8a6d3b` 只有 4.04 所以换成了 `#7f6334`。

## 6. 吉祥物「小伴」在场 —— ✅

`apps/desktop/src/components/kids-navigation.tsx` 的 `KidsMascot`，testid `kids-mascot`，内容 🐼 + 「小伴」二字 + 可选 TTS 朗读「小伴在这儿，我们一起学」。

- 只在 `theme === "kids"` 时渲染（`app-layout.tsx`）
- 朗读的是**固定欢迎语**而不是整页正文——孩子迷路时有声音说「我在」比每次念整页有用
- 覆盖：`kids-navigation.test.tsx` 8 条 + `kids-journey.spec.ts` 用例 1 的 E2E 断言

## 7. 所有正文支持 TTS 朗读 —— ⚠️

**已覆盖（kids 档自动带朗读）**：

| 位置 | 机制 | 取证 |
|---|---|---|
| 每个阶段页的标题 + 简介 | `StageShell` 的 `speakable` 开关 | `apps/desktop/src/components/stage-shell.tsx:55` `<AudioButton text={\`${heading}。${intro}\`} />` |
| 题干 | `QuestionCard` 的 `speakable` → `AudioButton text={stem}` | `packages/ui/src/learning/question-card.tsx` |
| 三层提示 | `HintStack` 的 `speakable` | `packages/ui/src/learning/hint-stack.tsx` |
| 讲解脚本（降级页） | `ScriptFallback` 每幕一个 `AudioButton` | `apps/desktop/src/routes/journey/explainer-blocks.tsx` |
| 知识地图节点 | 朗读「label，掌握度X」 | `packages/ui/src/learning/knowledge-map.tsx` |
| 吉祥物 | 固定欢迎语 | `kids-navigation.tsx` |
| onboarding | 有 `AudioButton` | `apps/desktop/src/routes/onboarding.tsx` |

`speakable` 的来源统一是 `theme === "kids"`（各阶段页 `const speakable = theme === "kids"`）。

**⚠️ 未覆盖（一处，已记录为待补）**：`JourneyStepper` 的「当前：第 N 站」「下一站：X」两处导航提示**没有朗读按钮**。
- 影响面：孩子不知道下一步要去哪儿时，只能靠读小字（而这两处正是本单第 2 项刚放大过的小字）。
- 为什么没直接补：`JourneyStepper` 是六个阶段页共用的组件，加了朗读会在每个页面都多一个喇叭图标，对专注模式是噪音。
- **建议方案**（留待下一轮）：只在 kids 档给这两处提示挂一个**共享的**朗读入口（复用 `KidsNavBar` 已有的一次性朗读，而不是每页加图标），或者把「下一站」直接读进 `StageShell` 的标题朗读里。

**能力降级是安全的**：`AudioButton` 在浏览器不支持 `speechSynthesis` 时返回 `null` 自行隐藏（`packages/ui/src/learning/audio-button.tsx`），不抛错、不阻断主流程。

## 8. 答对有正反馈动效 —— ✅

`packages/ui/src/learning/answer-pickers.tsx` 的 `CorrectBurst`，接入点 `apps/desktop/src/routes/journey/unit-blocks.tsx` 的 `FeedbackCard`：

```tsx
<Card className="relative overflow-hidden">
  {isCorrect ? <CorrectBurst testId="unit-celebrate" /> : null}
```

| 细节 | 取证 |
|---|---|
| 5 色取自 §4.1 儿童主色 | `CONFETTI_COLORS = ["#F6C445","#4BA3E3","#7BC96F","#F08A5D","#9B7EDE"]` |
| 尊重动效敏感 | `KEYFRAMES` 内 `@media (prefers-reduced-motion: reduce) { .xb-confetti-piece { animation: none !important; display: none; } }` |
| 不挡交互 | 外层 `aria-hidden` + `pointer-events-none` |
| 不依赖音频文件 | 纯 CSS keyframes，无外部资源 |
| 覆盖 | `unit-blocks.test.tsx` 的 `FeedbackCard` 三条（答对撒花 / 答错不撒花 / 两个出口可点） |

音效**未做**：§4.1 写的是「正反馈动效（答对撒花/音效）」，斜杠是并列项，目前只做了动效。音效需要音频资产与用户偏好开关（7 岁孩子的设备可能静音或已被家长禁用声音），不属于「零成本」范围，留到 P2。

## 9. 不提供深色模式 —— ✅

- kids 档 `app-layout.tsx` 的 `mode-toggle` 按钮 `disabled={theme === "kids"}`
- E2E 守卫：`apps/desktop/e2e/shell.spec.ts`「P0 儿童模式不提供深色（§4.1）」——断言 `mode-toggle` 禁用 **且** `document.documentElement` 不含 `dark` class（两个条件都查，防止「按钮禁用但主题已被别处切过去」）

## 10. 导航不依赖文字识别 —— ✅

kids 档用 `KidsNavBar`（`apps/desktop/src/components/kids-navigation.tsx`）**替换**学院派侧边栏（不是并列——两条侧边栏并排会挤掉内容区）：

| 阶段 | 图标 | testid |
|---|---|---|
| 今天 | 🔥 | `kids-nav-today` |
| 诊断 | 🩺 | `kids-nav-diagnosis` |
| 计划 | 🗺️ | `kids-nav-plan` |
| 单元 | 📖 | `kids-nav-unit` |
| 错题 | 🧩 | `kids-nav-mistakes` |
| 复习 | 🔁 | `kids-nav-review` |

**图标是主视觉、文字是补充**，且 emoji 自带暖色与圆脸，比描边线性图标更接近儿童读物。图标取自 `STAGE_ICONS` 映射表，未知 id 回退 `⭐` 而不是空白。
家长/老师可在同一安装切回专注模式（`theme-toggle`），两套导航各有适用人群。
覆盖：`kids-navigation.test.tsx` 8 条（每阶段有专属图标、当前阶段 `aria-current="page"`、按钮带 `min-h-[var(--tap-min)]`）+ E2E 用例 1。

## 11. 一年级全部题干可朗读 —— ✅

- 出题 prompt 强制「题干必须口语化、可朗读（一年级会由 TTS 朗读题干），不要用生僻符号」（`app/services/prompts.py` 的 `QUESTION_GEN_SYSTEM_PROMPT` 第 3 条）
- 题型覆盖：选择 / 判断 / 填空 / 连线 / 口算 / 点选识字 六种都有作答控件（`answer-pickers.tsx` 的 `LinkMatcher` 连线台 + `JUDGE_OPTIONS` 判断大按钮；`question-card.tsx` 的 `kind="pick"` 点选识字）
- 判卷按题型归一，不会出现「连线题永远判错」（`app/services/diagnosis_service.py` 的 `check_answer` 分派）

## 12. 一年级 20 分钟强制休息 —— ✅

- hook：`apps/desktop/src/journey/use-rest-break.ts`，阈值固定 **20 分钟**（`SESSION_MINUTES=20`）、休息 5 分钟、剩 3 分钟预警
- **休息期间不提供任何跳过按钮**（「强制」就是不给出路）——E2E 用例 2 专门断言 `overlay.getByRole("button")` 数量为 0
- 遮罩 `role="dialog"` + `aria-modal="true"`，倒计时 `tabular-nums`
- 已用时长落 localStorage：切页面/切阶段不重置（「换个页面就重新开始 20 分钟」等于没有限制）；存量 ≥6h 视为上次没关干净的残留，整体丢弃
- 与 `GuardianGate` 分工明确：GuardianGate 管「今天还能不能学」（服务端判定、家长可调），本 hook 管「这一次连着学太久必须歇」（阈值固定、家长不可调没）

## 13. 关键内容对比度达 WCAG AA —— ✅

E2E 断言（`shell.spec.ts`）：
- 「登录页与旅程主布局 axe 0 critical / serious」
- 「儿童模式旅程页 axe 0 critical / serious」

两条都扫 `wcag2a/2aa/21a/21aa`，critical 与 serious 视为不通过。
另外 `expectNoBlockingA11y` 在扫描前必须 `addStyleTag` 冻结 transition/animation 并等两帧——否则主题切换首帧会采到过渡中间色，把 color-contrast 误判成不通过（这是既有 flaky 的根因，已修）。

---

## 本单发现并修掉的问题

| # | 问题 | 严重度 | 状态 |
|---|---|---|---|
| 1 | `JourneyStepper` 的导航提示在 kids 下仍是 15.4px 小字 | 中（7 岁读不清「下一站」） | ✅ 已修 |
| 2 | `JourneyStepper` 的导航提示无 TTS 朗读 | 低（但影响「知道下一步去哪」） | ⬜ 留待下一轮，方案见第 7 项 |

## 本单**没有**覆盖到的（诚实登记）

- **没有真人试玩记录**。本单全部是代码与 token 层面的取证；「7 岁孩子实际会不会用」只能由真人试玩回答，
  而这正是下一轮 §4 出口门禁要补的「妹妹旅程真人试用」。
- **没有覆盖移动端**。本单只查了 `apps/desktop`。`packages/mobile` 与 `apps/web` 的儿童主题呈现未核。
- **没有覆盖学习效果**。「讲清楚了」不等于「学会了」，那要看掌握度曲线，不在本单范围。
- **音效未做**（第 8 项）。

## 复核方式

```powershell
# 字号/热区/圆角/主色这四条都在 token 里，改一处即可复核
Select-String -Path packages/config/tokens/theme.css -Pattern 'data-theme="kids"' -Context 0,20
# 朗读覆盖点
Select-String -Path apps/desktop/src/**/*.tsx -Pattern "AudioButton" -List
# 无深色模式守卫
Select-String -Path apps/desktop/e2e/shell.spec.ts -Pattern "不提供深色" -Context 0,6
```
