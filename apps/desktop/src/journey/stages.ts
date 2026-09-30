/**
 * 学习旅程状态机（REBUILD §7 P0）
 *
 * 旅程是唯一的主干：今日任务 → 诊断 → 规划 → 学习单元（讲解⇄练习）→ 错题复习 → 复盘。
 * 任何页面跳转都必须经由本状态机（`nextStage` / `canEnter`），禁止孤立页面跳转。
 */

/** 旅程阶段（顺序即主干顺序） */
export type JourneyStage = "today" | "diagnosis" | "plan" | "unit" | "mistakes" | "review";

/** 学段：kids 主题面向小学低年级，focus 主题面向少年/成人 */
export type GradeBand = "primary" | "junior" | "senior";

export interface StageDefinition {
  id: JourneyStage;
  /** 序号（1 起） */
  order: number;
  label: string;
  /** 导航副标题 */
  hint: string;
  /** 路由路径 */
  path: string;
  /** 进入该阶段前必须满足的旅程条件 */
  requires: JourneyCondition[];
}

/** 阶段进入条件 */
export interface JourneyCondition {
  key: "hasProfile" | "diagnosisDone" | "planReady" | "unitVisited" | "mistakesLogged" | "reviewDone";
  label: string;
}

export interface JourneyState {
  stage: JourneyStage;
  hasProfile: boolean;
  diagnosisDone: boolean;
  planReady: boolean;
  unitVisited: boolean;
  mistakesLogged: boolean;
  reviewDone: boolean;
}

export const STAGES: readonly StageDefinition[] = [
  {
    id: "today",
    order: 1,
    label: "今日任务",
    hint: "今天要做的三件事",
    path: "/journey/today",
    requires: [],
  },
  {
    id: "diagnosis",
    order: 2,
    label: "诊断",
    hint: "摸清当前水平",
    path: "/journey/diagnosis",
    requires: [{ key: "hasProfile", label: "完成 onboarding" }],
  },
  {
    id: "plan",
    order: 3,
    label: "规划",
    hint: "按知识点排学习顺序",
    path: "/journey/plan",
    requires: [
      { key: "hasProfile", label: "完成 onboarding" },
      { key: "diagnosisDone", label: "完成首次诊断" },
    ],
  },
  {
    id: "unit",
    order: 4,
    label: "学习单元",
    hint: "讲解与练习交替",
    path: "/journey/unit",
    requires: [
      { key: "hasProfile", label: "完成 onboarding" },
      { key: "planReady", label: "已有学习规划" },
    ],
  },
  {
    id: "mistakes",
    order: 5,
    label: "错题复习",
    hint: "把错题变会做",
    path: "/journey/mistakes",
    requires: [{ key: "hasProfile", label: "完成 onboarding" }],
  },
  {
    id: "review",
    order: 6,
    label: "复盘",
    hint: "一周学得怎么样",
    path: "/journey/review",
    requires: [{ key: "hasProfile", label: "完成 onboarding" }],
  },
] as const;

const BY_ID: ReadonlyMap<JourneyStage, StageDefinition> = new Map(
  STAGES.map((stage) => [stage.id, stage]),
);

export function stageDefinition(id: JourneyStage): StageDefinition {
  const found = BY_ID.get(id);
  if (!found) throw new Error(`未知旅程阶段：${id}`);
  return found;
}

export function stagePath(id: JourneyStage): string {
  return stageDefinition(id).path;
}

/** 尚未满足的条件（空数组 = 可进入） */
export function unmetConditions(id: JourneyStage, state: JourneyState): JourneyCondition[] {
  return stageDefinition(id).requires.filter((condition) => !state[condition.key]);
}

export function canEnter(id: JourneyStage, state: JourneyState): boolean {
  return unmetConditions(id, state).length === 0;
}

/**
 * 状态机主转移：给定当前阶段与状态，返回下一阶段。
 * 规则：先补齐未完成的前置阶段（未诊断 → 诊断；已诊断无规划 → 规划；无规划 → 学习单元），
 * 否则沿主干前进；复盘是收尾阶段，到达后回到今日任务开始新一天。
 */
export function nextStage(state: JourneyState): JourneyStage {
  if (!state.hasProfile) return "today";
  if (!state.diagnosisDone) return "diagnosis";
  if (!state.planReady) return "plan";
  if (state.stage === "today" || state.stage === "diagnosis" || state.stage === "plan") {
    return "unit";
  }
  if (state.stage === "unit") return "mistakes";
  if (state.stage === "mistakes") return "review";
  return "today";
}

/**
 * 学段 → 主题皮肤、默认学科与题库学段（onboarding 选学段后自动切主题）
 *
 * `stage` 必须与后端 `Question.stage` 的取值一致：诊断选题按
 * `subject + stage + PUBLISHED` 精确筛选并强制 join 知识点关联，没有模糊匹配。
 * 当前题库实况：仅 `math/junior` 有题；`primary`/`senior` 暂无题库，
 * 对应页面走「题库建设中」空态（P1 §6.1 补一二年级题库、P3 补高中题库）。
 */
export const GRADE_BANDS: Record<
  GradeBand,
  { label: string; theme: "kids" | "focus"; subject: string; grade: string; stage: string }
> = {
  primary: { label: "小学低年级", theme: "kids", subject: "math", grade: "grade1", stage: "primary" },
  junior: { label: "初中", theme: "focus", subject: "math", grade: "grade7", stage: "junior" },
  senior: { label: "高中", theme: "focus", subject: "math", grade: "grade10", stage: "senior" },
};

export function defaultJourneyState(overrides: Partial<JourneyState> = {}): JourneyState {
  return {
    stage: "today",
    hasProfile: true,
    diagnosisDone: false,
    planReady: false,
    unitVisited: false,
    mistakesLogged: false,
    reviewDone: false,
    ...overrides,
  };
}
