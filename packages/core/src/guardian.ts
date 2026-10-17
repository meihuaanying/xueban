/**
 * 防沉迷闸门的共享契约（§8 约束 7：三端重复实现必须合并）。
 *
 * 桌面端与移动端各有一份 `guardian-gate.tsx`，两边的以下东西**逐字相同**：
 * - 服务端返回的状态形状
 * - 锁定原因的展示文案（`daily_limit` / `curfew`）
 * - 锁屏页的全部中文文案
 * - 60 秒轮询周期
 *
 * 属于平台差异的只有「怎么画」（Web 用 Card/Badge，原生端用 View/Text）。
 * 把文案与契约放在这里，是因为**文案漂移是真会发生的事**：抽取前两端就已经不一致——
 * 移动端写「休息一下再回来」，桌面端写「看一会儿远处，休息一下再回来」。同一句提示
 * 在不同设备上不一样，家长和孩子都会困惑。规则/文案必须只有一份。
 *
 * 注意：本模块**不含任何 UI 依赖**，纯数据与纯函数，因此 Web / React Native 都能用。
 */

/** 服务端 `GET /v1/guardian/status` 的返回形状（两端共用）。 */
export interface GuardianStatus {
  locked: boolean;
  reasons: string[];
  used_minutes: number;
  limit_minutes: number | null;
  available_from: string | null;
  /** 仅桌面端消费：是否到了「建议休息」的软提醒。 */
  suggest_break?: boolean;
  /** 仅桌面端消费：当前是否处于宵禁时段。 */
  curfew_active?: boolean;
}

/** 轮询周期：60 秒复核一次，无法本地绕过。 */
export const GUARDIAN_POLL_MS = 60_000;

/** 锁定原因 → 中文说明。未知原因原样透出，不吞掉服务端新加的类型。 */
const REASON_LABELS: Record<string, string> = {
  daily_limit: "今日学习时长已达上限",
  curfew: "当前不在允许使用时段",
};

export function guardianReasonLabel(reason: string): string {
  return REASON_LABELS[reason] ?? reason;
}

/** 锁屏页文案（统一口径，两端不再各写一份）。 */
export const GUARDIAN_COPY = {
  title: "学习时间已到",
  body: "家长设置了使用管理，当前学习已暂停。看一会儿远处，休息一下再回来。",
  retry: "我休息好了，重新检查",
  fetchFailed: "防沉迷状态获取失败，将在稍后重试。",
} as const;

/** 「今日已学 N 分钟 / 上限 M 分钟」。 */
export function guardianUsageText(state: Pick<GuardianStatus, "used_minutes" | "limit_minutes">): string {
  const limit = state.limit_minutes ? ` / 上限 ${state.limit_minutes} 分钟` : "";
  return `今日已学 ${state.used_minutes} 分钟${limit}`;
}

/** 「允许使用时段：HH:mm 开始」。 */
export function guardianAvailableText(availableFrom: string): string {
  return `允许使用时段：${availableFrom} 开始`;
}
