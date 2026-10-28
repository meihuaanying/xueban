"use client";

/** 错题重练面板：独立文件，避免错题页超过 150 行。 */
import { Button, Card, CardContent, CardHeader, CardTitle } from "@xueban/ui";

import { useJourney } from "@/journey/journey-context";
import { GRADE_BANDS } from "@/journey/stages";
import { useRepractice } from "@/journey/use-repractice";
import { QuestionSection } from "./question-section";
import { FeedbackCard } from "./unit-blocks";

export function RepracticePanel({
  onAnswered,
  onOpenExplainer,
  speakable,
}: {
  onAnswered: () => void;
  onOpenExplainer: (knowledgeId: string) => void;
  speakable: boolean;
}) {
  const repractice = useRepractice();
  const { band, subject } = useJourney();
  const current = repractice.current;

  const start = () =>
    void repractice.start(5, {
      subject,
      stage: band ? GRADE_BANDS[band].stage : undefined,
    });
  const submit = async (value: string) => {
    const result = await repractice.answer(value);
    if (result) onAnswered();
  };
  const explain = () => {
    const knowledgeId = current?.knowledge_point_ids[0];
    if (knowledgeId) onOpenExplainer(knowledgeId);
  };

  if (!repractice.set && repractice.busy) {
    return (
      <Card data-testid="repractice-loading">
        <CardHeader>
          <CardTitle>错题重练</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-app-sm text-muted-foreground">正在从错题本挑题…</p>
        </CardContent>
      </Card>
    );
  }

  if (!repractice.set && !repractice.busy) {
    return (
      <Card data-testid="repractice-panel">
        <CardHeader>
          <CardTitle>错题重练</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col items-start gap-sm">
          <p className="text-app-sm text-muted-foreground">
            从错题本抽 5 道题重做；答对并达到移出条件后自动出本。
          </p>
          {repractice.error ? (
            <p className="text-app-sm text-destructive" data-testid="repractice-error">
              {repractice.error}
            </p>
          ) : null}
          <Button type="button" data-testid="repractice-start" onClick={start}>
            开始重练
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (repractice.set && repractice.set.questions.length === 0 && !repractice.busy) {
    return (
      <Card data-testid="repractice-empty">
        <CardHeader>
          <CardTitle>错题重练</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col items-start gap-sm">
          <p className="text-app-sm text-muted-foreground">
            当前没有可重练的错题；继续保持，错题会在这里出现。
          </p>
          <Button type="button" variant="outline" data-testid="repractice-again" onClick={start}>
            重新检查
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (repractice.finished) {
    return (
      <Card data-testid="repractice-finished">
        <CardHeader>
          <CardTitle className="text-success">本组重练完成</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col items-start gap-sm">
          <p className="text-app-sm text-foreground">错题本与复习卡已按本次作答更新。</p>
          <Button type="button" data-testid="repractice-again" onClick={start}>
            再练一组
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card data-testid="repractice-running">
      <CardHeader>
        <CardTitle>错题重练</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-sm">
        {repractice.error ? (
          <p className="text-app-sm text-destructive" data-testid="repractice-error">
            {repractice.error}
          </p>
        ) : null}
        {current ? (
          <QuestionSection
            question={current}
            index={repractice.index}
            total={repractice.set?.questions.length ?? 0}
            busy={repractice.busy}
            speakable={speakable}
            onAnswer={(value) => void submit(value)}
          />
        ) : null}
        {repractice.last ? (
          <FeedbackCard
            isCorrect={repractice.last.is_correct}
            explanation={repractice.last.explanation}
            mistakeCollected={repractice.last.mistake_collected}
            onOpenTutor={explain}
            onNext={() => repractice.next()}
          />
        ) : null}
      </CardContent>
    </Card>
  );
}
