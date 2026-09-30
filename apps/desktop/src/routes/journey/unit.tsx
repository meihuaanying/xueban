"use client";

/** 阶段页：学习单元（第 4 站）——讲解 ⇄ 练习循环 + 三层提示 */

import { Button } from "@xueban/ui";

import { JourneyStepper } from "../../components/journey-blocks";
import { StageShell } from "../../components/stage-shell";
import { useJourney } from "../../journey/journey-context";
import { GRADE_BANDS } from "../../journey/stages";
import { usePractice } from "../../journey/use-journey-data";
import { useTutorHints } from "../../journey/use-tutor";
import {
  FeedbackCard,
  GenerateCard,
  QuestionSection,
  TutorCard,
} from "./unit-blocks";

export default function UnitStagePage() {
  const { band, theme, mark, goTo } = useJourney();
  const preset = band ? GRADE_BANDS[band] : GRADE_BANDS.primary;
  const practice = usePractice(preset.subject);
  const tutor = useTutorHints();
  const current = practice.current;
  const speakable = theme === "kids";

  return (
    <StageShell
      stage="unit"
      title="学习单元"
      description="看懂 → 练一练 → 再看讲解，循环到掌握为止。"
      speakable={speakable}
      data-testid="stage-unit"
    >
      <div className="flex flex-col gap-md">
        {current ? (
          <QuestionSection
            question={current}
            index={practice.index}
            total={practice.set?.questions.length ?? 0}
            busy={practice.busy}
            speakable={speakable}
            onAnswer={(value) => void practice.answer(current.id, value)}
          />
        ) : (
          <GenerateCard
            busy={practice.busy}
            error={practice.error}
            onGenerate={() => void practice.generate()}
          />
        )}

        {practice.last ? (
          <FeedbackCard
            isCorrect={practice.last.is_correct}
            explanation={practice.last.explanation}
            mistakeCollected={practice.last.mistake_collected}
            onOpenTutor={() => {
              if (current) void tutor.openTutor(current.id);
            }}
            onNext={practice.next}
          />
        ) : null}

        {tutor.session ? (
          <TutorCard
            hints={tutor.hints}
            revealed={tutor.revealed}
            error={tutor.error}
            speakable={speakable}
            onReveal={(level) => void tutor.askHint(level)}
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
        ) : null}

        <JourneyStepper />
      </div>
    </StageShell>
  );
}
