import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { REST_MINUTES, SESSION_MINUTES, useRestBreak } from "./use-rest-break";

const STORAGE_KEY = "xueban.session.active-ms";
const SECOND = 1000;
const MINUTE = 60 * SECOND;

function advance(minutes: number): void {
  act(() => {
    vi.advanceTimersByTime(minutes * MINUTE);
  });
}

describe("useRestBreak（§8 约束 2 一年级 20 分钟强制休息）", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("默认阈值就是 20 分钟 / 休息 5 分钟", () => {
    expect(SESSION_MINUTES).toBe(20);
    expect(REST_MINUTES).toBe(5);
  });

  it("刚挂载时不该提醒，还有整整 20 分钟", () => {
    const { result } = renderHook(() => useRestBreak());
    expect(result.current.resting).toBe(false);
    expect(result.current.warning).toBe(false);
    expect(result.current.remainingSeconds).toBe(SESSION_MINUTES * 60);
  });

  it("学满 20 分钟后进入强制休息", () => {
    const { result } = renderHook(() => useRestBreak());
    advance(19);
    expect(result.current.resting).toBe(false);
    advance(1);
    expect(result.current.resting).toBe(true);
    expect(result.current.remainingSeconds).toBe(0);
  });

  it("剩余不足 3 分钟就提前提醒", () => {
    const { result } = renderHook(() => useRestBreak());
    advance(SESSION_MINUTES - 2);
    expect(result.current.resting).toBe(false);
    expect(result.current.warning).toBe(true);
    expect(result.current.remainingSeconds).toBeLessThanOrEqual(180);
  });

  it("休息期间倒计时会走动", () => {
    const { result } = renderHook(() => useRestBreak());
    advance(SESSION_MINUTES);
    const start = result.current.restRemainingSeconds;
    advance(1);
    expect(result.current.restRemainingSeconds).toBeLessThan(start);
    expect(result.current.restRemainingSeconds).toBe((REST_MINUTES - 1) * 60);
  });

  it("休息满 5 分钟后自动恢复并清零", () => {
    const { result } = renderHook(() => useRestBreak());
    advance(SESSION_MINUTES);
    expect(result.current.resting).toBe(true);
    advance(REST_MINUTES);
    expect(result.current.resting).toBe(false);
    expect(result.current.remainingSeconds).toBe(SESSION_MINUTES * 60);
    expect(result.current.elapsedMinutes).toBe(0);
  });

  it("休息期满要清掉存量，下次进来从 0 开始", () => {
    const { result } = renderHook(() => useRestBreak());
    advance(SESSION_MINUTES);
    advance(REST_MINUTES);
    expect(window.localStorage.getItem(STORAGE_KEY)).toBeNull();
    expect(result.current.elapsedMinutes).toBe(0);
  });

  it("enabled=false 时完全不计时", () => {
    const { result } = renderHook(() => useRestBreak({ enabled: false }));
    advance(SESSION_MINUTES * 2);
    expect(result.current.resting).toBe(false);
    expect(result.current.remainingSeconds).toBe(SESSION_MINUTES * 60);
    expect(result.current.elapsedMinutes).toBe(0);
  });

  it("切页面后接着上一段的时间，不重新给 20 分钟", () => {
    const first = renderHook(() => useRestBreak());
    advance(10);
    expect(first.result.current.elapsedMinutes).toBe(10);
    first.unmount();

    const second = renderHook(() => useRestBreak());
    expect(second.result.current.elapsedMinutes).toBe(10);
    expect(second.result.current.remainingSeconds).toBe((SESSION_MINUTES - 10) * 60);
  });

  it("存量超过 6 小时视为上次没关干净的残留，整体丢弃", () => {
    window.localStorage.setItem(STORAGE_KEY, String(8 * 60 * MINUTE));
    const { result } = renderHook(() => useRestBreak());
    expect(result.current.elapsedMinutes).toBe(0);
    expect(result.current.resting).toBe(false);
  });

  it("已经超时的存量直接进入休息态", () => {
    window.localStorage.setItem(STORAGE_KEY, String(SESSION_MINUTES * MINUTE));
    const { result } = renderHook(() => useRestBreak());
    expect(result.current.resting).toBe(true);
  });

  it("存储损坏（NaN）时按 0 处理", () => {
    window.localStorage.setItem(STORAGE_KEY, "不是数字");
    const { result } = renderHook(() => useRestBreak());
    expect(result.current.remainingSeconds).toBe(SESSION_MINUTES * 60);
  });

  it("localStorage 抛错也不阻断主流程", () => {
    const spy = vi.spyOn(window.localStorage, "getItem").mockImplementation(() => {
      throw new Error("无痕模式");
    });
    const { result } = renderHook(() => useRestBreak());
    expect(result.current.resting).toBe(false);
    expect(result.current.remainingSeconds).toBe(SESSION_MINUTES * 60);
    spy.mockRestore();
  });

  it("自定义阈值可用（测试用 1 分钟，别真等 20 分钟）", () => {
    const { result } = renderHook(() => useRestBreak({ sessionMinutes: 1, restMinutes: 1 }));
    advance(1);
    expect(result.current.resting).toBe(true);
    advance(1);
    expect(result.current.resting).toBe(false);
  });
});
