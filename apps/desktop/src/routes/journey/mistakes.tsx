"use client";

/** 旅程第 5 站 · 错题复习：错题本 + 复习卡（FSRS 到期）。 */
import { Badge, Button, Card, CardContent, CardHeader, CardTitle } from "@xueban/ui";
import { useCallback, useState } from "react";

import { AsyncFeedback, JourneyStepper } from "@/components/journey-blocks";
import { StageShell } from "@/components/stage-shell";
import { api, type ReviewGrade } from "@/lib/api";
import { useJourney } from "@/journey/journey-context";
import { useMistakes, useReviewDue } from "@/journey/use-journey-data";

const GRADES = [
  { grade: 1, label: "忘了" },
  { grade: 2, label: "有点难" },
  { grade: 3, label: "想起来了" },
  { grade: 4, label: "很简单" },
] as const;

function GradeActions({
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

export default function MistakesStagePage() {
  const { mark, goTo } = useJourney();
  const mistakes = useMistakes();
  const review = useReviewDue();
  const [graded, setGraded] = useState<Record<string, ReviewGrade>>({});
  const [busy, setBusy] = useState(false);

  const grade = useCallback(
    async (cardId: string, value: number) => {
      setBusy(true);
      try {
        const result = await api.reviewGrade(cardId, value);
        setGraded((prev) => ({ ...prev, [cardId]: result }));
        await review.reload();
      } finally {
        setBusy(false);
      }
    },
    [review],
  );

  const finish = useCallback(() => {
    mark({ mistakesLogged: true });
    goTo("review");
  }, [goTo, mark]);

  const entries = mistakes.data?.entries ?? [];
  const cards = review.data?.cards ?? [];

  return (
    <StageShell
      stage="mistakes"
      title="错题复习"
      description="答错的题会自动进入错题本；到期的复习卡按掌握程度评分，系统据此安排下次复习。"
      speakable
      data-testid="stage-mistakes"
    >
      <div className="flex flex-col gap-md">
        <AsyncFeedback
          loading={review.loading}
          error={review.error}
          empty={!review.loading && cards.length === 0}
          emptyTitle="今天没有到期的复习卡"
          emptyHint="把错题本里的题重做一遍，系统会自动安排复习时间。"
          onRetry={() => void review.reload()}
        >
          <section aria-label="到期复习卡" className="flex flex-col gap-sm" data-testid="review-due">
            <h3 className="text-app-lg font-semibold">到期复习卡（{cards.length}）</h3>
            {cards.map((card) => (
              <Card key={card.card_id} data-testid={`review-card-${card.card_id}`}>
                <CardHeader>
                  <CardTitle>{card.question.stem}</CardTitle>
                </CardHeader>
                <CardContent className="flex flex-col gap-sm">
                  <GradeActions
                    cardId={card.card_id}
                    done={graded[card.card_id]}
                    busy={busy}
                    onGrade={grade}
                  />
                </CardContent>
              </Card>
            ))}
          </section>
        </AsyncFeedback>

        <AsyncFeedback
          loading={mistakes.loading}
          error={mistakes.error}
          empty={!mistakes.loading && entries.length === 0}
          emptyTitle="错题本还是空的"
          emptyHint="练习中答错的题会自动收录到这里。"
          onRetry={() => void mistakes.reload()}
        >
          <section aria-label="错题本" className="flex flex-col gap-sm" data-testid="mistake-list">
            <h3 className="text-app-lg font-semibold">
              错题本（{mistakes.data?.active_count ?? 0}）
            </h3>
            {entries.map((entry) => (
              <Card key={entry.id} data-testid={`mistake-${entry.id}`}>
                <CardHeader>
                  <CardTitle>{entry.question.stem}</CardTitle>
                </CardHeader>
                <CardContent className="flex flex-wrap items-center gap-xs">
                  <Badge variant={entry.state === "mastered" ? "success" : "warning"}>
                    {entry.state === "mastered" ? "已掌握" : "待巩固"}
                  </Badge>
                  <span className="text-app-xs text-muted-foreground">
                    错因：{entry.error_reason_label} · 已复习 {entry.review_count} 次
                  </span>
                </CardContent>
              </Card>
            ))}
          </section>
        </AsyncFeedback>

        <Button onClick={finish} data-testid="mistakes-to-review">
          完成复习，去复盘
        </Button>
        <JourneyStepper />
      </div>
    </StageShell>
  );
}
