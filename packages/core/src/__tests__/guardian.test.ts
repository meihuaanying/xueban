import { describe, expect, it } from "vitest";

import {
  guardianAvailableText,
  guardianReasonLabel,
  guardianUsageText,
} from "../guardian";

describe("guardianReasonLabel", () => {
  it("已知原因给出中文说明", () => {
    expect(guardianReasonLabel("daily_limit")).toBe("今日学习时长已达上限");
    expect(guardianReasonLabel("curfew")).toBe("当前不在允许使用时段");
  });

  it("未知原因原样透出，不吞掉服务端新加的类型", () => {
    expect(guardianReasonLabel("future_reason")).toBe("future_reason");
  });
});

describe("guardianUsageText", () => {
  it("有上限时带上限", () => {
    expect(guardianUsageText({ used_minutes: 45, limit_minutes: 60 })).toBe(
      "今日已学 45 分钟 / 上限 60 分钟",
    );
  });

  it("无上限时只报已学时长", () => {
    expect(guardianUsageText({ used_minutes: 45, limit_minutes: null })).toBe("今日已学 45 分钟");
  });

  it("上限为 0 视为未设置（避免出现「上限 0 分钟」）", () => {
    expect(guardianUsageText({ used_minutes: 5, limit_minutes: 0 })).toBe("今日已学 5 分钟");
  });
});

describe("guardianAvailableText", () => {
  it("拼出允许使用时段", () => {
    expect(guardianAvailableText("07:30")).toBe("允许使用时段：07:30 开始");
  });
});
