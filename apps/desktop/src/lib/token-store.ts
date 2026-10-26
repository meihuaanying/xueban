/**
 * 登录态持久化：桌面端走系统 keyring（Rust 命令），浏览器/E2E 回退 localStorage。
 */

import { invoke } from "@tauri-apps/api/core";

import { setRefreshToken, type TokenPair } from "./api";

const ACCESS_ACCOUNT = "access_token";
const REFRESH_ACCOUNT = "refresh_token";
const STORAGE_PREFIX = "xueban.desktop.";
// keyring 不可用且不允许本地明文回退时（refresh token），仅存内存
const memorySecrets = new Map<string, string>();

export function isTauri(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

async function saveSecret(
  account: string,
  secret: string,
  allowLocalFallback: boolean,
): Promise<void> {
  if (isTauri()) {
    try {
      await invoke("credential_save", { account, secret });
      return;
    } catch {
      // keyring 不可用时回退本地存储（不阻塞登录）
    }
  }
  if (allowLocalFallback) {
    window.localStorage.setItem(STORAGE_PREFIX + account, secret);
  } else {
    memorySecrets.set(account, secret);
  }
}

async function loadSecret(account: string): Promise<string | null> {
  if (isTauri()) {
    try {
      const value = await invoke<string | null>("credential_load", { account });
      if (value) return value;
    } catch {
      // 忽略，走本地存储回退
    }
  }
  return (
    window.localStorage.getItem(STORAGE_PREFIX + account) ?? memorySecrets.get(account) ?? null
  );
}

async function deleteSecret(account: string): Promise<void> {
  if (isTauri()) {
    try {
      await invoke("credential_delete", { account });
    } catch {
      // 忽略
    }
  }
  window.localStorage.removeItem(STORAGE_PREFIX + account);
  memorySecrets.delete(account);
}

export async function saveTokens(pair: TokenPair): Promise<void> {
  await saveSecret(ACCESS_ACCOUNT, pair.access_token, true);
  await saveSecret(REFRESH_ACCOUNT, pair.refresh_token, false);
  setRefreshToken(pair.refresh_token);
}

export async function loadTokens(): Promise<{ accessToken: string; refreshToken: string } | null> {
  const accessToken = await loadSecret(ACCESS_ACCOUNT);
  if (!accessToken) return null;
  const refreshToken = (await loadSecret(REFRESH_ACCOUNT)) ?? "";
  setRefreshToken(refreshToken || null);
  return { accessToken, refreshToken };
}

export async function clearTokens(): Promise<void> {
  await deleteSecret(ACCESS_ACCOUNT);
  await deleteSecret(REFRESH_ACCOUNT);
  setRefreshToken(null);
}

/** 测试/E2E 辅助：清空两种存储。 */
export function clearTokensSync(): void {
  window.localStorage.removeItem(STORAGE_PREFIX + ACCESS_ACCOUNT);
  window.localStorage.removeItem(STORAGE_PREFIX + REFRESH_ACCOUNT);
}
