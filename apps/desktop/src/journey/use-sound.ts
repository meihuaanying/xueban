"use client";

/**
 * 答题音效偏好（§4.1「答对撒花/音效」）。
 *
 * 为什么要有开关而不是「做了就一直响」：
 * - 设备可能静音，也可能是在图书馆/睡前；家长需要一个明确的关闭入口。
 * - 桌面端与移动端共用同一套 localStorage 键名约定（`xueban.*`），
 *   以后移动端接入时偏好能自然延续。
 *
 * **默认开**：音效是 §4.1 要求的儿童主题能力，默认关等于没做。但存储不可用时
 * （隐私模式）退化为「仅本次会话有效」，不抛错、不阻断。
 */

import { useCallback, useState } from "react";

export const SOUND_STORAGE_KEY = "xueban.sound";

function readInitial(): boolean {
  if (typeof window === "undefined") return true;
  try {
    const raw = window.localStorage.getItem(SOUND_STORAGE_KEY);
    // 只有显式存过 "off" 才算关；没存过、或存了看不懂的值，都按默认开处理
    return raw !== "off";
  } catch {
    return true;
  }
}

export interface SoundPreference {
  /** 是否播放答题音效 */
  enabled: boolean;
  setEnabled: (next: boolean) => void;
  toggle: () => void;
}

export function useSoundPreference(): SoundPreference {
  const [enabled, setEnabledState] = useState<boolean>(readInitial);

  const setEnabled = useCallback((next: boolean) => {
    setEnabledState(next);
    if (typeof window === "undefined") return;
    try {
      window.localStorage.setItem(SOUND_STORAGE_KEY, next ? "on" : "off");
    } catch {
      /* 隐私模式下 localStorage 不可用，降级为仅本次会话有效 */
    }
  }, []);

  const toggle = useCallback(() => {
    setEnabledState((prev) => {
      const next = !prev;
      if (typeof window !== "undefined") {
        try {
          window.localStorage.setItem(SOUND_STORAGE_KEY, next ? "on" : "off");
        } catch {
          /* 同上 */
        }
      }
      return next;
    });
  }, []);

  return { enabled, setEnabled, toggle };
}
