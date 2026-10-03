"use client";

/** 一年级「每次 20 分钟强制休息」（§8 约束 2：未成年人保护）。
 *
 * 与 GuardianGate 的区别要分清：
 * - GuardianGate 是**服务端**判定的每日上限，阈值由家长设置，锁的是当天；
 * - 这里管的是**单次连续使用**时长，一年级默认 20 分钟就必须休息，阈值固定、
 *   不可被调没（这是未成年人保护的底线，不是偏好）。
 *
 * 已用时长落 localStorage：切页面、切阶段都不该把计时器重置——
 * 「换个页面就重新开始 20 分钟」等于没有限制。
 */

import { useEffect, useMemo, useRef, useState } from "react";

/** 一年级单次连续学习上限（分钟）。 */
export const SESSION_MINUTES = 20;
/** 强制休息时长（分钟）。 */
export const REST_MINUTES = 5;
/** 剩余不足这个秒数就提前提醒。 */
export const WARNING_SECONDS = 180;

const STORAGE_KEY = "xueban.session.active-ms";
/** 存量记录超过这个时长就当是上次没关干净的残留，整体丢弃。 */
const STALE_MS = 6 * 60 * 60 * 1000;
const TICK_MS = 1000;

function readBase(): number {
  try {
    const parsed = Number(window.localStorage.getItem(STORAGE_KEY));
    return Number.isFinite(parsed) && parsed >= 0 ? parsed : 0;
  } catch {
    return 0;
  }
}

function writeBase(value: number): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, String(Math.round(value)));
  } catch {
    // 无痕模式/存储配额满：退化为「本次会话内有效」，不阻断主流程
  }
}

function clearBase(): void {
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    // 同上，忽略
  }
}

export interface UseRestBreakOptions {
  /** 关掉就没有任何计时（专注模式/非小学低年级学段）。 */
  enabled?: boolean;
  sessionMinutes?: number;
  restMinutes?: number;
}

export interface RestBreakState {
  /** 已连续学习分钟（向上取整）。 */
  elapsedMinutes: number;
  /** 距离强制休息还有多少秒；休息中为 0。 */
  remainingSeconds: number;
  /** 是否处于强制休息。 */
  resting: boolean;
  /** 休息还要多久才能继续（秒）。 */
  restRemainingSeconds: number;
  /** 剩余不足 3 分钟，提前提醒。 */
  warning: boolean;
}

export function useRestBreak({
  enabled = true,
  sessionMinutes = SESSION_MINUTES,
  restMinutes = REST_MINUTES,
}: UseRestBreakOptions = {}): RestBreakState {
  const sessionMs = Math.max(1, sessionMinutes) * 60_000;
  const restMs = Math.max(1, restMinutes) * 60_000;

  const [now, setNow] = useState(() => Date.now());
  const [elapsedMs, setElapsedMs] = useState(0);
  const [resting, setResting] = useState(false);
  /**
   * 累计时长用 ref 而不是 state：tick 每秒读一次 state 再写 state，会因为
   * effect 闭包不跟着更新而永远读到旧值（表现就是计时停在 1 秒不动）。
   * state 只留一份给渲染用。
   */
  const elapsedRef = useRef(0);
  /** 上一次 tick 的时刻，算增量用。 */
  const lastTickRef = useRef(0);
  /** 休息开始时刻，0 表示不在休息。 */
  const restStartedAtRef = useRef(0);

  // 启用状态变化时重置基准，并把上次的存量接进来
  useEffect(() => {
    const at = Date.now();
    lastTickRef.current = at;
    if (!enabled) {
      elapsedRef.current = 0;
      restStartedAtRef.current = 0;
      setElapsedMs(0);
      setResting(false);
      return;
    }
    const stored = readBase();
    const fresh = stored < STALE_MS;
    if (!fresh) clearBase();
    elapsedRef.current = fresh ? stored : 0;
    restStartedAtRef.current = 0;
    setElapsedMs(elapsedRef.current);
    setResting(elapsedRef.current >= sessionMs);
  }, [enabled, sessionMs]);

  useEffect(() => {
    if (!enabled) return;
    lastTickRef.current = Date.now();
    const tick = () => {
      const current = Date.now();
      setNow(current);
      const delta = Math.max(0, current - lastTickRef.current);
      lastTickRef.current = current;

      if (restStartedAtRef.current > 0) {
        if (current - restStartedAtRef.current >= restMs) {
          // 休息够了：清零重新计时，并清掉存量，下次进来从 0 开始
          restStartedAtRef.current = 0;
          elapsedRef.current = 0;
          clearBase();
          setElapsedMs(0);
          setResting(false);
        }
        return;
      }

      const total = Math.min(sessionMs, elapsedRef.current + delta);
      elapsedRef.current = total;
      setElapsedMs(total);
      writeBase(total);
      if (total >= sessionMs) {
        restStartedAtRef.current = current;
        setResting(true);
      }
    };
    const timer = window.setInterval(tick, TICK_MS);
    return () => window.clearInterval(timer);
  }, [enabled, restMs, sessionMs]);

  return useMemo(() => {
    const remaining = resting ? 0 : Math.max(0, Math.ceil((sessionMs - elapsedMs) / 1000));
    const restLeft = resting
      ? Math.max(0, Math.ceil((restMs - (now - restStartedAtRef.current)) / 1000))
      : 0;
    return {
      elapsedMinutes: Math.ceil(elapsedMs / 60_000),
      remainingSeconds: remaining,
      resting,
      restRemainingSeconds: restLeft,
      warning: !resting && remaining <= WARNING_SECONDS,
    };
  }, [elapsedMs, now, resting, restMs, sessionMs]);
}
