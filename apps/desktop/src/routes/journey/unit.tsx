"use client";

/** 阶段页：学习单元（第 4 站）——讲解 ⇄ 练习循环 + 三层提示 + 交互讲解（§5.1） */

import { Button } from "@xueban/ui";

import { JourneyStepper } from "../../components/journey-blocks";
import { StageShell } from "../../components/stage-shell";
import { useExplainer } from "../../journey/use-explainer";
import { useJourney } from "../../journey/journey-context";
import { GRADE_BANDS } from "../../journey/stages";
import { usePractice } from "../../journey/use-journey-data";
import { useTutorHints } from "../../journey/use-tutor";
import { ExplainerCard } from "./explainer-blocks";
import {
  FeedbackCard,
  GenerateCard,
  QuestionSection,
  TutorCard,
} from "./unit-blocks";

/** §5.1 触发场景 1：连续 2 次答错就自动建议动画讲解。 */
const SUGGEST_AFTER_WRONG = 2;

export default function UnitStagePage() {
  const { band, theme, mark, goTo } = useJourney();
  const preset = band ? GRADE_BANDS[band] : GRADE_BANDS.primary;
  const practice = usePractice(preset.subject);
  const tutor = useTutorHints();
  const explainer = useExplainer();
  const current = practice.current;
  const speakable = theme === "kids";

  // 讲解绑定到当前题的第一个知识点；没有题时不自动开，避免空知识点生成垃圾讲解。
  const knowledgeId = current?.knowledge_points?.[0] ?? "";
  const suggested = practice.wrongStreak >= SUGGEST_AFTER_WRONG && Boolean(knowledgeId);

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

        {/* §5.1 触发场景 1/2：连续答错自动建议；孩子主动关掉后不反复打扰。 */}
        {knowledgeId && !explainer.dismissed && (suggested || explainer.status !== "idle") ? (
          <ExplainerCard
            status={explainer.status}
            content={explainer.content}
            error={explainer.error}
            speakable={speakable}
            busy={practice.busy}
            onOpen={() => void explainer.open(knowledgeId)}
            onRetry={() => void explainer.open(knowledgeId)}
            onClose={explainer.close}
            onFeedback={(understood) => void explainer.feedback(understood)}
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
