/** 工具页：微课生成（F-16）+ V3 学习工具（F-04/F-26/F-36~F-38）。 */

import { useCallback, useEffect, useState } from "react";
import {
  Alert,
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Label,
  Select,
} from "@xueban/ui";

import { EmptyBlock, ErrorBlock, SectionTitle } from "@/components/state";
import { V3Tools } from "@/components/v3-tools";
import { ApiError, api, type MasteryPoint, type MicroLesson } from "@/lib/api";

export default function ToolsPage() {
  const [points, setPoints] = useState<MasteryPoint[]>([]);
  const [selected, setSelected] = useState("");
  const [lesson, setLesson] = useState<MicroLesson | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const loadPoints = useCallback(async () => {
    try {
      const data = await api.mastery();
      setPoints(data.points.slice(0, 30));
      const first = data.points[0];
      if (first) setSelected(first.knowledge_point_id);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "加载知识点失败。");
    }
  }, []);

  useEffect(() => {
    void loadPoints();
  }, [loadPoints]);

  async function handleCreate() {
    if (!selected) {
      setError("请先选择知识点。");
      return;
    }
    setBusy(true);
    setError(null);
    setAudioUrl(null);
    try {
      setLesson(await api.createMicroLesson(selected));
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "微课生成失败（可稍后重试）。");
    } finally {
      setBusy(false);
    }
  }

  async function handleAudio() {
    if (!lesson) return;
    setBusy(true);
    setError(null);
    try {
      const data = await api.microLessonAudio(lesson.lesson_id);
      setAudioUrl(data.url);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "音频尚未就绪，请稍后再试。");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <SectionTitle hint="微课讲解（F-16）与后续版本工具入口。">学习工具</SectionTitle>

      {error ? <ErrorBlock message={error} onRetry={() => setError(null)} /> : null}

      <Card>
        <CardHeader>
          <CardTitle>微课生成（F-16）</CardTitle>
          <CardDescription>选择薄弱知识点，生成 600~1000 字微课脚本与配音音频。</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {points.length > 0 ? (
            <>
              <div className="max-w-sm space-y-2">
                <Label htmlFor="micro-point">知识点</Label>
                <Select
                  id="micro-point"
                  options={points.map((point) => ({
                    value: point.knowledge_point_id,
                    label: `${point.name}（${Math.round(point.mastery * 100)}%）`,
                  }))}
                  value={selected}
                  onChange={(event) => setSelected(event.target.value)}
                />
              </div>
              <Button disabled={busy || !selected} onClick={() => void handleCreate()}>
                {busy ? "生成中…" : "生成微课"}
              </Button>
            </>
          ) : (
            <EmptyBlock title="暂无知识点数据" hint="先完成一次诊断，薄弱知识点会出现在这里。" />
          )}

          {lesson ? (
            <div className="space-y-2 rounded-lg border border-border p-4 text-sm" data-testid="micro-lesson">
              <div className="flex items-center gap-2">
                <p className="font-medium">{lesson.title}</p>
                <Badge variant={lesson.status === "ready" ? "success" : lesson.status === "failed" ? "danger" : "warning"}>
                  {lesson.status}
                </Badge>
              </div>
              <p className="text-muted-foreground">
                字数 {lesson.char_count} · 重试 {lesson.retries} 次
              </p>
              {lesson.error ? <Alert variant="warning">{lesson.error}</Alert> : null}
              <Button variant="outline" size="sm" disabled={busy} onClick={() => void handleAudio()}>
                获取配音音频
              </Button>
              {audioUrl ? (
                <audio controls src={audioUrl} data-testid="micro-audio" className="w-full">
                  您的浏览器不支持音频播放。
                </audio>
              ) : null}
            </div>
          ) : null}
        </CardContent>
      </Card>

      <div>
        <SectionTitle hint="拍照搜题 / 手写诊断 / 文档问答 / 知识卡片 / 编程判题">
          V3 学习工具
        </SectionTitle>
        <div className="mt-4">
          <V3Tools />
        </div>
      </div>
    </div>
  );
}
