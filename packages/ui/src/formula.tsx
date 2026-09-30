"use client";

import katex from "katex";
import type { HTMLAttributes } from "react";

import { cn } from "./cn";

export interface MathFormulaProps extends HTMLAttributes<HTMLSpanElement> {
  formula: string;
  displayMode?: boolean;
}

/**
 * 数学公式渲染（KaTeX；样式由宿主应用引入 katex 主题）。
 * 从 data.tsx 独立出来：学习域组件（QuestionCard / ExplainerFrame）也要用它，
 * 而 data.tsx 依赖 recharts，不应让公式渲染被图表依赖拖累。
 */
export function MathFormula({ className, formula, displayMode = false, ...props }: MathFormulaProps) {
  let html = "";
  try {
    html = katex.renderToString(formula, { throwOnError: false, displayMode });
  } catch {
    html = formula;
  }
  return (
    <span
      className={cn("text-app", displayMode && "block text-center", className)}
      // KaTeX 输出为受控 HTML（throwOnError=false 不执行脚本）
      dangerouslySetInnerHTML={{ __html: html }}
      {...props}
    />
  );
}
