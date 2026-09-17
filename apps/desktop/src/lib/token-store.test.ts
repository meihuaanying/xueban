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

  it("keyring 异常时静默回退本地存储", async () => {
    const invoke = vi.fn().mockRejectedValue(new Error("keyring unavailable"));
    vi.stubGlobal("__TAURI_INTERNALS__", {});
    vi.doMock("@tauri-apps/api/core", () => ({ invoke }));

    const store = await import("./token-store");
    await store.saveTokens(TOKENS);
    const loaded = await store.loadTokens();
    expect(loaded?.accessToken).toBe("access-1");
    await store.clearTokens();
    expect(await store.loadTokens()).toBeNull();
  });
});
