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
 * 学段之下再选具体年级（`grades`，grade1~12）；API 调用携带年级时，
 * 题目范围会经知识点 grade 列收窄到人教版教材进度（见后端 grade_scope）。
 */
export interface GradeBandPreset {
  label: string;
  theme: "kids" | "focus";
  subject: string;
  /** 默认年级（学段内第一个年级） */
  grade: string;
  /** 该学段可选的年级（grade1~12），onboarding 第二步从这里选 */
  grades: readonly string[];
  stage: string;
}

export const GRADE_BANDS: Record<GradeBand, GradeBandPreset> = {
  primary: {
    label: "小学",
    theme: "kids",
    subject: "math",
    grade: "grade1",
    grades: ["grade1", "grade2", "grade3", "grade4", "grade5", "grade6"],
    stage: "primary",
  },
  junior: {
    label: "初中",
    theme: "focus",
    subject: "math",
    grade: "grade7",
    grades: ["grade7", "grade8", "grade9"],
    stage: "junior",
  },
  senior: {
    label: "高中",
    theme: "focus",
    subject: "math",
    grade: "grade10",
    grades: ["grade10", "grade11", "grade12"],
    stage: "senior",
  },
};

/** 学科的中文名与可选性（广东口径：小学语数英；初中九科；高中语数英 + 3+1+2 六科）。 */
export const SUBJECT_LABELS: Record<string, string> = {
  chinese: "语文",
  math: "数学",
  english: "英语",
  physics: "物理",
  chemistry: "化学",
  biology: "生物",
  history: "历史",
  geography: "地理",
  politics: "政治",
};

/** 各学段可切换的学科（顺序即展示顺序，默认仍是数学）。 */
export const SUBJECT_OPTIONS: Record<GradeBand, readonly string[]> = {
  primary: ["chinese", "math", "english"],
  junior: ["chinese", "math", "english", "physics", "chemistry", "biology", "history", "geography", "politics"],
  senior: ["chinese", "math", "english", "physics", "chemistry", "biology", "history", "geography", "politics"],
};

export function subjectLabel(subject: string): string {
  return SUBJECT_LABELS[subject] ?? subject;
}

/** 年级的中文名（与后端 curriculum.GRADE_NAMES 一致，高中用高一/高二/高三）。 */
export const GRADE_LABELS: Record<string, string> = {
  grade1: "一年级",
  grade2: "二年级",
  grade3: "三年级",
  grade4: "四年级",
  grade5: "五年级",
  grade6: "六年级",
  grade7: "七年级",
  grade8: "八年级",
  grade9: "九年级",
  grade10: "高一",
  grade11: "高二",
  grade12: "高三",
};

export function gradeLabel(grade: string): string {
  return GRADE_LABELS[grade] ?? grade;
}

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
