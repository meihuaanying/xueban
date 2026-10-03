"use client";

/** 学习单元页（第 4 站）的三块 UI：出题卡、答题反馈卡、讲解三层提示卡。 */

import type { ReactNode } from "react";
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  HintStack,
  type HintLevel,
  QuestionCard,
} from "@xueban/ui";

import type { PracticeQuestion, TutorHint } from "@/lib/api";
import { parseLinkItems, resolveKind, toLinkSubmit, toOptions } from "./question-kinds";

/** 未出题时的引导卡。 */
export function GenerateCard({
  busy,
  error,
  onGenerate,
}: {
  busy: boolean;
  error: string | null;
  onGenerate: () => void;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>生成练习</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col items-start gap-sm">
        <p className="text-app-sm text-muted-foreground">
          优先出你薄弱知识点的题，做错会自动进错题本。
        </p>
        {error ? <p className="text-app-sm text-destructive">{error}</p> : null}
        <Button type="button" data-testid="unit-generate" disabled={busy} onClick={onGenerate}>
          {busy ? "出题中…" : "生成练习"}
        </Button>
      </CardContent>
    </Card>
  );
}

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
  question: PracticeQuestion;
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

/** 答题反馈卡：即时反馈 + 「看讲解」/「下一题」两个出口。 */
export function FeedbackCard({
  isCorrect,
  explanation,
  mistakeCollected,
  onOpenTutor,
  onNext,
}: {
  isCorrect: boolean;
  explanation: string | null | undefined;
  mistakeCollected: boolean;
  onOpenTutor: () => void;
  onNext: () => void;
}) {
  return (
    <Card data-testid="unit-feedback">
      <CardHeader>
        <CardTitle className={isCorrect ? "text-success" : "text-warning"}>
          {isCorrect ? "回答正确" : "还没掌握"}
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col items-start gap-sm">
        <p className="text-app-sm text-foreground">{explanation}</p>
        {mistakeCollected ? <Badge variant="warning">已加入错题本</Badge> : null}
        <div className="flex gap-sm">
          <Button type="button" variant="outline" data-testid="unit-open-tutor" onClick={onOpenTutor}>
            看讲解
          </Button>
          <Button type="button" data-testid="unit-next" onClick={onNext}>
            下一题
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

/** 讲解卡：守护型三层提示栈，红线默认只给第 1 层。 */
export function TutorCard({
  hints,
  revealed,
  error,
  speakable,
  onReveal,
  fallback,
}: {
  hints: TutorHint[];
  revealed: number;
  error: string | null;
  speakable: boolean;
  onReveal: (level: number) => void;
  fallback: ReactNode;
}) {
  return (
    <Card data-testid="unit-tutor">
      <CardHeader>
        <CardTitle>讲解 · 守护型三层提示</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-sm">
        {error ? (
          <p className="text-app-sm text-destructive" data-testid="unit-tutor-error">
            {error}
          </p>
        ) : null}
        <HintStack
          hints={hints.map((item) => ({
            level: Math.min(Math.max(item.level, 1), 3) as HintLevel,
            text: item.content,
          }))}
          revealed={revealed}
          onReveal={(level) => onReveal(level)}
          speakable={speakable}
          fallback={fallback}
        />
      </CardContent>
    </Card>
  );
}
