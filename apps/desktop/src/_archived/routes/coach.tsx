/** 陪练页（T8.6 / F-32~F-35）：学习陪伴、情景口语、面试模拟、文书辅助。 */

import { useCallback, useEffect, useState } from "react";
import {
  Alert,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Input,
  Label,
  Select,
  Tabs,
  Textarea,
} from "@xueban/ui";

import { ErrorBlock, SectionTitle } from "@/components/state";
import { ApiError, coachApi, type CoachTurn } from "@/lib/api";

interface Message {
  role: "user" | "coach";
  content: string;
  corrections?: CoachTurn["corrections"];
}

export default function CoachPage() {
  const [tab, setTab] = useState("companion");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // 陪伴 / 情景口语 / 面试 共用消息区
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [crisis, setCrisis] = useState<{ active: boolean; resources: string[] }>({
    active: false,
    resources: [],
  });
  const [scenes, setScenes] = useState<{ key: string; title: string; opening: string }[]>([]);
  const [scene, setScene] = useState("restaurant");

  // 文书
  const [writingText, setWritingText] = useState("");
  const [writingKind, setWritingKind] = useState("resume");
  const [writing, setWriting] = useState<{
    suggestions: string[];
    annotations: { excerpt: string; issue: string; suggestion: string }[];
    integrity_notice: string;
  } | null>(null);

  useEffect(() => {
    coachApi
      .scenes()
      .then(setScenes)
      .catch(() => undefined);
  }, []);

  const resetConversation = useCallback(() => {
    setMessages([]);
    setSessionId(null);
    setCrisis({ active: false, resources: [] });
  }, []);

  async function send(mode: "companion" | "roleplay" | "interview") {
    if (!input.trim()) return;
    setBusy(true);
    setError(null);
    const userMessage = input.trim();
    setMessages((prev) => [...prev, { role: "user", content: userMessage }]);
    setInput("");
    try {
      const payload = { message: userMessage, session_id: sessionId };
      const result =
        mode === "companion"
          ? await coachApi.companion(payload)
          : mode === "roleplay"
            ? await coachApi.roleplay({ ...payload, scene })
            : await coachApi.interview(payload);
      setSessionId(result.session_id);
      setMessages((prev) => [
        ...prev,
        { role: "coach", content: result.reply, corrections: result.corrections },
      ]);
      if (result.crisis) {
        setCrisis({ active: true, resources: result.crisis_resources });
      }
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "陪练服务暂时不可用。");
    } finally {
      setBusy(false);
    }
  }

  async function submitWriting() {
    if (!writingText.trim()) return;
    setBusy(true);
    setError(null);
    try {
      setWriting(await coachApi.writing({ kind: writingKind, text: writingText }));
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "文书辅助失败。");
    } finally {
      setBusy(false);
    }
  }

  const conversation = (
    <div className="space-y-3">
      {crisis.active ? (
        <Alert variant="danger" title="我们很在意你的安全">
          <p className="mb-2">
            专业支持比任何学习建议都重要。请立即联系家长、老师或拨打以下热线，也可直接拨打 120/110：
          </p>
          <ul className="list-disc space-y-1 pl-5">
            {crisis.resources.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </Alert>
      ) : null}

      <div className="max-h-96 space-y-2 overflow-y-auto rounded-lg border border-border p-3">
        {messages.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            {tab === "companion"
              ? "说说今天的学习状态吧：厌学、焦虑、卡壳都可以聊，我会先照顾情绪，再给具体行动。"
              : tab === "roleplay"
                ? scenes.find((item) => item.key === scene)?.opening ?? "选择一个场景后开始对话。"
                : "粘贴一道面试题或你的回答，我会给出内容/逻辑/表达三维反馈。"}
          </p>
        ) : null}
        {messages.map((message, index) => (
          <div key={index} className={message.role === "user" ? "text-right" : ""}>
            <div
              className={
                message.role === "user"
                  ? "inline-block rounded-xl bg-accent px-3 py-2 text-sm text-accent-foreground"
                  : "inline-block rounded-xl bg-muted px-3 py-2 text-sm text-foreground"
              }
            >
              <p className="whitespace-pre-wrap">{message.content}</p>
            </div>
            {message.corrections && message.corrections.length > 0 ? (
              <div className="mt-2 space-y-1">
                {message.corrections.map((item) => (
                  <p key={item.original} className="text-xs text-muted-foreground">
                    纠错：<span className="line-through">{item.original}</span> → {item.suggestion}（{item.note}）
                  </p>
                ))}
              </div>
            ) : null}
          </div>
        ))}
      </div>

      {tab === "roleplay" ? (
        <div className="max-w-sm space-y-2">
          <Label htmlFor="scene">场景</Label>
          <Select
            id="scene"
            data-testid="scene-select"
            options={scenes.map((item) => ({ value: item.key, label: item.title }))}
            value={scene}
            onChange={(event) => {
              setScene(event.target.value);
              resetConversation();
            }}
          />
        </div>
      ) : null}

      <div className="flex gap-2">
        <Input
          data-testid="coach-input"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") void send(tab as "companion" | "roleplay" | "interview");
          }}
          placeholder={tab === "roleplay" ? "Use English to reply..." : "说说你的情况…"}
        />
        <Button
          disabled={busy || !input.trim()}
          onClick={() => void send(tab as "companion" | "roleplay" | "interview")}
          data-testid="coach-send"
        >
          发送
        </Button>
      </div>
    </div>
  );

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <SectionTitle hint="陪练不替代心理咨询与教师指导：危机表述会优先引导专业求助。">
        陪练中心
      </SectionTitle>

      {error ? <ErrorBlock message={error} onRetry={() => setError(null)} /> : null}

      <Tabs
        defaultKey="companion"
        onChange={(key) => {
          setTab(key);
          resetConversation();
        }}
        tabs={[
          { key: "companion", label: "学习陪伴", content: conversation },
          { key: "roleplay", label: "情景口语", content: conversation },
          { key: "interview", label: "面试模拟", content: conversation },
          {
            key: "writing",
            label: "文书辅助",
            content: (
              <div className="space-y-3">
                <div className="flex flex-wrap items-end gap-3">
                  <div className="space-y-2">
                    <Label htmlFor="writing-kind">类型</Label>
                    <Select
                      id="writing-kind"
                      options={[
                        { value: "resume", label: "简历" },
                        { value: "cover_letter", label: "自荐信" },
                        { value: "paper_outline", label: "论文框架" },
                        { value: "custom", label: "其他" },
                      ]}
                      value={writingKind}
                      onChange={(event) => setWritingKind(event.target.value)}
                    />
                  </div>
                </div>
                <Textarea
                  data-testid="writing-input"
                  rows={6}
                  value={writingText}
                  onChange={(event) => setWritingText(event.target.value)}
                  placeholder="粘贴你的文书/论文片段：只给表达建议，不代写观点。"
                />
                <Button disabled={busy || !writingText.trim()} onClick={() => void submitWriting()} data-testid="writing-submit">
                  获取修改建议
                </Button>
                {writing ? (
                  <Card data-testid="writing-result">
                    <CardHeader>
                      <CardTitle>修改建议与批注</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-2 text-sm">
                      {writing.suggestions.map((item) => (
                        <p key={item}>· {item}</p>
                      ))}
                      {writing.annotations.map((item) => (
                        <p key={item.excerpt} className="text-muted-foreground">
                          批注：{item.excerpt} → {item.suggestion}
                        </p>
                      ))}
                      <Alert variant="info">{writing.integrity_notice}</Alert>
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
