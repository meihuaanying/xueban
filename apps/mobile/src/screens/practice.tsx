/** 练习 Tab（T6.4）：出题作答、错题本与重练。 */

import { useCallback, useEffect, useState } from "react";
import { Text, View } from "react-native";

import { Badge, Card, EmptyBlock, ErrorBlock, PrimaryButton, Screen } from "../components/ui";
import { enqueueAnswer, flushOnReconnect, newEventId } from "../lib/offline-queue";
import {
  ApiError,
  api,
  type MistakeEntry,
  type PracticeAnswer,
  type PracticeQuestion,
} from "../lib/api";

export function PracticeScreen() {
  const [questions, setQuestions] = useState<PracticeQuestion[]>([]);
  const [index, setIndex] = useState(0);
  const [answer, setAnswer] = useState("");
  const [feedback, setFeedback] = useState<PracticeAnswer | null>(null);
  const [mistakes, setMistakes] = useState<MistakeEntry[]>([]);
  const [repractice, setRepractice] = useState<{ id: string; stem: string; options: Record<string, string> | null }[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const loadMistakes = useCallback(async () => {
    try {
      const data = await api.mistakes();
      setMistakes(data.entries);
    } catch {
      // 错题本加载失败不阻塞练习
    }
  }, []);

  useEffect(() => {
    void loadMistakes();
    // 启动时尝试补齐离线作答
    void flushOnReconnect();
  }, [loadMistakes]);

  const current = questions[index] ?? null;

  async function generate() {
    setBusy(true);
    setError(null);
    setFeedback(null);
    try {
      const result = await api.generatePractice({ subject: "math", count: 5 });
      setQuestions(result.questions);
      setIndex(0);
      setAnswer("");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "生成练习失败。");
    } finally {
      setBusy(false);
    }
  }

  async function submit() {
    if (!current || !answer.trim()) return;
    setBusy(true);
    setError(null);
    const eventId = newEventId();
    try {
      const result = await api.answerPractice({
        question_id: current.id,
        answer: answer.trim(),
        source: "practice",
        client_event_id: eventId,
      });
      setFeedback(result);
      if (result.mistake_collected) void loadMistakes();
    } catch (caught) {
      if (caught instanceof ApiError) {
        setError(caught.message);
      } else {
        // 网络异常：离线保存，联网后自动补齐（幂等）
        await enqueueAnswer({
          client_event_id: eventId,
          question_id: current.id,
          answer: answer.trim(),
          source: "practice",
        });
        setError("当前网络不可用：已离线保存作答，联网后自动提交（不重复计数）。");
      }
    } finally {
      setBusy(false);
    }
  }

  async function startRepractice() {
    setBusy(true);
    setError(null);
    try {
      const result = await api.repractice();
      setRepractice(result.questions);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "生成重练题失败。");
    } finally {
      setBusy(false);
    }
  }

  async function answerRepractice(questionId: string, value: string) {
    setBusy(true);
    setError(null);
    try {
      const result = await api.answerPractice({ question_id: questionId, answer: value, source: "repractice" });
      setError(
        result.mistake_removed
          ? null
          : result.is_correct
            ? null
            : `回答错误，正确答案：${result.correct_answer}`,
      );
      if (result.mistake_removed) {
        setRepractice((prev) => prev.filter((item) => item.id !== questionId));
        void loadMistakes();
      }
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "重练提交失败。");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Screen title="练习" hint="薄弱知识点优先；答错自动进入错题本。">
      {error ? <ErrorBlock message={error} onRetry={() => setError(null)} /> : null}

      <PrimaryButton label={busy ? "出题中…" : "生成 5 道练习"} disabled={busy} onPress={() => void generate()} testID="generate-practice" />

      {current ? (
        <Card testID="practice-question">
          <Text className="text-sm text-muted">
            {index + 1} / {questions.length} · 难度 {current.difficulty}
          </Text>
          <Text className="mt-2 text-base text-foreground">{current.stem}</Text>
          <View className="mt-3 gap-2">
            {current.options
              ? Object.entries(current.options).map(([key, label]) => (
                  <PrimaryButton
                    key={key}
                    testID={`option-${key}`}
                    label={`${key}. ${label}`}
                    variant={answer === key ? "primary" : "outline"}
                    onPress={() => setAnswer(key)}
                  />
                ))
              : null}
          </View>
          {feedback ? (
            <View className="mt-3 gap-2" testID="practice-feedback">
              <Badge
                label={feedback.is_correct ? "回答正确" : "回答错误"}
                tone={feedback.is_correct ? "success" : "danger"}
              />
              {!feedback.is_correct ? (
                <Text className="text-sm text-danger">
                  正确答案：{feedback.correct_answer}
                  {feedback.mistake_collected ? "（已加入错题本）" : ""}
                </Text>
              ) : null}
              {feedback.explanation ? <Text className="text-sm text-muted">{feedback.explanation}</Text> : null}
              <PrimaryButton
                label="下一题"
                variant="outline"
                onPress={() => {
                  setIndex((value) => value + 1);
                  setAnswer("");
                  setFeedback(null);
                }}
              />
            </View>
          ) : (
            <View className="mt-3">
              <PrimaryButton
                label="提交答案"
                disabled={busy || !answer.trim()}
                onPress={() => void submit()}
                testID="submit-practice"
              />
            </View>
          )}
        </Card>
      ) : null}

      <Card testID="mistake-list">
        <View className="flex-row items-center justify-between">
          <Text className="font-semibold text-foreground">错题本（{mistakes.length}）</Text>
          <PrimaryButton label="错题重练" variant="outline" disabled={busy} onPress={() => void startRepractice()} />
        </View>
        <View className="mt-2 gap-2">
          {mistakes.slice(0, 5).map((entry) => (
            <View key={entry.id} className="rounded-xl border border-border p-3">
              <Text className="text-sm text-foreground">{entry.question.stem}</Text>
              <Text className="mt-1 text-xs text-muted">
                错因：{entry.error_reason_label ?? "未归因"} · 重练 {entry.review_count} 次
              </Text>
            </View>
          ))}
          {mistakes.length === 0 ? <EmptyBlock title="错题本为空" hint="答错的题会自动收录。" /> : null}
        </View>

        {repractice.length > 0 ? (
          <View className="mt-4 gap-3" testID="repractice-panel">
            {repractice.map((question) => (
              <View key={question.id} className="rounded-xl bg-secondary p-3">
                <Text className="text-sm text-foreground">{question.stem}</Text>
                {question.options ? (
                  <View className="mt-2 gap-2">
                    {Object.entries(question.options).map(([key]) => (
                      <PrimaryButton
                        key={key}
                        testID={`repractice-${key}`}
                        label={key}
                        variant="outline"
                        disabled={busy}
                        onPress={() => void answerRepractice(question.id, key)}
                      />
                    ))}
                  </View>
                ) : (
                  <View className="mt-2">
                    <PrimaryButton
                      label="提交答案"
                      variant="outline"
                      disabled={busy}
                      onPress={() => void answerRepractice(question.id, "1")}
                    />
                  </View>
                )}
              </View>
            ))}
          </View>
        ) : null}
      </Card>
    </Screen>
  );
}
