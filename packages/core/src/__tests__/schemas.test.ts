import { describe, expect, it } from "vitest";

import { ApiErrorSchema, HealthResponseSchema, PaginationSchema } from "../schemas";

describe("ApiErrorSchema", () => {
  it("接受合法错误结构", () => {
    const parsed = ApiErrorSchema.parse({ code: "AUTH_401", message: "未登录", trace_id: "t-1" });
    expect(parsed.code).toBe("AUTH_401");
  });

  it("拒绝缺少 message 的结构", () => {
    expect(() => ApiErrorSchema.parse({ code: "X" })).toThrow();
  });
});

describe("HealthResponseSchema", () => {
  it("仅接受 status=ok", () => {
    expect(HealthResponseSchema.parse({ status: "ok", service: "xueban-api", version: "0.1.0" }).service).toBe(
      "xueban-api",
    );
    expect(() =>
      HealthResponseSchema.parse({ status: "down", service: "xueban-api", version: "0.1.0" }),
    ).toThrow();
  });
});

describe("PaginationSchema", () => {
  it("page_size 上限为 100", () => {
    expect(() => PaginationSchema.parse({ page: 1, page_size: 101, total: 0 })).toThrow();
  });
});
