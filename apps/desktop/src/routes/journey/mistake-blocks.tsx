"use client";

/**
 * 错题本列表（旅程第 5 站）。
 *
 * 单独成文件有两个理由：
 * 1. `mistakes.tsx` 原本已经 158 行，超出 §8 约束 7 的 150 行上限；
 * 2. 场景 2（错题详情 → 动画讲解）要往每条卡里加入口按钮，放在这里最贴近语境。
 */

import { Badge, Button, Card, CardContent, CardHeader, CardTitle } from "@xueban/ui";

import type { MistakeEntry, ReviewGrade } from "@/lib/api";
import { ExplainerTrigger } from "./explainer-launcher";

const GRADES = [
  { grade: 1, label: "忘了" },
  { grade: 2, label: "有点难" },
  { grade: 3, label: "想起来了" },
  { grade: 4, label: "很简单" },
] as const;

/** FSRS 评分按钮组；评分后原地换成「下次复习时间」，避免重复提交。 */
export function GradeActions({
  cardId,
  done,
  busy,
  onGrade,
}: {
  cardId: string;
  done: ReviewGrade | undefined;
  busy: boolean;
  onGrade: (cardId: string, value: number) => Promise<void>;
}) {
  if (done) {
    return (
      <p className="text-app-sm text-success-foreground">
        已记录：下次 {done.interval_days} 天后复习
      </p>
    );
  }
  return (
    <div className="flex flex-wrap gap-xs">
      {GRADES.map((item) => (
        <Button
          key={item.grade}
          variant="outline"
          disabled={busy}
          onClick={() => void onGrade(cardId, item.grade)}
          data-testid={`review-grade-${cardId}-${item.grade}`}
        >
          {item.label}
        </Button>
      ))}
    </div>
  );
}

export interface MistakeListProps {
  entries: MistakeEntry[];
  /** kids 主题下才朗读与放大热区（§4.1）。 */
  speakable?: boolean;
  /** 某条错题触发讲解时的回调（传知识点编码）。 */
  onOpenExplainer: (knowledgeId: string) => void;
}

/** 取这道题挂在哪个知识点上；取不到就不给讲解入口。
 *
 * 必须用 `knowledge_point_ids`（库内 UUID）而不是 `knowledge_points`（显示名）：
 * 讲解接口只认 id，传显示名后端一律 404 `CURRICULUM_POINT_NOT_FOUND`。 */
export function knowledgeIdOf(entry: MistakeEntry): string {
  return entry.question?.knowledge_point_ids?.[0] ?? "";
}

export function MistakeList({ entries, speakable = false, onOpenExplainer }: MistakeListProps) {
  return (
    <section aria-label="错题本" className="flex flex-col gap-sm" data-testid="mistake-list">
      <h3 className="text-app-lg font-semibold">错题本（{entries.length}）</h3>
      {entries.map((entry) => {
        const knowledgeId = knowledgeIdOf(entry);
        return (
          <Card key={entry.id} data-testid={`mistake-${entry.id}`}>
            <CardHeader>
              <CardTitle>{entry.question.stem}</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-sm">
              <div className="flex flex-wrap items-center gap-xs">
                <Badge variant={entry.state === "mastered" ? "success" : "warning"}>
                  {entry.state === "mastered" ? "已掌握" : "待巩固"}
                </Badge>
                <span className="text-app-xs text-muted-foreground">
                  错因：{entry.error_reason_label} · 已复习 {entry.review_count} 次
                </span>
              </div>
              {/* 场景 2（§5.1）：错题详情 →「动画讲解这个知识点」 */}
              <div className="flex flex-wrap items-center gap-xs">
                <ExplainerTrigger
                  knowledgeId={knowledgeId}
                  testId={`mistake-explainer-${entry.id}`}
                  speakable={speakable}
                  onOpen={onOpenExplainer}
                />
              </div>
            </CardContent>
          </Card>
        );
      })}
    </section>
  );
}
