"use client";

/**
 * 图文分步降级视图（REBUILD §5.4：渲染失败或超时必须降级，禁止白屏）。
 *
 * 独立成文件的理由：这个视图是**讲解页彻底跑不起来时的最后一道防线**，它必须比
 * 交互页更可靠——所以它连一行脚本都不依赖（纯 `<ol>` + 朗读按钮）。把它和
 * `ExplainerCard` 的四态机混在一个文件里，容易在改卡片时顺手改坏这条兜底路径，
 * 而这条路径一旦坏掉就是白屏。
 */

import { AudioButton } from "@xueban/ui";

import type { ExplainerContent } from "@/lib/api";

/** 教学脚本的一幕（后端 prompts.py 的 EXPLAINER 脚本结构）。 */
export interface ExplainerAct {
  name?: string;
  goal?: string;
  narration?: string;
}

function readActs(script: Record<string, unknown>): ExplainerAct[] {
  const acts = script.acts;
  if (Array.isArray(acts)) return acts as ExplainerAct[];
  // §5.3 视频讲解的脚本结构是 sequence.segments；降级时同样按幕展示台词。
  const sequence = script.sequence;
  if (Array.isArray(sequence)) return sequence as ExplainerAct[];
  return [];
}

/**
 * 直接复用后端产出的教学脚本：即使交互页没跑起来，讲解词也还能读给孩子听。
 */
export function ScriptFallback({
  content,
  speakable,
}: {
  content: ExplainerContent;
  speakable: boolean;
}) {
  const acts = readActs(content.script);
  if (acts.length === 0) {
    return (
      <p className="text-app-sm text-muted-foreground" data-testid="explainer-steps">
        这段讲解暂时放不出来，换个时间再看看吧。
      </p>
    );
  }
  return (
    <ol className="flex flex-col gap-sm" data-testid="explainer-steps">
      {acts.map((act, index) => (
        <li key={index} className="rounded-control border border-border-strong p-sm">
          <p className="text-app-xs font-semibold">
            第 {index + 1} 幕 · {act.name ?? "讲解"}
          </p>
          <p className="text-app-sm">{act.narration ?? act.goal ?? ""}</p>
          {speakable && act.narration ? <AudioButton text={act.narration} /> : null}
        </li>
      ))}
    </ol>
  );
}

/** 朗读用的旁白全文（把各幕讲解词接起来），供讲解卡上的「听讲解」按钮使用。 */
export function narrationOf(content: ExplainerContent): string {
  return readActs(content.script)
    .map((act) => act.narration ?? "")
    .join("");
}
