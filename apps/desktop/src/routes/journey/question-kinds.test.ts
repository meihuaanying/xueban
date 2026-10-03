/**
 * 题型映射的单元测试（§6.1）。
 *
 * 这些函数是「题库数据形态」与「前端作答控件」之间的唯一接缝：
 * 题干解析和提交格式错一点，学生就会遇到一道永远判不对的题。
 */
import { describe, expect, it } from "vitest";

import { parseLinkItems, resolveKind, toLinkSubmit, toOptions } from "./question-kinds";

describe("resolveKind", () => {
  it("六种小学题型各有各的作答形态", () => {
    expect(resolveKind("choice")).toBe("choice");
    expect(resolveKind("fill")).toBe("fill");
    expect(resolveKind("judge")).toBe("judge");
    expect(resolveKind("match")).toBe("link");
    expect(resolveKind("oral")).toBe("oral");
    expect(resolveKind("pick_hanzi")).toBe("pick");
  });

  it("主观题按填空处理", () => {
    expect(resolveKind("essay")).toBe("fill");
    expect(resolveKind("short_answer")).toBe("fill");
  });

  it("未知题型按选择处理，最宽容", () => {
    expect(resolveKind("brand-new-type")).toBe("choice");
    expect(resolveKind("")).toBe("choice");
  });
});

describe("parseLinkItems", () => {
  it("从题干里取出连线左项（题库真实形态）", () => {
    const stem = "把物品和它的形状连起来：铅笔盒、乒乓球、易拉罐、魔方。";
    expect(parseLinkItems(stem)).toEqual(["铅笔盒", "乒乓球", "易拉罐", "魔方"]);
  });

  it("中英文冒号都认", () => {
    expect(parseLinkItems("连线题:苹果、香蕉")).toEqual(["苹果", "香蕉"]);
  });

  it("兼容逗号分隔", () => {
    expect(parseLinkItems("把下面连起来：猫，狗，兔")).toEqual(["猫", "狗", "兔"]);
  });

  it("不按「和」「与」切，避免误伤含这些字的词", () => {
    expect(parseLinkItems("连线：共和国、和平鸟")).toEqual(["共和国", "和平鸟"]);
  });

  it("取不到左项时返回空数组，调用方据此降级", () => {
    expect(parseLinkItems("")).toEqual([]);
  });
});

describe("toOptions", () => {
  it("把 Record 转成数组并保留顺序", () => {
    expect(toOptions({ A: "长方形", B: "圆形" })).toEqual([
      { key: "A", label: "长方形" },
      { key: "B", label: "圆形" },
    ]);
  });

  it("null 与空对象都返回 undefined（不渲染空选项列表）", () => {
    expect(toOptions(null)).toBeUndefined();
    expect(toOptions({})).toBeUndefined();
  });
});

describe("toLinkSubmit", () => {
  it("序列化成 JSON 对象字符串，与后端按映射比对对齐", () => {
    expect(toLinkSubmit({ 铅笔盒: "长方形" })).toBe('{"铅笔盒":"长方形"}');
  });

  it("键序无关：两种插入顺序解出同一个映射", () => {
    const a = toLinkSubmit({ 铅笔盒: "长方形", 乒乓球: "圆形" });
    const b = toLinkSubmit({ 乒乓球: "圆形", 铅笔盒: "长方形" });
    expect(JSON.parse(a)).toEqual(JSON.parse(b));
  });
});
