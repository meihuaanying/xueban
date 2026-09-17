/** 富文本公式渲染：把 $...$ / $$...$$ 片段交给 KaTeX，其余按文本渲染。 */

import { MathFormula } from "@xueban/ui";
import type { ReactNode } from "react";

const SEGMENT_PATTERN = /(\$\$[^$]+\$\$|\$[^$\n]+\$)/g;

export function MathText({ content }: { content: string }) {
  const parts = content.split(SEGMENT_PATTERN).filter((part) => part.length > 0);
  const nodes: ReactNode[] = parts.map((part, index) => {
    if (part.startsWith("$$") && part.endsWith("$$") && part.length > 4) {
      return <MathFormula key={index} formula={part.slice(2, -2)} displayMode />;
    }
    if (part.startsWith("$") && part.endsWith("$") && part.length > 2) {
      return <MathFormula key={index} formula={part.slice(1, -1)} />;
    }
    return (
      <span key={index} className="whitespace-pre-wrap">
        {part}
      </span>
    );
  });
  return <div className="space-y-2 leading-7">{nodes}</div>;
}
