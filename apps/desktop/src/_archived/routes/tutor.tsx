/** 讲解页（T5.4 / F-11~F-15）：分层提示、SSE 流式渲染、多解法/类比/变式。 */

import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  Alert,
  Badge,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Input,
  Separator,
  Spinner,
} from "@xueban/ui";

import { MathText } from "@/components/math-text";
import { ErrorBlock, SectionTitle } from "@/components/state";
import {
  ApiError,
  api,
  streamTutorHint,
  type AltSolution,
  type AnalogyResult,
  type PracticeQuestion,
  type TutorSession,
  type Variant,
  type VariantAnswerResponse,
} from "@/lib/api";

interface HintMessage {
  level: number;
  levelName: string;
  content: string;
  streaming: boolean;
}

const LEVEL_BUTTONS: { level: number; label: string }[] = [
  { level: 1, label: "第一层：思路提示" },
  { level: 2, label: "第二层：关键步骤" },
  { level: 3, label: "第三层：完整解答" },
];

export default function TutorPage() {
  const [question, setQuestion] = useState<PracticeQuestion | null>(null);
  const [session, setSession] = useState<TutorSession | null>(null);
  const [messages, setMessages] = useState<HintMessage[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [analogy, setAnalogy] = useState<AnalogyResult | null>(null);
  const [solutions, setSolutions] = useState<AltSolution[] | null>(null);
  const [variants, setVariants] = useState<Variant[] | null>(null);
  const [variantAnswer, setVariantAnswer] = useState("");
  const [variantFeedback, setVariantFeedback] = useState<VariantAnswerResponse | null>(null);

  const [searchParams] = useSearchParams();
  const quickstart = searchParams.get("quickstart") === "1";

  const pickQuestion = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const result = await api.generatePractice({ subject: "math", count: 1 });
      const first = result.questions[0] ?? null;
      setQuestion(first);
      setSession(null);
      setMessages([]);
      setAnalogy(null);
      setSolutions(null);
      setVariants(null);
      setVariantFeedback(null);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "获取题目失败，请重试。");
    } finally {
      setBusy(false);
    }
  }, []);

  async function startSession() {
    if (!question) return;
    setBusy(true);
    setError(null);
    try {
      const created = await api.createTutorSession(question.id);
      setSession(created);
      setMessages([]);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "创建讲解会话失败，请重试。");
    } finally {
      setBusy(false);
    }
  }

  async function requestHint(level: number) {
    if (!session) return;
    setStreaming(true);
    setError(null);
    setMessages((prev) => [...prev, { level, levelName: "", content: "", streaming: true }]);
    try {
      await streamTutorHint(session.session_id, level, {
        onStart: (payload) => {
          setMessages((prev) =>
            prev.map((message, index) =>
              index === prev.length - 1
                ? { ...message, level: payload.level, levelName: payload.level_name }
                : message,
            ),
          );
        },
        onDelta: (content) => {
          setMessages((prev) =>
            prev.map((message, index) =>
              index === prev.length - 1
                ? { ...message, content: message.content + content }
                : message,
            ),
          );
        },
        onDone: (payload) => {
          setMessages((prev) =>
            prev.map((message, index) =>
              index === prev.length - 1
                ? { ...message, content: payload.content, streaming: false }
                : message,
            ),
          );
          setSession((current) => (current ? { ...current, hint_level: payload.level } : current));
        },
      });
    } catch (caught) {
      setMessages((prev) => prev.filter((message) => !message.streaming));
      setError(caught instanceof ApiError ? caught.message : "流式讲解中断，请重试。");
    } finally {
      setStreaming(false);
    }
  }

  async function handleAnalogy() {
    if (!session) return;
    setBusy(true);
    try {
      setAnalogy(await api.tutorAnalogy(session.session_id));
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "类比生成失败。");
    } finally {
      setBusy(false);
    }
  }

  async function handleSolutions() {
    if (!session) return;
    setBusy(true);
    try {
      const result = await api.tutorAltSolutions(session.session_id);
      setSolutions(result.solutions);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "多解法生成失败。");
    } finally {
      setBusy(false);
    }
  }

  async function handleVariants() {
    if (!session) return;
    setBusy(true);
    try {
      const result = await api.tutorVariants(session.session_id);
      setVariants(result.variants);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "变式题生成失败。");
    } finally {
      setBusy(false);
    }
  }

  async function submitVariant(variantId: string) {
    if (!variantAnswer.trim() || !session) return;
    setBusy(true);
    try {
      const response = await api.answerVariant(session.session_id, variantId, variantAnswer.trim());
      setVariantFeedback(response);
      setVariantAnswer("");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "变式题提交失败。");
    } finally {
      setBusy(false);
    }
  }

  // 新手引导：带 quickstart=1 进入时自动获取题目并开始第一次讲解
  useEffect(() => {
    if (!quickstart || question || busy) return;
    let cancelled = false;
    (async () => {
      setBusy(true);
      try {
        const result = await api.generatePractice({ subject: "math", count: 1 });
        const first = result.questions[0] ?? null;
        if (cancelled || !first) return;
        setQuestion(first);
        const created = await api.createTutorSession(first.id);
        if (cancelled) return;
        setSession(created);
        setMessages([]);
      } catch {
        // 引导流程失败时保留手动入口
      } finally {
        if (!cancelled) setBusy(false);
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [quickstart]);

  const nextLevel = session ? Math.min(session.hint_level + 1, 3) : 1;

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <SectionTitle hint="守护型讲解：必须逐层解锁（思路 → 关键步骤 → 完整解答），跳层会被服务端拒绝。">
        守护型讲解
      </SectionTitle>

      {error ? <ErrorBlock message={error} onRetry={() => setError(null)} /> : null}

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <CardTitle>讲解题目</CardTitle>
            <Button variant="outline" size="sm" onClick={() => void pickQuestion()} disabled={busy}>
              {question ? "换一题" : "获取一道题"}
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {question ? (
            <>
              <p className="text-base leading-7" data-testid="tutor-stem">
                {question.stem}
              </p>
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="outline">难度 {question.difficulty}</Badge>
                {question.knowledge_points.map((point) => (
                  <Badge key={point}>{point}</Badge>
                ))}
              </div>
              {session ? null : (
                <Button onClick={() => void startSession()} disabled={busy}>
                  开始守护型讲解
                </Button>
              )}
            </>
          ) : (
            <p className="text-sm text-muted-foreground">点击「获取一道题」开始一次讲解会话。</p>
          )}
        </CardContent>
      </Card>

      {session ? (
        <Card>
          <CardHeader>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <CardTitle>分层提示</CardTitle>
              <Badge variant={session.hint_level >= 3 ? "warning" : "default"}>
                当前层级：{session.hint_level === 0 ? "未开始" : `${session.hint_level} / 3`}
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap gap-2">
              {LEVEL_BUTTONS.map((item) => {
                const reached = session.hint_level >= item.level;
                const isNext = !reached && item.level === nextLevel;
                return (
                  <Button
                    key={item.level}
                    variant={isNext ? "primary" : "outline"}
                    size="sm"
                    disabled={!isNext || streaming}
                    onClick={() => void requestHint(item.level)}
                    data-testid={`hint-level-${item.level}`}
                  >
                    {reached ? "已解锁 · " : ""}
                    {item.label}
                  </Button>
                );
              })}
            </div>

            <div className="space-y-3" data-testid="tutor-messages">
              {messages.map((message, index) => (
                <div key={index} className="rounded-xl border border-border bg-muted/40 p-4">
                  <div className="mb-2 flex items-center gap-2">
                    <Badge variant="outline">{message.levelName || `第 ${message.level} 层`}</Badge>
                    {message.streaming ? <Spinner size="sm" /> : null}
                  </div>
                  {message.content ? <MathText content={message.content} /> : null}
                </div>
              ))}
              {messages.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  点击「第一层：思路提示」开始；讲解完成前不会解锁下一层。
                </p>
              ) : null}
            </div>
          </CardContent>
        </Card>
      ) : null}

      {session ? (
        <Card>
          <CardHeader>
            <CardTitle>讲解扩展（F-12~F-14）</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" size="sm" disabled={busy} onClick={() => void handleAnalogy()}>
                打一个类比
              </Button>
              <Button variant="outline" size="sm" disabled={busy} onClick={() => void handleSolutions()}>
                其他解法
              </Button>
              <Button variant="outline" size="sm" disabled={busy} onClick={() => void handleVariants()}>
                生成变式题
              </Button>
            </div>

            {analogy ? (
              <div className="rounded-lg border border-border p-4 text-sm">
                <p className="font-semibold">类比</p>
                <MathText content={analogy.analogy} />
                <p className="mt-2 text-xs text-muted-foreground">
                  映射：{analogy.mapping} · 注意：{analogy.caveat}
                </p>
              </div>
            ) : null}

            {solutions ? (
              <div className="space-y-2">
                {solutions.map((solution) => (
                  <div key={solution.title} className="rounded-lg border border-border p-4 text-sm">
                    <p className="font-semibold">
                      {solution.title}
                      {solution.answer_verified ? (
                        <Badge variant="success" className="ml-2">
                          SymPy 抽检通过
                        </Badge>
                      ) : null}
                    </p>
                    <ol className="mt-2 list-decimal space-y-1 pl-5 text-muted-foreground">
                      {solution.steps.map((step, index) => (
                        <li key={index}>{step}</li>
                      ))}
                    </ol>
                    <p className="mt-2 text-xs text-muted-foreground">适用：{solution.scenario}</p>
                  </div>
                ))}
              </div>
            ) : null}

            {variants ? (
              <div className="space-y-3" data-testid="tutor-variants">
                <Separator />
                {variants.map((variant) => (
                  <div key={variant.question_id} className="rounded-lg border border-border p-4 text-sm">
                    <p>{variant.stem}</p>
                    <div className="mt-2 flex items-center gap-2">
                      <Input
                        aria-label={`变式题答案 ${variant.question_id}`}
                        value={variantAnswer}
                        onChange={(event) => setVariantAnswer(event.target.value)}
                        placeholder="输入答案"
                        className="max-w-xs"
                      />
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={busy}
                        onClick={() => void submitVariant(variant.question_id)}
                      >
                        提交
                      </Button>
                    </div>
                  </div>
                ))}
                {variantFeedback ? (
                  <Alert variant={variantFeedback.is_correct ? "success" : "warning"}>
                    {variantFeedback.is_correct
                      ? "回答正确，掌握得不错。"
                      : `回答错误，正确答案：${variantFeedback.correct_answer}。已安排同类题回炉练习。`}
                  </Alert>
                ) : null}
              </div>
            ) : null}
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
