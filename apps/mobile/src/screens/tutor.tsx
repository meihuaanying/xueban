/** 讲解 Tab（T6.3）：提示分层 + SSE 流式输出 + 公式渲染。 */

import { useState } from "react";
import { Text, View } from "react-native";

import { Badge, Card, ErrorBlock, PrimaryButton, Screen } from "../components/ui";
import { MathText } from "../components/math-text";
import {
  ApiError,
  api,
  streamTutorHint,
  type PracticeQuestion,
  type TutorSession,
} from "../lib/api";

interface HintMessage {
  level: number;
  levelName: string;
  content: string;
  streaming: boolean;
}

export function TutorScreen() {
  const [question, setQuestion] = useState<PracticeQuestion | null>(null);
  const [session, setSession] = useState<TutorSession | null>(null);
  const [messages, setMessages] = useState<HintMessage[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [streaming, setStreaming] = useState(false);

  async function pick() {
    setBusy(true);
    setError(null);
    try {
      const result = await api.generatePractice({ subject: "math", count: 1 });
      const first = result.questions[0] ?? null;
      setQuestion(first);
      setSession(null);
      setMessages([]);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "获取题目失败。");
    } finally {
      setBusy(false);
    }
  }

  async function start() {
    if (!question) return;
    setBusy(true);
    setError(null);
    try {
      setSession(await api.createTutorSession(question.id));
      setMessages([]);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "创建讲解会话失败。");
    } finally {
      setBusy(false);
    }
  }

  async function requestHint(level: number) {
    if (!session) return;
    setStreaming(true);
    setError(null);
    setMessages((prev) => [...prev, { level, levelName: "", content: "", streaming: true }]);
    const append = (update: (message: HintMessage) => HintMessage) =>
      setMessages((prev) => prev.map((message, index) => (index === prev.length - 1 ? update(message) : message)));
    try {
      await streamTutorHint(session.session_id, level, {
        onStart: (payload) => append((message) => ({ ...message, level: payload.level, levelName: payload.level_name })),
        onDelta: (content) => append((message) => ({ ...message, content: message.content + content })),
        onDone: (payload) => {
          append((message) => ({ ...message, content: payload.content, streaming: false }));
          setSession((current) => (current ? { ...current, hint_level: payload.level } : current));
        },
      });
    } catch (caught) {
      // 流式不可用时回退到非流式接口，保证功能可用
      try {
        const hint = await api.tutorHint(session.session_id, level);
        append(() => ({ level: hint.level, levelName: hint.level_name, content: hint.content, streaming: false }));
        setSession((current) => (current ? { ...current, hint_level: hint.level } : current));
      } catch (fallbackError) {
        setMessages((prev) => prev.filter((message) => !message.streaming));
        setError(
          fallbackError instanceof ApiError
            ? fallbackError.message
            : caught instanceof ApiError
              ? caught.message
              : "讲解获取失败。",
        );
      }
    } finally {
      setStreaming(false);
    }
  }

  const nextLevel = session ? Math.min(session.hint_level + 1, 3) : 1;

  return (
    <Screen title="讲解" hint="守护型讲解：逐层解锁，不直接给答案。">
      {error ? <ErrorBlock message={error} onRetry={() => setError(null)} /> : null}

      <Card testID="tutor-question">
        {question ? (
          <>
            <Text className="text-base text-foreground" testID="tutor-stem">
              {question.stem}
            </Text>
            <View className="mt-2">
              <Badge label={`难度 ${question.difficulty}`} />
            </View>
            {!session ? (
              <View className="mt-3">
                <PrimaryButton label="开始守护型讲解" disabled={busy} onPress={() => void start()} testID="start-tutor" />
              </View>
            ) : null}
          </>
        ) : (
          <Text className="text-sm text-muted">点击下方按钮获取一道题，开始讲解会话。</Text>
        )}
        <View className="mt-3">
          <PrimaryButton
            label={question ? "换一题" : "获取一道题"}
            variant="outline"
            disabled={busy}
            onPress={() => void pick()}
            testID="pick-question"
          />
        </View>
      </Card>

      {session ? (
        <Card testID="tutor-hints">
          <Text className="font-semibold text-foreground">
            当前层级：{session.hint_level === 0 ? "未开始" : `${session.hint_level} / 3`}
          </Text>
          <View className="mt-3 gap-2">
            {[
              { level: 1, label: "第一层：思路提示" },
              { level: 2, label: "第二层：关键步骤" },
              { level: 3, label: "第三层：完整解答" },
            ].map((item) => {
              const reached = session.hint_level >= item.level;
              const isNext = !reached && item.level === nextLevel;
              return (
                <PrimaryButton
                  key={item.level}
                  testID={`hint-${item.level}`}
                  label={reached ? `已解锁 · ${item.label}` : item.label}
                  variant={isNext ? "primary" : "outline"}
                  disabled={!isNext || streaming}
                  onPress={() => void requestHint(item.level)}
                />
              );
            })}
          </View>
          <View className="mt-4 gap-3">
            {messages.map((message, index) => (
              <View key={index} className="rounded-xl bg-secondary p-3">
                <View className="mb-1 flex-row items-center gap-2">
                  <Badge label={message.levelName || `第 ${message.level} 层`} />
                  {message.streaming ? <Text className="text-xs text-muted">输出中…</Text> : null}
                </View>
                <MathText content={message.content} />
              </View>
            ))}
          </View>
        </Card>
      ) : null}
    </Screen>
  );
}
