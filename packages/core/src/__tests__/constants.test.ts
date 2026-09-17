import { afterEach, describe, expect, it } from "vitest";

import {
  APP_NAME,
  APP_SLOGAN,
  API_PREFIX,
  DEFAULT_LOCALE,
  getApiBaseUrl,
} from "../constants";

const originalEnv = { ...process.env };

afterEach(() => {
  process.env = { ...originalEnv };
});

describe("产品常量与 API 基址", () => {
  it("导出产品常量", () => {
    expect(APP_NAME).toBe("学伴");
    expect(APP_SLOGAN).toContain("把每一道题");
    expect(DEFAULT_LOCALE).toBe("zh-CN");
    expect(API_PREFIX).toBe("/v1");
  });

  it("NEXT_PUBLIC_API_BASE_URL 优先", () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = "https://web.example.com";
    process.env.EXPO_PUBLIC_API_BASE_URL = "https://mobile.example.com";
    expect(getApiBaseUrl()).toBe("https://web.example.com");
  });

  it("退回 EXPO_PUBLIC_API_BASE_URL", () => {
    delete process.env.NEXT_PUBLIC_API_BASE_URL;
    process.env.EXPO_PUBLIC_API_BASE_URL = "https://mobile.example.com";
    expect(getApiBaseUrl()).toBe("https://mobile.example.com");
  });

  it("无环境变量时使用 fallback", () => {
    delete process.env.NEXT_PUBLIC_API_BASE_URL;
    delete process.env.EXPO_PUBLIC_API_BASE_URL;
    expect(getApiBaseUrl()).toBe("http://localhost:8000");
    expect(getApiBaseUrl("http://127.0.0.1:8090")).toBe("http://127.0.0.1:8090");
  });
});
