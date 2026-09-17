/** 陪练（T8.6 / F-32~F-34 移动端形态）：学习陪伴与情景口语。 */

import { useState } from "react";
import { Text, View } from "react-native";

import { Badge, Card, ErrorBlock, PrimaryButton, Screen, TextField } from "../components/ui";
import { ApiError, coachApi, type CoachTurn } from "../lib/api";

interface Message {
  role: "user" | "coach";
  content: string;
  corrections?: CoachTurn["corrections"];
}

export function CoachScreen() {
  const [mode, setMode] = useState<"companion" | "roleplay">("companion");
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [crisis, setCrisis] = useState<{ active: boolean; resources: string[] }>({
    active: false,
    resources: [],
  });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function send() {
    if (!input.trim()) return;
    setBusy(true);
    setError(null);
    const text = input.trim();
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setInput("");
    try {
      const payload = { message: text, session_id: sessionId };
      const result =
        mode === "companion"
          ? await coachApi.companion(payload)
          : await coachApi.roleplay({ ...payload, scene: "campus" });
      setSessionId(result.session_id);
      setMessages((prev) => [
        ...prev,
        { role: "coach", content: result.reply, corrections: result.corrections },
      ]);
      if (result.crisis) setCrisis({ active: true, resources: result.crisis_resources });
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "陪练服务暂时不可用。");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Screen title="陪练" hint="学习陪伴与情景口语；危机表述会优先引导专业求助。">
      {error ? <ErrorBlock message={error} onRetry={() => setError(null)} /> : null}

      <View className="flex-row gap-2">
        {(["companion", "roleplay"] as const).map((key) => (
          <PrimaryButton
            key={key}
            testID={`coach-mode-${key}`}
            label={key === "companion" ? "学习陪伴" : "情景口语"}
            variant={mode === key ? "primary" : "outline"}
            onPress={() => {
              setMode(key);
              setMessages([]);
              setSessionId(null);
              setCrisis({ active: false, resources: [] });
            }}
          />
        ))}
      </View>

      {crisis.active ? (
        <Card testID="coach-crisis">
          <Text className="text-sm font-semibold text-danger">我们很在意你的安全</Text>
          <Text className="mt-1 text-sm text-muted">
            请立即联系家长、老师，或拨打以下 24 小时热线；如有危险请拨打 120/110。
          </Text>
          {crisis.resources.map((item) => (
            <Text key={item} className="mt-1 text-sm text-foreground">
              · {item}
            </Text>
          ))}
        </Card>
      ) : null}

      <View className="gap-2">
        {messages.map((message, index) => (
          <Card key={index} testID={`coach-message-${message.role}`}>
            <View className="mb-1">
              <Badge label={message.role === "user" ? "我" : "教练"} tone={message.role === "user" ? "default" : "success"} />
            </View>
            <Text className="text-sm text-foreground">{message.content}</Text>
            {message.corrections?.map((item) => (
              <Text key={item.original} className="mt-1 text-xs text-muted">
                纠错：{item.original} → {item.suggestion}（{item.note}）
              </Text>
            ))}
          </Card>
        ))}
      </View>

      <TextField
        label={mode === "roleplay" ? "用英语回复" : "说说你的学习状态"}
        testID="coach-input"
        value={input}
        onChangeText={setInput}
      />
      <PrimaryButton
        label={busy ? "发送中…" : "发送"}
        disabled={busy || !input.trim()}
        onPress={() => void send()}
        testID="coach-send"
      />
    </Screen>
  );
}
