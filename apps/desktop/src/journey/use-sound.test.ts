/**
 * 答题音效偏好测试（§4.1）。
 *
 * 契约有三条，都值得钉死：
 * 1. **默认开**——音效是 §4.1 要求的儿童主题能力，默认关等于没做；
 * 2. 关掉之后要落盘，下次进来还是关的；
 * 3. localStorage 抛错（隐私模式）时不能崩，退化为仅本次会话有效。
 */
import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SOUND_STORAGE_KEY, useSoundPreference } from "./use-sound";

beforeEach(() => {
  window.localStorage.clear();
});

afterEach(() => {
  vi.restoreAllMocks();
  window.localStorage.clear();
});

describe("useSoundPreference", () => {
  it("默认开启", () => {
    const { result } = renderHook(() => useSoundPreference());
    expect(result.current.enabled).toBe(true);
  });

  it("toggle 关掉后落盘为 off，并且状态跟着变", () => {
    const { result } = renderHook(() => useSoundPreference());

    act(() => result.current.toggle());

    expect(result.current.enabled).toBe(false);
    expect(window.localStorage.getItem(SOUND_STORAGE_KEY)).toBe("off");
  });

  it("再次 toggle 回到开启并落盘为 on", () => {
    const { result } = renderHook(() => useSoundPreference());

    act(() => result.current.toggle());
    act(() => result.current.toggle());

    expect(result.current.enabled).toBe(true);
    expect(window.localStorage.getItem(SOUND_STORAGE_KEY)).toBe("on");
  });

  it("存量 off 时初始就是关的", () => {
    window.localStorage.setItem(SOUND_STORAGE_KEY, "off");
    const { result } = renderHook(() => useSoundPreference());
    expect(result.current.enabled).toBe(false);
  });

  it("存量是看不懂的值时按默认开处理（只有显式 off 才算关）", () => {
    window.localStorage.setItem(SOUND_STORAGE_KEY, "maybe");
    const { result } = renderHook(() => useSoundPreference());
    expect(result.current.enabled).toBe(true);
  });

  it("setEnabled 直接设定也落盘", () => {
    const { result } = renderHook(() => useSoundPreference());

    act(() => result.current.setEnabled(false));

    expect(result.current.enabled).toBe(false);
    expect(window.localStorage.getItem(SOUND_STORAGE_KEY)).toBe("off");
  });

  it("localStorage 不可用时不崩，退化为仅本次会话有效", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("QuotaExceededError");
    });
    const { result } = renderHook(() => useSoundPreference());

    expect(() => act(() => result.current.toggle())).not.toThrow();
    expect(result.current.enabled).toBe(false);
  });

  it("localStorage 读取抛错时按默认开处理", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("SecurityError");
    });
    const { result } = renderHook(() => useSoundPreference());
    expect(result.current.enabled).toBe(true);
  });
});
