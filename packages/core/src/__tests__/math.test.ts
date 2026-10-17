import { describe, expect, it } from "vitest";

import { splitMathText } from "../math";

describe("splitMathText", () => {
  it("纯文本返回单个 text 段", () => {
    expect(splitMathText("小明有 3 个苹果")).toEqual([
      { kind: "text", value: "小明有 3 个苹果" },
    ]);
  });

  it("切出行内公式并剥掉 $ 定界符", () => {
    expect(splitMathText("3 + 4 = $7$")).toEqual([
      { kind: "text", value: "3 + 4 = " },
      { kind: "inline", value: "7" },
    ]);
  });

  it("切出独立公式并剥掉 $$ 定界符", () => {
    expect(splitMathText("看图：$$\\frac{1}{2}$$ 是半个")).toEqual([
      { kind: "text", value: "看图：" },
      { kind: "display", value: "\\frac{1}{2}" },
      { kind: "text", value: " 是半个" },
    ]);
  });

  it("同一段里混排行内与独立公式，顺序不变", () => {
    expect(splitMathText("$a$ 和 $$b$$ 和 $c$")).toEqual([
      { kind: "inline", value: "a" },
      { kind: "text", value: " 和 " },
      { kind: "display", value: "b" },
      { kind: "text", value: " 和 " },
      { kind: "inline", value: "c" },
    ]);
  });

  it("公式在首尾时不会产生空文本段", () => {
    expect(splitMathText("$5$")).toEqual([{ kind: "inline", value: "5" }]);
  });

  it("空定界符不会被当成公式（正则要求至少一个非 $ 字符）", () => {
    expect(splitMathText("a$$$$b")).toEqual([{ kind: "text", value: "a$$$$b" }]);
  });

  it("单个 $ 不会开启公式（长度不足 3 的 $$ 当文本）", () => {
    expect(splitMathText("价格 $ 5 元")).toEqual([{ kind: "text", value: "价格 $ 5 元" }]);
  });

  it("跨行的 $...$ 不被当成行内公式", () => {
    expect(splitMathText("第一行 $未闭合\n第二行")).toEqual([
      { kind: "text", value: "第一行 $未闭合\n第二行" },
    ]);
  });

  it("空字符串返回空数组", () => {
    expect(splitMathText("")).toEqual([]);
  });
});
