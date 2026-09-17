/** 批改页（T5.5 / F-22~F-24）：主观题逐步给分、作文多口径批阅。 */

import { useState } from "react";
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
  Progress,
  Select,
  Tabs,
  Textarea,
} from "@xueban/ui";

import { ErrorBlock, SectionTitle } from "@/components/state";
import { ApiError, api, type EssayGrading, type SubjectiveGrading } from "@/lib/api";

const RUBRICS = [
  { value: "zhongkao", label: "中考作文" },
  { value: "gaokao", label: "高考作文" },
  { value: "cet", label: "四六级作文" },
  { value: "kaoyan", label: "考研作文" },
];

function ScoreRow({ label, score, maxScore }: { label: string; score: number; maxScore: number }) {
  const percent = maxScore > 0 ? Math.round((score / maxScore) * 100) : 0;
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-sm">
        <span>{label}</span>
        <span className="text-muted-foreground">
          {score} / {maxScore}
        </span>
      </div>
      <Progress value={percent} />
    </div>
  );
}

export default function GradingPage() {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [stem, setStem] = useState("");
  const [criteria, setCriteria] = useState("");
  const [studentAnswer, setStudentAnswer] = useState("");
  const [subjective, setSubjective] = useState<SubjectiveGrading | null>(null);

  const [rubric, setRubric] = useState("gaokao");
  const [essayPrompt, setEssayPrompt] = useState("");
  const [essayContent, setEssayContent] = useState("");
  const [essay, setEssay] = useState<EssayGrading | null>(null);

  async function handleSubjective() {
    if (!studentAnswer.trim()) {
      setError("请填写作答内容。");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      setSubjective(
        await api.gradeSubjective({
          stem: stem || undefined,
          criteria: criteria || undefined,
          student_answer: studentAnswer,
        }),
      );
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "批改失败，请重试。");
    } finally {
      setBusy(false);
    }
  }

  async function handleEssay() {
    if (!essayContent.trim()) {
      setError("请填写作文内容。");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      setEssay(
        await api.gradeEssay({
          rubric,
          content: essayContent,
          prompt: essayPrompt || undefined,
        }),
      );
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "作文批阅失败，请重试。");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <SectionTitle hint="主观题逐步给分并标注丢分点；作文按考场口径三维评分。">批改中心</SectionTitle>

      {error ? <ErrorBlock message={error} onRetry={() => setError(null)} /> : null}

      <Tabs
        defaultKey="subjective"
        tabs={[
          {
            key: "subjective",
            label: "主观题批改",
            content: (
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="grading-stem">题目（选填）</Label>
                  <Textarea
                    id="grading-stem"
                    rows={2}
                    value={stem}
                    onChange={(event) => setStem(event.target.value)}
                    placeholder="粘贴题目文本"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="grading-criteria">评分细则（选填）</Label>
                  <Textarea
                    id="grading-criteria"
                    rows={2}
                    value={criteria}
                    onChange={(event) => setCriteria(event.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="grading-answer">学生作答</Label>
                  <Textarea
                    id="grading-answer"
                    rows={5}
                    value={studentAnswer}
                    onChange={(event) => setStudentAnswer(event.target.value)}
                  />
                </div>
                <Button disabled={busy} onClick={() => void handleSubjective()}>
                  {busy ? "批改中…" : "提交批改"}
                </Button>

                {subjective ? (
                  <Card data-testid="subjective-result">
                    <CardHeader>
                      <CardTitle>
                        得分 {subjective.total_score} / {subjective.max_score}
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3 text-sm">
                      {subjective.steps.map((step, index) => (
                        <div key={index} className="rounded-lg border border-border p-3">
                          <p className="font-medium">
                            {step.step} · 得分 {step.score}
                          </p>
                          <p className="mt-1 text-muted-foreground">{step.comment}</p>
                          {step.lost_points ? (
                            <p className="mt-1 text-destructive">丢分点：{step.lost_points}</p>
                          ) : null}
                        </div>
                      ))}
                      <Alert variant="info" title="改写示范">
                        {subjective.rewrite}
                      </Alert>
                      <p className="text-muted-foreground">{subjective.summary}</p>
                    </CardContent>
                  </Card>
                ) : null}
              </div>
            ),
          },
          {
            key: "essay",
            label: "作文批阅",
            content: (
              <div className="space-y-4">
                <div className="flex flex-wrap items-end gap-3">
                  <div className="space-y-2">
                    <Label htmlFor="essay-rubric">评分口径</Label>
                    <Select
                      id="essay-rubric"
                      options={RUBRICS}
                      value={rubric}
                      onChange={(event) => setRubric(event.target.value)}
                    />
                  </div>
                  <div className="min-w-64 flex-1 space-y-2">
                    <Label htmlFor="essay-prompt">题目要求（选填）</Label>
                    <Input
                      id="essay-prompt"
                      value={essayPrompt}
                      onChange={(event) => setEssayPrompt(event.target.value)}
                    />
                  </div>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="essay-content">作文正文</Label>
                  <Textarea
                    id="essay-content"
                    rows={8}
                    value={essayContent}
                    onChange={(event) => setEssayContent(event.target.value)}
                  />
                </div>
                <Button disabled={busy} onClick={() => void handleEssay()}>
                  {busy ? "批阅中…" : "提交作文"}
                </Button>

                {essay ? (
                  <Card data-testid="essay-result">
                    <CardHeader>
                      <CardTitle>
                        总分 {essay.total_score} / {essay.max_score}
                        <Badge className="ml-2" variant="outline">
                          {essay.rubric}
                        </Badge>
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4 text-sm">
                      <ScoreRow label="结构" score={essay.structure.score} maxScore={essay.structure.max_score} />
                      <ScoreRow label="立意" score={essay.ideas.score} maxScore={essay.ideas.max_score} />
                      <ScoreRow label="语言" score={essay.language.score} maxScore={essay.language.max_score} />
                      <div className="space-y-2">
                        {essay.paragraphs.map((paragraph) => (
                          <p key={paragraph.index} className="rounded-lg border border-border p-3">
                            第 {paragraph.index} 段：{paragraph.comment}
                          </p>
                        ))}
                      </div>
                      <Alert variant="info" title="升格范文片段">
                        {essay.upgrade_sample}
                      </Alert>
                      <p className="text-muted-foreground">{essay.summary}</p>
                    </CardContent>
                  </Card>
                ) : null}
              </div>
            ),
          },
        ]}
      />
    </div>
  );
}
