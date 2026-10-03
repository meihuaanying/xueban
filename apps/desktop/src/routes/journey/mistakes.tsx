"use client";

/** 旅程第 5 站 · 错题复习：错题本 + 复习卡（FSRS 到期）+ 动画讲解入口（场景 2）。 */
import { Button, Card, CardContent, CardHeader, CardTitle } from "@xueban/ui";
import { useCallback, useState } from "react";

import { AsyncFeedback, JourneyStepper } from "@/components/journey-blocks";
import { StageShell } from "@/components/stage-shell";
import { api, type ReviewGrade } from "@/lib/api";
import { useExplainer } from "@/journey/use-explainer";
import { useJourney } from "@/journey/journey-context";
import { useMistakes, useReviewDue } from "@/journey/use-journey-data";
import { ExplainerDock } from "./explainer-launcher";
import { GradeActions, MistakeList } from "./mistake-blocks";

export default function MistakesStagePage() {
  const { mark, goTo, theme } = useJourney();
  const mistakes = useMistakes();
  const review = useReviewDue();
  const explainer = useExplainer();
  const [graded, setGraded] = useState<Record<string, ReviewGrade>>({});
  const [busy, setBusy] = useState(false);
  // 当前打开讲解的知识点；空表示用户还没点任何入口（此时不渲染面板）
  const [explainKnowledgeId, setExplainKnowledgeId] = useState("");
  const speakable = theme === "kids";

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
          <MistakeList
            entries={entries}
            speakable={speakable}
            onOpenExplainer={(knowledgeId) => {
              setExplainKnowledgeId(knowledgeId);
              void explainer.open(knowledgeId);
            }}
          />
        </AsyncFeedback>

        {/* 场景 2（§5.1）：讲解面板只显示一份，点哪条看哪条 */}
        <ExplainerDock explainer={explainer} knowledgeId={explainKnowledgeId} speakable={speakable} />

        <Button onClick={finish} data-testid="mistakes-to-review">
          完成复习，去复盘
        </Button>
        <JourneyStepper />
      </div>
    </StageShell>
  );
}
