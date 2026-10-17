/**
 * 富文本中的公式分段（全端共享，§8 约束 7：三端重复实现必须合并）。
 *
 * 三端（桌面 / 移动 / 官网）都要把题干里混排的 `$...$`（行内）与 `$$...$$`（独立）
 * 公式切出来，再交给各平台自己的渲染器。**切分规则是纯逻辑，必须只有一份**；
 * 「切出来之后怎么画」才是平台差异（Web 用 KaTeX，原生端用等宽文本兜底）。
 *
 * 本模块在拆 `math-text.tsx` 时抽出：此前 desktop 与 mobile 各写了一份**完全相同**的
 * 正则与判断（`SEGMENT_PATTERN` / `SEGMENTS`、两处 `startsWith` 分支），共 10 余行
 * 逐字重复的规则代码。规则一旦要调（例如支持 `\(...\)`），两边不同步就会让同一道题
 * 在两端显示不一致——这是纯逻辑必须共享的典型信号。
 */

/** 一个已切好的片段类型。 */
export type MathSegmentKind = "text" | "inline" | "display";

/** 切分结果。`text` 段的 `value` 是原文；`inline`/`display` 段的 `value` 是**去掉 `$` 定界符后的公式体**。 */
export interface MathSegment {
  kind: MathSegmentKind;
  value: string;
}

/**
 * 匹配 `$$...$$`（独立公式）或 `$...$`（行内公式）。
 *
 * 与原先两端各自实现的正则逐字一致：
 * - 独立公式不跨行、内容非空；
 * - 行内公式不跨行（`[^$\n]`）、内容非空。
 *
 * 用捕获组包住整段，这样 `String.split` 会把定界符一并留在结果里（见下方实现），
 * 从而在一次遍历里同时拿到文本段与公式段。
 */
const SEGMENT_PATTERN = /(\$\$[^$]+\$\$|\$[^$\n]+\$)/g;

/**
 * 把一段可能混排公式的文本切成片段序列。
 *
 * 判定顺序与边界条件都照搬原实现，避免重构改变显示行为：
 * - 先判 `$$`（长度 > 4 才算独立公式，即 `$$$$` 这类空壳当普通文本）；
 * - 再判 `$`（长度 > 2 才算行内公式，即 `$$` 当普通文本）；
 * - 其余一律按文本。
 *
 * @example
 * splitMathText("3 + 4 = $7$")
 * // [{ kind: "text", value: "3 + 4 = " }, { kind: "inline", value: "7" }]
 */
export function splitMathText(content: string): MathSegment[] {
  const parts = content.split(SEGMENT_PATTERN).filter((part) => part.length > 0);
  return parts.map((part) => {
    if (part.startsWith("$$") && part.endsWith("$$") && part.length > 4) {
      return { kind: "display", value: part.slice(2, -2) };
    }
    if (part.startsWith("$") && part.endsWith("$") && part.length > 2) {
      return { kind: "inline", value: part.slice(1, -1) };
    }
    return { kind: "text", value: part };
  });
}
