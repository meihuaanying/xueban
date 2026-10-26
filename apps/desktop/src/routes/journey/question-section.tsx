"use client";

/**
 * 学习单元页的题卡块。
 *
 * 从 `unit-blocks.tsx` 拆出来的原因不是「文件太长」，而是**它自己就有一份独立的
 * 题型映射责任**（qtype → 作答形态），那套规则与反馈卡、提示卡毫无关系。
 * 混在一起时，改题型映射要在一个塞了三块 UI 的文件里翻。
 */

import { QuestionCard } from "@xueban/ui";

import type { PracticeQuestion } from "@/lib/api";
import { parseLinkItems, resolveKind, toLinkSubmit, toOptions } from "./question-kinds";

/** 已出题时的题卡容器（`unit-question` 仅在有题时渲染）。
 *
 * 六种小学题型各有各的作答形态，不能一律当 choice 渲染——那样生成的
 * judge/match/oral/pick_hanzi 题孩子根本没法答（match 会把形状池当单选，
 * judge/oral 因为没有 options 会掉进文本框）。
 */
export function QuestionSection({
  question,
  index,
  total,
  busy,
  speakable,
  onAnswer,
}: {
  question: Pick<PracticeQuestion, "stem" | "qtype" | "options" | "difficulty">;
  index: number;
  total: number;
  busy: boolean;
  speakable: boolean;
  onAnswer: (value: string) => void;
}) {
  const kind = resolveKind(question.qtype);
  const options = toOptions(question.options);
  const linkItems = kind === "link" ? parseLinkItems(question.stem) : [];
  // 取不到左项就别硬撑连线台，退回普通选项形态，至少还能选
  const usableKind = kind === "link" && linkItems.length === 0 ? "choice" : kind;
  return (
    <div className="flex flex-col gap-sm" data-testid="unit-question">
      <p className="text-app-xs text-muted-foreground">
        第 {index + 1} / {total} 题
      </p>
      <QuestionCard
        stem={question.stem}
        meta={`难度 ${question.difficulty}`}
        kind={usableKind}
        options={options}
        linkItems={linkItems}
        onLinkPairs={(pairs, complete) => {
          if (complete) onAnswer(toLinkSubmit(pairs));
        }}
        speakable={speakable}
        disabled={busy}
        onSelect={onAnswer}
      />
    </div>
  );
}
