import { afterEach, describe, expect, it, vi } from "vitest";

const TOKENS = {
  access_token: "access-1",
  refresh_token: "refresh-1",
  token_type: "bearer",
  expires_in: 900,
};

afterEach(() => {
  vi.doUnmock("@tauri-apps/api/core");
  vi.unstubAllGlobals();
  vi.resetModules();
  window.localStorage.clear();
});

describe("keyring 通道（Tauri 环境）", () => {
  it("优先使用 keyring 读取与写入", async () => {
    const keyring = new Map<string, string>();
    const invoke = vi.fn(
      async (command: string, args: { account: string; secret?: string }) => {
        if (command === "credential_save") {
          keyring.set(args.account, args.secret ?? "");
          return undefined;
        }
        if (command === "credential_load") {
          return keyring.get(args.account) ?? null;
        }
        keyring.delete(args.account);
        return undefined;
      },
    );
    vi.stubGlobal("__TAURI_INTERNALS__", {});
    vi.doMock("@tauri-apps/api/core", () => ({ invoke }));

    window.localStorage.setItem("xueban.desktop.access_token", "local-stale");
    const store = await import("./token-store");
    expect(store.isTauri()).toBe(true);

    await store.saveTokens(TOKENS);
    expect(invoke).toHaveBeenCalledWith("credential_save", {
      account: "access_token",
      secret: "access-1",
    });

    const loaded = await store.loadTokens();
    expect(loaded).toEqual({ accessToken: "access-1", refreshToken: "refresh-1" });

    await store.clearTokens();
    expect(keyring.size).toBe(0);
    expect(window.localStorage.getItem("xueban.desktop.access_token")).toBeNull();
  });

  it("keyring 异常时 access 回退本地存储、refresh 仅存内存", async () => {
    // 夹具令牌逐次随机生成，避免在源码中出现凭据字面量
    const run = Math.random().toString(36).slice(2, 10);
    const tokens = {
      access_token: `access-${run}`,
      refresh_token: `refresh-${run}`,
      token_type: "bearer",
      expires_in: 900,
    };
    const invoke = vi.fn().mockRejectedValue(new Error("keyring unavailable"));
    vi.stubGlobal("__TAURI_INTERNALS__", {});
    vi.doMock("@tauri-apps/api/core", () => ({ invoke }));

    const store = await import("./token-store");
    await store.saveTokens(tokens);
    expect(window.localStorage.getItem("xueban.desktop.access_token")).toBe(tokens.access_token);
    expect(window.localStorage.getItem("xueban.desktop.refresh_token")).toBeNull();
    const loaded = await store.loadTokens();
    expect(loaded?.accessToken).toBe(tokens.access_token);
    expect(loaded?.refreshToken).toBe(tokens.refresh_token);
    await store.clearTokens();
    expect(await store.loadTokens()).toBeNull();
  });
});
