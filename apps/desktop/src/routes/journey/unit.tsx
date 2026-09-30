"use client";

/** 阶段页：学习单元（第 4 站）——讲解 ⇄ 练习循环 + 三层提示 */
import { useCallback, useState } from "react";
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  HintStack,
  HintLevel,
  QuestionCard,
} from "@xueban/ui";

import { JourneyStepper } from "../../components/journey-blocks";
import { StageShell } from "../../components/stage-shell";
import { useJourney } from "../../journey/journey-context";
import { GRADE_BANDS } from "../../journey/stages";
import { usePractice } from "../../journey/use-journey-data";
import { api, type TutorHint, type TutorSession } from "../../lib/api";

export default function UnitStagePage() {
  const { band, theme, mark, goTo } = useJourney();
  const preset = band ? GRADE_BANDS[band] : GRADE_BANDS.primary;
  const practice = usePractice(preset.subject);
  const [session, setSession] = useState<TutorSession | null>(null);
  const [hints, setHints] = useState<TutorHint[]>([]);
  const [revealed, setRevealed] = useState(1);
  const [tutorError, setTutorError] = useState<string | null>(null);

  const openTutor = useCallback(async (questionId: string) => {
    setHints([]);
    setRevealed(1);
    setTutorError(null);
    try {
      const created = await api.createTutorSession(questionId);
      setSession(created);
      // 守护型红线：进入讲解即给第 1 层提示，后续层由学生主动索取
      const first = await api.tutorHint(created.session_id);
      setHints([first]);
      setRevealed(first.level ?? 1);
    } catch (caught) {
      // 不静默失败：LLM 不可用时也要明确告知，而不是留下空白提示区
      setTutorError(
        caught instanceof Error ? caught.message : "讲解加载失败，请稍后重试。",
      );
    }
  }, []);

  const askHint = useCallback(
    async (level?: number) => {
      if (!session) return;
      try {
        const next = await api.tutorHint(session.session_id, level);
        setHints((prev) =>
          prev.some((item) => item.level === next.level) ? prev : [...prev, next],
        );
        if (next.level) setRevealed(next.level);
      } catch (caught) {
        setTutorError(
          caught instanceof Error ? caught.message : "提示加载失败，请稍后重试。",
        );
      }
    },
    [session],
  );

  const current = practice.current;
  const options = current?.options
    ? Object.entries(current.options).map(([key, label]) => ({ key, label }))
    : [];

  return (
    <StageShell
      stage="unit"
      title="学习单元"
      description="看懂 → 练一练 → 再看讲解，循环到掌握为止。"
      speakable={theme === "kids"}
      data-testid="stage-unit"
    >
      <div className="flex flex-col gap-md">
        {!current ? (
          <Card>
            <CardHeader>
              <CardTitle>生成练习</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col items-start gap-sm">
              <p className="text-app-sm text-muted-foreground">
                优先出你薄弱知识点的题，做错会自动进错题本。
              </p>
              {practice.error ? <p className="text-app-sm text-destructive">{practice.error}</p> : null}
              <Button
                type="button"
                data-testid="unit-generate"
                disabled={practice.busy}
                onClick={() => void practice.generate()}
              >
                {practice.busy ? "出题中…" : "生成练习"}
              </Button>
            </CardContent>
          </Card>
        ) : (
          <div className="flex flex-col gap-sm" data-testid="unit-question">
            <p className="text-app-xs text-muted-foreground">
              第 {practice.index + 1} / {practice.set?.questions.length ?? 0} 题
            </p>
            <QuestionCard
              stem={current.stem}
              meta={`难度 ${current.difficulty}`}
              kind={current.qtype === "fill" ? "fill" : "choice"}
              options={options}
              speakable={theme === "kids"}
              disabled={practice.busy}
              onSelect={(value) => void practice.answer(current.id, value)}
            />
          </div>
        )}

        {practice.last ? (
          <Card data-testid="unit-feedback">
            <CardHeader>
              <CardTitle className={practice.last.is_correct ? "text-success" : "text-warning"}>
                {practice.last.is_correct ? "回答正确" : "还没掌握"}
              </CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col items-start gap-sm">
              <p className="text-app-sm text-foreground">{practice.last.explanation}</p>
              {practice.last.mistake_collected ? <Badge variant="warning">已加入错题本</Badge> : null}
              <div className="flex gap-sm">
                <Button
                  type="button"
                  variant="outline"
                  data-testid="unit-open-tutor"
                  onClick={() => void openTutor(current!.id)}
                >
                  看讲解
                </Button>
                <Button type="button" data-testid="unit-next" onClick={practice.next}>
                  下一题
                </Button>
              </div>
            </CardContent>
          </Card>
        ) : null}

        {session ? (
          <Card data-testid="unit-tutor">
            <CardHeader>
              <CardTitle>讲解 · 守护型三层提示</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-sm">
              {tutorError ? (
                <p
                  className="text-app-sm text-destructive"
                  data-testid="unit-tutor-error"
                >
                  {tutorError}
                </p>
              ) : null}
              <HintStack
                hints={hints.map((item) => ({
                  level: Math.min(Math.max(item.level, 1), 3) as HintLevel,
                  text: item.content,
                }))}
                revealed={revealed}
                onReveal={(level) => void askHint(level)}
                speakable={theme === "kids"}
                fallback={
                  <Button
                    type="button"
                    data-testid="unit-to-mistakes"
                    onClick={() => {
                      mark({ unitVisited: true });
                      goTo("mistakes");
                    }}
                  >
                    去做错题复习
                  </Button>
                }
              />
            </CardContent>
          </Card>
        ) : null}

        <JourneyStepper />
      </div>
    </StageShell>
  );
}
