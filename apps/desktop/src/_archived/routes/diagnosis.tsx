/** 诊断与画像（T5.2 / F-01、F-02、F-03）：CAT 作答 → 报告雷达图。 */

import { useCallback, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Input,
  KnowledgeRadar,
  Label,
  Select,
  StatCard,
} from "@xueban/ui";

import { EmptyBlock, ErrorBlock, LoadingBlock, SectionTitle } from "@/components/state";
import { ApiError, api, type DiagnosisAnswer, type DiagnosisQuestion, type DiagnosisReport } from "@/lib/api";

const SUBJECTS = [
  { value: "math", label: "数学" },
  { value: "english", label: "英语" },
];

const STAGES = [
  { value: "primary", label: "小学" },
  { value: "junior", label: "初中" },
  { value: "senior", label: "高中" },
  { value: "postgraduate", label: "考研" },
];

type Phase = "idle" | "running" | "report";

export default function DiagnosisPage() {
  const [phase, setPhase] = useState<Phase>("idle");
  const [subject, setSubject] = useState("math");
  const [stage, setStage] = useState("junior");
  const [count, setCount] = useState("20");
  const [examId, setExamId] = useState<string | null>(null);
  const [progress, setProgress] = useState<{ answered: number; total: number } | null>(null);
  const [question, setQuestion] = useState<DiagnosisQuestion | null>(null);
  const [answer, setAnswer] = useState("");
  const [feedback, setFeedback] = useState<DiagnosisAnswer | null>(null);
  const [report, setReport] = useState<DiagnosisReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();

  const loadReport = useCallback(async (id: string) => {
    const data = await api.diagnosisReport(id);
    setReport(data);
  }, []);

  async function handleStart() {
    setBusy(true);
    setError(null);
    try {
      const started = await api.startDiagnosis({
        subject,
        stage,
        target_count: Number(count),
      });
      setExamId(started.exam_id);
      setProgress(started.progress);
      setQuestion(started.question);
      setFeedback(null);
      setAnswer("");
      setReport(null);
      setPhase("running");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "无法连接服务器，请稍后重试。");
    } finally {
      setBusy(false);
    }
  }

  async function handleAnswer() {
    if (!examId || !question) return;
    if (!answer.trim()) {
      setError("请先作答再提交。");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await api.answerDiagnosis(examId, {
        question_id: question.id,
        answer: answer.trim(),
      });
      setFeedback(result);
      setProgress(result.progress);
      if (result.finished) {
        await loadReport(examId);
        setPhase("report");
      } else {
        setQuestion(result.next_question);
        setAnswer("");
      }
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "提交失败，请稍后重试。");
    } finally {
      setBusy(false);
    }
  }

  async function handleNext() {
    if (!question) return;
    setFeedback(null);
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <SectionTitle hint="自适应诊断（答对加难 / 答错降难），完成后生成学情画像雷达图。">
        学情诊断
      </SectionTitle>

      {error ? <ErrorBlock message={error} onRetry={() => setError(null)} /> : null}

      {phase === "idle" ? (
        <Card data-testid="onboarding-card">
          <CardHeader>
            <CardTitle>新手引导：三步开始学习</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <p className="text-muted-foreground">
              1. 完成一次诊断画像 → 2. 领取今日任务卡 → 3. 开始第一次守护型讲解（≤5 步到达）。
            </p>
            <Button
              variant="outline"
              data-testid="quickstart-tutor"
              onClick={() => navigate("/tutor?quickstart=1")}
            >
              跳过诊断，先体验一次讲解
            </Button>
          </CardContent>
        </Card>
      ) : null}

      {phase === "idle" ? (
        <Card>
          <CardHeader>
            <CardTitle>开始一次新诊断</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-3">
              <div className="space-y-2">
                <Label htmlFor="subject">学科</Label>
                <Select
                  id="subject"
                  options={SUBJECTS}
                  value={subject}
                  onChange={(event) => setSubject(event.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="stage">学段</Label>
                <Select
                  id="stage"
                  options={STAGES}
                  value={stage}
                  onChange={(event) => setStage(event.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="count">题量</Label>
                <Select
                  id="count"
                  options={[
                    { value: "20", label: "20 题" },
                    { value: "25", label: "25 题" },
                    { value: "30", label: "30 题" },
                  ]}
                  value={count}
                  onChange={(event) => setCount(event.target.value)}
                />
              </div>
            </div>
            <Button size="lg" onClick={() => void handleStart()} disabled={busy}>
              {busy ? "正在出题…" : "开始诊断"}
            </Button>
          </CardContent>
        </Card>
      ) : null}

      {phase === "running" && question ? (
        <Card>
          <CardHeader>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <CardTitle>
                第 {progress ? progress.answered + 1 : 1} 题
                {progress ? ` / ${progress.total}` : ""}
              </CardTitle>
              <div className="flex items-center gap-2">
                <Badge variant="outline">难度 {question.difficulty}</Badge>
                {question.knowledge_points.map((point) => (
                  <Badge key={point} variant="default">
                    {point}
                  </Badge>
                ))}
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-base leading-7" data-testid="diagnosis-stem">
              {question.stem}
            </p>
            {question.options ? (
              <div className="grid gap-2 sm:grid-cols-2">
                {Object.entries(question.options).map(([key, label]) => (
                  <Button
                    key={key}
                    variant={answer === key ? "primary" : "outline"}
                    onClick={() => setAnswer(key)}
                    className="justify-start"
                    data-testid={`diagnosis-option-${key}`}
                  >
                    {key}. {label}
                  </Button>
                ))}
              </div>
            ) : (
              <div className="space-y-2">
                <Label htmlFor="answer">你的答案</Label>
                <Input
                  id="answer"
                  value={answer}
                  onChange={(event) => setAnswer(event.target.value)}
                  placeholder="请输入答案"
                />
              </div>
            )}

            {feedback ? (
              <div className="space-y-3" data-testid="diagnosis-feedback">
                <p className={feedback.is_correct ? "text-sm text-success" : "text-sm text-destructive"}>
                  {feedback.is_correct ? "回答正确" : "回答错误"} · 正确答案：{feedback.correct_answer}
                </p>
                <Button onClick={handleNext} disabled={busy}>
                  下一题
                </Button>
              </div>
            ) : (
              <Button onClick={() => void handleAnswer()} disabled={busy || !answer.trim()}>
                {busy ? "提交中…" : "提交答案"}
              </Button>
            )}
          </CardContent>
        </Card>
      ) : null}

      {phase === "report" ? (
        report?.has_data ? (
          <div className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-3">
              <StatCard
                title="红区知识点"
                value={String(report.points.filter((point) => point.level === "red").length)}
                hint="掌握度 < 60%"
                tone="danger"
              />
              <StatCard
                title="黄区知识点"
                value={String(report.points.filter((point) => point.level === "yellow").length)}
                hint="60% ~ 80%"
                tone="warning"
              />
              <StatCard
                title="绿区知识点"
                value={String(report.points.filter((point) => point.level === "green").length)}
                hint="≥ 80%"
                tone="success"
              />
            </div>
            <KnowledgeRadar
              title="本次诊断掌握度雷达（与 API report.points 一致）"
              data-testid="diagnosis-radar"
              data={report.points.slice(0, 8).map((point) => ({
                label: point.name,
                value: Math.round(point.mastery * 100),
              }))}
            />
            <Card>
              <CardHeader>
                <CardTitle>知识点明细</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                {report.points.map((point) => (
                  <div
                    key={point.knowledge_point_id}
                    className="flex items-center justify-between gap-3 border-b border-border py-2 last:border-0"
                    data-testid="mastery-row"
                  >
                    <span>{point.name}</span>
                    <span className="text-muted-foreground">
                      {Math.round(point.mastery * 100)}% · {point.level}
                    </span>
                  </div>
                ))}
              </CardContent>
            </Card>
            <div className="flex gap-3">
              <Button
                variant="outline"
                onClick={() => {
                  setPhase("idle");
                  setReport(null);
                  setExamId(null);
                }}
              >
                再测一次
              </Button>
              <Link to="/plan">
                <Button>去规划页生成学习路径</Button>
              </Link>
            </div>
          </div>
        ) : (
          <EmptyBlock
            title="诊断数据不足"
            hint="本次诊断没有产生有效掌握度数据，请重新测一次。"
            action={
              <Button
                onClick={() => {
                  setPhase("idle");
                  setReport(null);
                }}
              >
                返回重新开始
              </Button>
            }
          />
        )
      ) : null}

      {busy && phase === "idle" ? <LoadingBlock rows={2} label="正在获取题目" /> : null}
    </div>
  );
}
