/** 练习页（T5.5 / F-17~F-19、F-20）：智能出题、错题本与重练、FSRS 复习、模考。 */

import { useCallback, useEffect, useState } from "react";
import {
  Alert,
  Badge,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Input,
  Label,
  Select,
  StatCard,
} from "@xueban/ui";

import { EmptyBlock, ErrorBlock, LoadingBlock, SectionTitle } from "@/components/state";
import {
  ApiError,
  api,
  type ExamCreate,
  type ExamReport,
  type MistakeList,
  type PracticeAnswer,
  type PracticeGenerate,
  type QuestionBrief,
  type ReviewCard,
} from "@/lib/api";

function QuestionOptions({
  options,
  value,
  onChange,
  prefix,
}: {
  options: Record<string, string> | null;
  value: string;
  onChange: (key: string) => void;
  prefix: string;
}) {
  if (!options) {
    return (
      <div className="space-y-2">
        <Label htmlFor={`${prefix}-answer`}>你的答案</Label>
        <Input
          id={`${prefix}-answer`}
          data-testid={`${prefix}-answer-input`}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder="请输入答案"
        />
      </div>
    );
  }
  return (
    <div className="flex flex-wrap gap-2">
      {Object.entries(options).map(([key, label]) => (
        <Button
          key={key}
          variant={value === key ? "primary" : "outline"}
          data-testid={`${prefix}-option-${key}`}
          onClick={() => onChange(key)}
        >
          {key}. {label}
        </Button>
      ))}
    </div>
  );
}

export default function PracticePage() {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // 智能出题
  const [subject, setSubject] = useState("math");
  const [count, setCount] = useState("5");
  const [practice, setPractice] = useState<PracticeGenerate | null>(null);
  const [activeQuestion, setActiveQuestion] = useState<PracticeGenerate["questions"][number] | null>(null);
  const [answer, setAnswer] = useState("");
  const [feedback, setFeedback] = useState<PracticeAnswer | null>(null);

  // 错题本
  const [mistakes, setMistakes] = useState<MistakeList | null>(null);
  const [repracticeQuestions, setRepracticeQuestions] = useState<QuestionBrief[]>([]);
  const [repracticeIndex, setRepracticeIndex] = useState(0);
  const [repracticeAnswer, setRepracticeAnswer] = useState("");
  const [repracticeFeedback, setRepracticeFeedback] = useState<PracticeAnswer | null>(null);

  // FSRS 复习
  const [dueCards, setDueCards] = useState<ReviewCard[] | null>(null);

  // 模考
  const [exam, setExam] = useState<ExamCreate | null>(null);
  const [examAnswers, setExamAnswers] = useState<Record<string, string>>({});
  const [examReport, setExamReport] = useState<ExamReport | null>(null);

  const loadMistakes = useCallback(async () => {
    try {
      setMistakes(await api.mistakes({ limit: 20 }));
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "加载错题本失败。");
    }
  }, []);

  const loadDue = useCallback(async () => {
    try {
      const data = await api.reviewDue(5);
      setDueCards(data.cards);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "加载复习卡片失败。");
    }
  }, []);

  useEffect(() => {
    void loadMistakes();
    void loadDue();
  }, [loadMistakes, loadDue]);

  async function handleGenerate() {
    setBusy(true);
    setError(null);
    setFeedback(null);
    try {
      const result = await api.generatePractice({ subject, count: Number(count) });
      setPractice(result);
      setActiveQuestion(result.questions[0] ?? null);
      setAnswer("");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "生成练习失败，请重试。");
    } finally {
      setBusy(false);
    }
  }

  async function handlePracticeAnswer() {
    if (!activeQuestion || !answer.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const result = await api.answerPractice({
        question_id: activeQuestion.id,
        answer: answer.trim(),
        source: "practice",
      });
      setFeedback(result);
      if (result.mistake_collected) void loadMistakes();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "提交失败，请重试。");
    } finally {
      setBusy(false);
    }
  }

  function nextPracticeQuestion() {
    if (!practice) return;
    const index = practice.questions.findIndex((item) => item.id === activeQuestion?.id);
    const next = practice.questions[index + 1] ?? null;
    setActiveQuestion(next);
    setAnswer("");
    setFeedback(null);
  }

  async function handleRepractice() {
    setBusy(true);
    setError(null);
    try {
      const result = await api.repractice({ count: 5 });
      setRepracticeQuestions(result.questions);
      setRepracticeIndex(0);
      setRepracticeAnswer("");
      setRepracticeFeedback(null);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "生成重练题失败。");
    } finally {
      setBusy(false);
    }
  }

  async function handleRepracticeAnswer() {
    const question = repracticeQuestions[repracticeIndex];
    if (!question || !repracticeAnswer.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const result = await api.answerPractice({
        question_id: question.id,
        answer: repracticeAnswer.trim(),
        source: "repractice",
      });
      setRepracticeFeedback(result);
      if (result.mistake_removed) void loadMistakes();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "重练提交失败。");
    } finally {
      setBusy(false);
    }
  }

  async function handleCreateExam() {
    setBusy(true);
    setError(null);
    try {
      const result = await api.createExam({ subject, count: 5, time_limit_minutes: 20 });
      setExam(result);
      setExamAnswers({});
      setExamReport(null);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "创建模考失败。");
    } finally {
      setBusy(false);
    }
  }

  async function handleSubmitExam() {
    if (!exam) return;
    setBusy(true);
    setError(null);
    try {
      const result = await api.submitExam(
        exam.exam_id,
        Object.entries(examAnswers).map(([question_id, value]) => ({ question_id, answer: value })),
      );
      setExamReport(result);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "交卷失败。");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <SectionTitle hint="薄弱知识点优先（≥60%），7 天自动去重；答错自动进入错题本。">智能练习</SectionTitle>

      {error ? <ErrorBlock message={error} onRetry={() => setError(null)} /> : null}

      <Card>
        <CardHeader>
          <CardTitle>出题与作答</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-end gap-3">
            <div className="space-y-2">
              <Label htmlFor="practice-subject">学科</Label>
              <Select
                id="practice-subject"
                options={[
                  { value: "math", label: "数学" },
                  { value: "english", label: "英语" },
                ]}
                value={subject}
                onChange={(event) => setSubject(event.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="practice-count">题量</Label>
              <Select
                id="practice-count"
                options={[
                  { value: "3", label: "3 题" },
                  { value: "5", label: "5 题" },
                  { value: "10", label: "10 题" },
                ]}
                value={count}
                onChange={(event) => setCount(event.target.value)}
              />
            </div>
            <Button onClick={() => void handleGenerate()} disabled={busy} data-testid="generate-practice">
              {busy ? "出题中…" : "生成练习"}
            </Button>
          </div>

          {practice ? (
            <p className="text-sm text-muted-foreground" data-testid="practice-summary">
              共 {practice.count} 题 · 薄弱知识点 {practice.weak_count} 题（占比{" "}
              {Math.round(practice.weak_ratio * 100)}%）
            </p>
          ) : null}

          {activeQuestion ? (
            <div className="space-y-4 rounded-lg border border-border p-4" data-testid="practice-question">
              <p className="text-base leading-7">{activeQuestion.stem}</p>
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Badge variant="outline">难度 {activeQuestion.difficulty}</Badge>
                <span>出题原因：{activeQuestion.reason}</span>
              </div>
              <QuestionOptions
                prefix="practice"
                options={activeQuestion.options}
                value={answer}
                onChange={setAnswer}
              />
              {feedback ? (
                <div className="space-y-2" data-testid="practice-feedback">
                  <Alert variant={feedback.is_correct ? "success" : "danger"}>
                    {feedback.is_correct
                      ? "回答正确"
                      : `回答错误，正确答案：${feedback.correct_answer}${
                          feedback.mistake_collected ? "（已加入错题本）" : ""
                        }`}
                  </Alert>
                  {feedback.explanation ? (
                    <p className="text-sm text-muted-foreground">{feedback.explanation}</p>
                  ) : null}
                  <Button variant="outline" onClick={nextPracticeQuestion} disabled={busy}>
                    下一题
                  </Button>
                </div>
              ) : (
                <Button onClick={() => void handlePracticeAnswer()} disabled={busy || !answer.trim()}>
                  提交答案
                </Button>
              )}
            </div>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <CardTitle>错题本</CardTitle>
            <Button variant="outline" size="sm" disabled={busy} onClick={() => void handleRepractice()}>
              错题重练
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-3">
            <StatCard title="待掌握" value={mistakes?.active_count ?? 0} tone="danger" />
            <StatCard title="已掌握" value={mistakes?.mastered_count ?? 0} tone="success" />
            <StatCard
              title="错因分布"
              value={mistakes?.summary.length ?? 0}
              hint={mistakes?.summary.map((item) => `${item.reason_label} ${item.count}`).join(" · ")}
            />
          </div>

          {mistakes && mistakes.entries.length > 0 ? (
            <div className="space-y-2">
              {mistakes.entries.map((entry) => (
                <div
                  key={entry.id}
                  className="rounded-lg border border-border px-4 py-3 text-sm"
                  data-testid="mistake-entry"
                >
                  <p>{entry.question.stem}</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    状态：{entry.state === "active" ? "待掌握" : "已掌握"} · 错因：
                    {entry.error_reason_label ?? "未归因"} · 重练 {entry.review_count} 次
                  </p>
                </div>
              ))}
            </div>
          ) : (
            <EmptyBlock title="错题本为空" hint="答错的题会自动收录，并可按错因分组重练。" />
          )}

          {repracticeQuestions.length > 0 && repracticeQuestions[repracticeIndex] ? (
            <div className="space-y-3 rounded-lg border border-dashed border-primary/40 p-4" data-testid="repractice-panel">
              <p className="text-sm font-medium">
                重练 {repracticeIndex + 1} / {repracticeQuestions.length}
              </p>
              <p className="text-base leading-7">{repracticeQuestions[repracticeIndex].stem}</p>
              <QuestionOptions
                prefix="repractice"
                options={repracticeQuestions[repracticeIndex].options}
                value={repracticeAnswer}
                onChange={setRepracticeAnswer}
              />
              {repracticeFeedback ? (
                <Alert variant={repracticeFeedback.is_correct ? "success" : "warning"}>
                  {repracticeFeedback.is_correct
                    ? `回答正确${repracticeFeedback.mistake_removed ? "，已移出错题本" : ""}`
                    : `回答错误，正确答案：${repracticeFeedback.correct_answer}`}
                </Alert>
              ) : null}
              <div className="flex gap-2">
                <Button
                  size="sm"
                  disabled={busy || !repracticeAnswer.trim()}
                  onClick={() => void handleRepracticeAnswer()}
                >
                  提交重练
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={busy}
                  onClick={() => {
                    setRepracticeIndex((index) => index + 1);
                    setRepracticeAnswer("");
                    setRepracticeFeedback(null);
                  }}
                >
                  下一题
                </Button>
              </div>
            </div>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>今日复习（FSRS）</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {dueCards === null ? (
            <LoadingBlock rows={2} label="加载复习卡片" />
          ) : dueCards.length === 0 ? (
            <EmptyBlock title="今天没有到期卡片" hint="完成练习后，系统会按记忆曲线安排复习。" />
          ) : (
            dueCards.map((card) => (
              <div key={card.card_id} className="space-y-2 rounded-lg border border-border p-4 text-sm">
                <p>{card.question.stem}</p>
                <div className="flex flex-wrap gap-2">
                  {[1, 2, 3, 4].map((grade) => (
                    <Button
                      key={grade}
                      size="sm"
                      variant="outline"
                      data-testid={`review-grade-${grade}`}
                      disabled={busy}
                      onClick={async () => {
                        setBusy(true);
                        try {
                          await api.reviewGrade(card.card_id, grade);
                          setDueCards((cards) => cards?.filter((item) => item.card_id !== card.card_id) ?? []);
                        } catch (caught) {
                          setError(caught instanceof ApiError ? caught.message : "评分失败。");
                        } finally {
                          setBusy(false);
                        }
                      }}
                    >
                      评分 {grade}
                    </Button>
                  ))}
                </div>
              </div>
            ))
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <CardTitle>限时模考（F-20）</CardTitle>
            <Button variant="outline" size="sm" disabled={busy} onClick={() => void handleCreateExam()}>
              开始一次模考
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {exam ? (
            <>
              <p className="text-sm text-muted-foreground">
                {exam.title} · {exam.questions.length} 题 · {exam.time_limit_minutes} 分钟
              </p>
              {exam.questions.map((question, index) => (
                <div key={question.id} className="space-y-2 rounded-lg border border-border p-4">
                  <p className="text-sm">
                    {index + 1}. {question.stem}
                  </p>
                  <QuestionOptions
                    prefix="exam"
                    options={question.options}
                    value={examAnswers[question.id] ?? ""}
                    onChange={(value) =>
                      setExamAnswers((answers) => ({ ...answers, [question.id]: value }))
                    }
                  />
                </div>
              ))}
              <Button disabled={busy || Object.keys(examAnswers).length < exam.questions.length} onClick={() => void handleSubmitExam()}>
                交卷
              </Button>
            </>
          ) : (
            <p className="text-sm text-muted-foreground">
              模考为限时闭卷测评；考试期间服务端会强制关闭讲解提示。
            </p>
          )}
          {examReport ? (
            <div className="space-y-2 rounded-lg border border-border p-4 text-sm" data-testid="exam-report">
              <p className="font-semibold">本次模考得分：{String(examReport.summary.score ?? "—")}</p>
              <p className="text-muted-foreground">共 {examReport.diagnoses.length} 道题有诊断记录</p>
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
