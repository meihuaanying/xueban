/** 登录态本地存储（仅浏览器端调用）。 */

import type { TokenPair } from "./api";

const ACCESS_TOKEN_KEY = "xueban.access_token";
const REFRESH_TOKEN_KEY = "xueban.refresh_token";

export function saveTokens(pair: TokenPair): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(ACCESS_TOKEN_KEY, pair.access_token);
  window.localStorage.setItem(REFRESH_TOKEN_KEY, pair.refresh_token);
}

export function saveAccessToken(token: string): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(ACCESS_TOKEN_KEY, token);
}

export function loadAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function clearTokens(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(ACCESS_TOKEN_KEY);
  window.localStorage.removeItem(REFRESH_TOKEN_KEY);
}
