"use client";

/** 19 题模考的三个视图：开场说明、作答、交卷报告（含解答题逐题批改）。 */

import { useState } from "react";

import {
  Badge,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Progress,
  QuestionCard,
} from "@xueban/ui";

import type {
  ExamCreate,
  ExamDiagnosis,
  ExamQuestion,
  ExamReport,
  ExamSubjectiveGrade,
} from "@/lib/api";

const KIND_BY_QTYPE: Record<string, "choice" | "multi" | "fill"> = {
  choice: "choice",
  multi_choice: "multi",
  fill: "fill",
};

const PART_HINT = ["8 道单选", "3 道多选", "3 道填空", "5 道解答（交卷后逐题批改）"];

function formatClock(seconds: number | null): string {
  if (seconds === null) return "—";
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(rest).padStart(2, "0")}`;
}

function asNumber(value: unknown): number | null {
  return typeof value === "number" ? value : null;
}

export function MockExamIntro({
  busy,
  error,
  onStart,
}: {
  busy: boolean;
  error: string | null;
  onStart: () => void;
}) {
  return (
    <Card data-testid="mock-exam-intro">
      <CardHeader>
        <CardTitle>新高考数学 · 19 题结构模考</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-sm">
        <p className="text-app-sm text-muted-foreground">时长 120 分钟，满分 150 分。</p>
        <ul className="flex flex-col gap-xs text-app-sm">
          {PART_HINT.map((item) => (
            <li key={item}>· {item}</li>
          ))}
        </ul>
        <p className="text-app-sm text-muted-foreground">
          多选题至少选两项；解答题按步骤给分，交卷后逐题批改，全部批完才出整卷总分。
        </p>
        {error ? (
          <p role="alert" data-testid="mock-exam-error" className="text-app-sm text-danger">
            {error}
          </p>
        ) : null}
        <Button data-testid="mock-exam-start" disabled={busy} onClick={onStart}>
          {busy ? "正在组卷…" : "开始模考"}
        </Button>
      </CardContent>
    </Card>
  );
}

export function ExamRunner({
  exam,
  current,
  index,
  answers,
  answeredCount,
  remaining,
  busy,
  error,
  onAnswer,
  onNavigate,
  onSubmit,
}: {
  exam: ExamCreate;
  current: ExamQuestion;
  index: number;
  answers: Record<string, string>;
  answeredCount: number;
  remaining: number | null;
  busy: boolean;
  error: string | null;
  onAnswer: (questionId: string, value: string) => void;
  onNavigate: (next: number) => void;
  onSubmit: () => void;
}) {
  const total = exam.questions.length;
  const kind = KIND_BY_QTYPE[current.qtype] ?? "fill";
  const isText = current.qtype === "short_answer" || current.qtype === "fill";
  const recorded = answers[current.id];

  return (
    <div className="flex flex-col gap-sm" data-testid="mock-exam-runner">
      <div className="flex flex-wrap items-center justify-between gap-sm">
        <Badge variant={remaining !== null && remaining <= 300 ? "danger" : "outline"}>
          剩余 {formatClock(remaining)}
        </Badge>
        <span className="text-app-sm text-muted-foreground" data-testid="mock-exam-progress">
          已答 {answeredCount} / {total}
        </span>
        <div className="w-40">
          <Progress value={answeredCount} max={total} label="作答进度" />
        </div>
      </div>

      <ol aria-label="题号" className="flex flex-wrap gap-xs">
        {exam.questions.map((item, order) => (
          <li key={item.id}>
            <button
              type="button"
              data-testid={`mock-exam-jump-${order + 1}`}
              aria-current={order === index ? "true" : undefined}
              onClick={() => onNavigate(order)}
              className={
                "min-h-[var(--tap-min)] min-w-[var(--tap-min)] rounded-control border px-xs text-app-sm " +
                (answers[item.id]
                  ? "border-success bg-success-soft text-success "
                  : "border-border-strong bg-card ") +
                (order === index ? "ring-2 ring-ring" : "")
              }
            >
              {order + 1}
            </button>
          </li>
        ))}
      </ol>

      <p className="text-app-xs text-muted-foreground">
        第 {index + 1} 题 / {total} 题 · {current.qtype === "short_answer" ? "解答题" : "客观题"}
      </p>

      {isText ? (
        <Card>
          <CardContent className="flex flex-col gap-xs">
            <p className="text-app-lg font-semibold">{current.stem}</p>
            <label className="text-app-sm text-muted-foreground" htmlFor={`exam-answer-${current.id}`}>
              你的{current.qtype === "short_answer" ? "解答过程" : "答案"}
            </label>
            <textarea
              id={`exam-answer-${current.id}`}
              data-testid="mock-exam-textarea"
              value={recorded ?? ""}
              rows={current.qtype === "short_answer" ? 6 : 2}
              maxLength={8000}
              disabled={busy}
              onChange={(event) => onAnswer(current.id, event.target.value)}
              className="w-full rounded-control border border-border-strong bg-card px-sm py-xs text-app text-foreground"
            />
            <p className="text-app-xs text-muted-foreground" data-testid="mock-exam-char-count">
              {(recorded ?? "").length} / 8000
            </p>
          </CardContent>
        </Card>
      ) : (
        <QuestionCard
          key={current.id}
          stem={current.stem}
          meta={`难度 ${current.difficulty}`}
          kind={kind}
          value={recorded}
          options={
            current.options
              ? Object.entries(current.options).map(([key, label]) => ({ key, label }))
              : []
          }
          onSelect={kind === "multi" ? undefined : (value) => onAnswer(current.id, value)}
          onConfirm={kind === "multi" ? (value) => onAnswer(current.id, value) : undefined}
          disabled={busy}
        />
      )}

      {kind === "multi" && recorded ? (
        <p className="text-app-sm text-success" data-testid="mock-exam-multi-recorded">
          已记录：{recorded}
        </p>
      ) : null}
      {error ? (
        <p role="alert" className="text-app-sm text-danger">
          {error}
        </p>
      ) : null}

      <div className="flex flex-wrap items-center gap-sm">
        <Button
          variant="outline"
          disabled={index === 0 || busy}
          onClick={() => onNavigate(index - 1)}
        >
          上一题
        </Button>
        <Button
          variant="outline"
          disabled={index >= total - 1 || busy}
          onClick={() => onNavigate(index + 1)}
        >
          下一题
        </Button>
        <Button data-testid="mock-exam-submit" disabled={busy} onClick={onSubmit}>
          {busy ? "交卷中…" : "交卷"}
        </Button>
      </div>
    </div>
  );
}

function SubjectiveGrader({
  order,
  question,
  initial,
  grade,
  busy,
  onGrade,
}: {
  order: number;
  question: ExamQuestion;
  initial: string;
  grade: ExamSubjectiveGrade | undefined;
  busy: boolean;
  onGrade: (questionId: string, answer: string) => void;
}) {
  const [draft, setDraft] = useState(initial);
  return (
    <Card data-testid={`subjective-${order}`}>
      <CardHeader>
        <CardTitle className="text-app">第 {order} 题 · 解答题</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-xs">
        <p className="text-app-sm">{question.stem}</p>
        {grade ? (
          <div data-testid={`subjective-result-${order}`} className="flex flex-col gap-xs">
            <p className="text-app font-semibold">
              得分 {grade.score} / {grade.max_score}
            </p>
            <p className="text-app-sm text-muted-foreground">{grade.summary}</p>
            {grade.steps.length ? (
              <ul className="flex flex-col gap-hair text-app-sm">
                {grade.steps.map((step, stepIndex) => (
                  <li key={`${step.step}-${stepIndex}`}>
                    {step.step}：{step.score} 分（{step.comment}）
                  </li>
                ))}
              </ul>
            ) : null}
            {grade.rewrite ? (
              <p className="text-app-sm">规范写法：{grade.rewrite}</p>
            ) : null}
          </div>
        ) : (
          <>
            <textarea
              data-testid={`subjective-input-${order}`}
              value={draft}
              rows={5}
              maxLength={8000}
              disabled={busy}
              onChange={(event) => setDraft(event.target.value)}
              className="w-full rounded-control border border-border-strong bg-card px-sm py-xs text-app"
            />
            <p className="text-app-xs text-muted-foreground" data-testid={`subjective-count-${order}`}>
              {draft.length} / 8000
            </p>
            <Button
              data-testid={`subjective-grade-${order}`}
              disabled={busy || draft.trim().length === 0}
              onClick={() => onGrade(question.id, draft.trim())}
            >
              提交批改
            </Button>
          </>
        )}
      </CardContent>
    </Card>
  );
}

export function ExamReportView({
  exam,
  report,
  answers,
  grades,
  subjectiveCount,
  busy,
  error,
  onGrade,
}: {
  exam: ExamCreate;
  report: ExamReport;
  answers: Record<string, string>;
  grades: Record<string, ExamSubjectiveGrade>;
  subjectiveCount: number;
  busy: boolean;
  error: string | null;
  onGrade: (questionId: string, answer: string) => void;
}) {
  const summary = report.summary;
  const objectiveEarned = asNumber(summary.objective_earned);
  const objectiveTotal = asNumber(summary.objective_total);
  // 服务端的 subjective_earned 只在全部批完后回写，这里以逐题 grades 为准
  const subjectiveEarned = Object.values(grades).reduce((sum, item) => sum + item.score, 0);
  const subjectiveTotal = asNumber(summary.subjective_total);
  const gradedCount = Object.keys(grades).length;
  const finalScore =
    Object.values(grades)
      .map((item) => item.exam_score)
      .find((value): value is number => value !== null) ?? asNumber(summary.score);
  const subjective = exam.questions.filter((item) => item.qtype === "short_answer");
  const objectiveRows = (report.diagnoses ?? []).filter(
    (item: ExamDiagnosis) => !item.subjective,
  );

  return (
    <div className="flex flex-col gap-sm" data-testid="mock-exam-report">
      {error ? (
        <p role="alert" data-testid="mock-exam-report-error" className="text-app-sm text-danger">
          {error}
        </p>
      ) : null}
      <Card>
        <CardHeader>
          <CardTitle>
            模考结果
            <Badge variant="outline" className="ml-xs">
              客观题自动判分
            </Badge>
          </CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-xs">
          {finalScore !== null ? (
            <p className="text-app-2xl font-semibold" data-testid="mock-exam-score">
              {finalScore} / 150
            </p>
          ) : (
            <p className="text-app-lg font-semibold" data-testid="mock-exam-pending">
              客观题 {objectiveEarned ?? "—"} / {objectiveTotal ?? "—"}，解答题待批改
            </p>
          )}
          <p className="text-app-sm text-muted-foreground">
            客观题 {objectiveEarned ?? "—"} / {objectiveTotal ?? "—"} · 解答题{" "}
            {subjectiveEarned ?? 0} / {subjectiveTotal ?? "—"}（已批 {gradedCount} /{" "}
            {subjectiveCount}）
          </p>
          {report.auto_submitted ? (
            <p className="text-app-sm text-warning">倒计时结束，已自动交卷。</p>
          ) : null}
        </CardContent>
      </Card>

      {subjective.map((question) => (
        <SubjectiveGrader
          key={question.id}
          order={exam.questions.indexOf(question) + 1}
          question={question}
          initial={answers[question.id] ?? ""}
          grade={grades[question.id]}
          busy={busy}
          onGrade={onGrade}
        />
      ))}

      <Card>
        <CardHeader>
          <CardTitle className="text-app">客观题逐题诊断</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-xs" data-testid="mock-exam-objective-diagnoses">
          {objectiveRows.map((item) => (
            <div key={item.question_id} className="flex flex-col gap-hair border-b border-border pb-xs">
              <p className="text-app-sm font-semibold">{item.stem}</p>
              <p className="text-app-sm">
                {item.is_correct ? (
                  <span className="text-success">答对了</span>
                ) : (
                  <span className="text-danger">答错了</span>
                )}
                <span className="text-muted-foreground">
                  {" "}
                  · 正确答案：{item.correct_answer}
                </span>
              </p>
              {item.analysis ? (
                <p className="text-app-xs text-muted-foreground">{item.analysis}</p>
              ) : null}
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
