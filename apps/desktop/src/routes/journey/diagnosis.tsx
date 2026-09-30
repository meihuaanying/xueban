"use client";

/** 阶段页：诊断（第 2 站） */
import { Button, Card, CardContent, CardHeader, CardTitle, QuestionCard } from "@xueban/ui";

import { AsyncFeedback, JourneyStepper } from "../../components/journey-blocks";
import { StageShell } from "../../components/stage-shell";
import { useJourney } from "../../journey/journey-context";
import { GRADE_BANDS } from "../../journey/stages";
import { useDiagnosis } from "../../journey/use-journey-data";

export default function DiagnosisStagePage() {
  const { band, theme, mark, goTo } = useJourney();
  const diag = useDiagnosis();
  const preset = band ? GRADE_BANDS[band] : GRADE_BANDS.primary;
  const question = diag.start?.question ?? null;
  const options = question?.options ?? null;
  const finished = diag.start ? !diag.start.question || Boolean(diag.last?.finished) : false;

  return (
    <StageShell
      stage="diagnosis"
      title="入学诊断"
      description="先做一次诊断，系统才知道从哪一步开始教你。"
      speakable={theme === "kids"}
      data-testid="stage-diagnosis"
    >
      <div className="flex flex-col gap-md">
        {!diag.start ? (
          <Card>
            <CardHeader>
              <CardTitle>开始诊断</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col items-start gap-sm">
              <p className="text-app-sm text-muted-foreground">
                共 10 题，答错也没关系——诊断只是为了定位你的薄弱点。
              </p>
              {diag.error ? <p className="text-app-sm text-destructive">{diag.error}</p> : null}
              <Button
                type="button"
                data-testid="diagnosis-start"
                disabled={diag.busy}
                onClick={() => void diag.begin(preset.subject, preset.grade)}
              >
                {diag.busy ? "准备中…" : "开始诊断"}
              </Button>
            </CardContent>
          </Card>
        ) : null}

        {diag.start && !finished && question ? (
          <AsyncFeedback error={diag.error}>
            <div className="flex flex-col gap-sm">
              <p className="text-app-xs text-muted-foreground" data-testid="diagnosis-progress">
                进度 {diag.start.progress.answered} / {diag.start.progress.total}
              </p>
              <QuestionCard
                stem={question.stem}
                meta={`难度 ${question.difficulty}`}
                kind={question.qtype === "fill" ? "fill" : "choice"}
                options={
                  options
                    ? Object.entries(options).map(([key, label]) => ({ key, label }))
                    : []
                }
                speakable={theme === "kids"}
                onSelect={(value) => void diag.answer(question.id, value)}
                disabled={diag.busy}
              />
            </div>
          </AsyncFeedback>
        ) : null}

        {finished ? (
          <Card className="border-success" data-testid="diagnosis-done">
            <CardHeader>
              <CardTitle className="text-success">诊断完成</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col items-start gap-sm">
              <p className="text-app-sm text-foreground">
                {diag.last?.is_correct === false
                  ? "这道题还没掌握，没关系，规划会重点练它。"
                  : "很好，接下来按你的结果生成学习规划。"}
              </p>
              <Button
                type="button"
                data-testid="diagnosis-to-plan"
                onClick={() => {
                  mark({ diagnosisDone: true });
                  goTo("plan");
                }}
              >
                生成学习规划
              </Button>
            </CardContent>
          </Card>
        ) : null}

        <JourneyStepper />
      </div>
    </StageShell>
  );
}
