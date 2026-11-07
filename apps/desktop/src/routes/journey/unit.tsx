"use client";

/** 阶段页：学习单元（第 4 站）——讲解 ⇄ 练习循环 + 三层提示 + 交互讲解（§5.1） */

import { Button } from "@xueban/ui";
import { useSearchParams } from "react-router-dom";

import { JourneyStepper } from "../../components/journey-blocks";
import { StageShell } from "../../components/stage-shell";
import { useExplainer } from "../../journey/use-explainer";
import { useJourney } from "../../journey/journey-context";
import { GRADE_BANDS } from "../../journey/stages";
import { usePractice } from "../../journey/use-journey-data";
import { useSoundPreference } from "../../journey/use-sound";
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
  const { band, grade, subject, theme, mark, goTo } = useJourney();
  const [search] = useSearchParams();
  // 今日任务卡带 ?kp=<知识点 UUID> 进来：学习单元按该知识点出题，
  // 而不是又随机抽一组题，任务与练习才真正对得上。
  const kp = search.get("kp");
  const preset = band ? GRADE_BANDS[band] : GRADE_BANDS.primary;
  const practice = usePractice(subject, grade ?? preset.grade, kp ? [kp] : undefined);
  const tutor = useTutorHints();
  const explainer = useExplainer();
  const sound = useSoundPreference();
  const current = practice.current;
  const speakable = theme === "kids";

  // 讲解绑定到当前题的第一个知识点；没有题时不自动开，避免空知识点生成垃圾讲解。
  // 必须用 knowledge_point_ids（库内 UUID）：讲解接口只认 id，显示名会被判 404。
  const knowledgeId = current?.knowledge_point_ids?.[0] ?? "";
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

        {/* §5.3：高中生可主动看预生成视频；未预生成时 hook 会自动回落互动讲解。 */}
        {band === "senior" && knowledgeId ? (
          <div className="flex flex-wrap items-center gap-sm" data-testid="unit-video-row">
            <Button
              type="button"
              variant="outline"
              data-testid="unit-video-explainer"
              disabled={explainer.status === "pending"}
              onClick={() => void explainer.open(knowledgeId, "video")}
            >
              看视频讲解
            </Button>
            <span className="text-app-xs text-muted-foreground">
              视频还没准备好时，会自动切到互动讲解
            </span>
          </div>
        ) : null}

        {practice.last ? (
          <FeedbackCard
            isCorrect={practice.last.is_correct}
            explanation={practice.last.explanation}
            mistakeCollected={practice.last.mistake_collected}
            sound={sound.enabled}
            answerKey={practice.index}
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
            notice={explainer.notice}
            speakable={speakable}
            busy={practice.busy}
            onOpen={() => void explainer.open(knowledgeId)}
            // 视频是 §5.3 离线预生成产物，目前只给高中生入口；未预生成会自动回落互动讲解。
            onOpenVideo={
              band === "senior" ? () => void explainer.open(knowledgeId, "video") : undefined
            }
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
