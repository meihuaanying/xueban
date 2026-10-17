/**
 * 富文本公式渲染（Web）：把 `$...$` / `$$...$$` 片段交给 KaTeX，其余按文本渲染。
 *
 * 切分规则来自 `@xueban/core` 的 `splitMathText`（三端共享，§8 约束 7）；
 * 本文件只负责「切好之后怎么画」——Web 端画 KaTeX。
 */

import { splitMathText } from "@xueban/core";
import { MathFormula } from "@xueban/ui";
import type { ReactNode } from "react";

export function MathText({ content }: { content: string }) {
  const nodes: ReactNode[] = splitMathText(content).map((segment, index) => {
    if (segment.kind === "display") {
      return <MathFormula key={index} formula={segment.value} displayMode />;
    }
    if (segment.kind === "inline") {
      return <MathFormula key={index} formula={segment.value} />;
    }
    return (
      <span key={index} className="whitespace-pre-wrap">
        {segment.value}
      </span>
    );
  });
  return <div className="space-y-2 leading-7">{nodes}</div>;
}
