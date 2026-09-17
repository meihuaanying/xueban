/** 规划页（T5.3 / F-06~F-10）：学习路径、今日任务打卡、考期倒排。 */

import { useCallback, useEffect, useState } from "react";
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Input,
  Label,
  Progress,
  StatCard,
} from "@xueban/ui";

import { EmptyBlock, ErrorBlock, LoadingBlock, SectionTitle } from "@/components/state";
import { ApiError, api, type ExamCountdown, type PathResponse, type TodayResponse } from "@/lib/api";
import { useSync } from "@/lib/sync";

export default function PlanPage() {
  const { version } = useSync();
  const [path, setPath] = useState<PathResponse | null>(null);
  const [today, setToday] = useState<TodayResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [examDate, setExamDate] = useState("");
  const [countdown, setCountdown] = useState<ExamCountdown | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [pathData, todayData] = await Promise.all([api.path(), api.today()]);
      setPath(pathData);
      setToday(todayData);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "无法连接服务器，请稍后重试。");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  // 其他端有新数据（版本变化）时自动刷新本页
  useEffect(() => {
    if (version) void load();
  }, [version, load]);

  async function handleComplete(taskId: string) {
    setBusy(true);
    setError(null);
    try {
      const result = await api.completeTask(taskId);
      setToday(result.today);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "完成任务失败，请重试。");
    } finally {
      setBusy(false);
    }
  }

  async function handleRegenerate() {
    setBusy(true);
    setError(null);
    try {
      const result = await api.regeneratePath();
      setPath(result);
      const todayData = await api.today();
      setToday(todayData);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "重排失败，请重试。");
    } finally {
      setBusy(false);
    }
  }

  async function handleCountdown() {
    if (!examDate) {
      setError("请选择考试日期。");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await api.examCountdown({ exam_date: examDate });
      setCountdown(result);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "考期倒排失败，请重试。");
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <LoadingBlock rows={4} label="加载学习路径" />;

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <SectionTitle hint="路径按前置依赖排序；完成任务即打卡，连续天数实时更新。">学习规划</SectionTitle>

      {error ? <ErrorBlock message={error} onRetry={() => setError(null)} /> : null}

      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard
          title="今日完成"
          value={today ? `${today.completed_count} / ${today.total}` : "—"}
          hint="任务卡完成进度"
        />
        <StatCard
          title="连续打卡"
          value={today ? `${today.streak_days} 天` : "—"}
          hint="全部任务完成才计入"
          tone={today && today.streak_days > 0 ? "success" : "default"}
        />
        <StatCard title="路径阶段" value={path ? String(path.phases.length) : "—"} hint="先补前置 → 当前 → 拔高" />
      </div>

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <CardTitle>今日任务卡</CardTitle>
            <Badge variant={today?.all_completed ? "success" : "outline"}>
              {today?.all_completed ? "已全部完成" : "进行中"}
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-2">
          {today && today.tasks.length > 0 ? (
            today.tasks.map((task) => (
              <div
                key={task.id}
                className="flex items-center justify-between gap-3 rounded-lg border border-border px-4 py-3"
                data-testid="today-task"
              >
                <div>
                  <p className="text-sm font-medium">{task.title}</p>
                  <p className="text-xs text-muted-foreground">
                    {task.task_type} · {task.status === "done" ? "已完成" : "待完成"}
                  </p>
                </div>
                {task.status === "done" ? (
                  <Badge variant="success">已完成</Badge>
                ) : (
                  <Button size="sm" disabled={busy} onClick={() => void handleComplete(task.id)}>
                    完成任务
                  </Button>
                )}
              </div>
            ))
          ) : (
            <EmptyBlock title="今天还没有任务" hint="先做一次诊断，系统会按薄弱点生成今日任务。" />
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <CardTitle>学习路径</CardTitle>
            <Button variant="outline" size="sm" disabled={busy} onClick={() => void handleRegenerate()}>
              按最新学情重排
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {path?.has_path ? (
            path.phases.map((phase) => (
              <div key={phase.name} className="space-y-2" data-testid="path-phase">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-semibold">{phase.title}</p>
                  <Badge variant="outline">{phase.knowledge_points.length} 个知识点</Badge>
                </div>
                <div className="space-y-2">
                  {phase.knowledge_points.slice(0, 6).map((point) => (
                    <div key={point.id} className="space-y-1">
                      <div className="flex items-center justify-between text-xs text-muted-foreground">
                        <span>{point.name}</span>
                        <span>{Math.round(point.mastery * 100)}%</span>
                      </div>
                      <Progress value={Math.round(point.mastery * 100)} />
                    </div>
                  ))}
                </div>
              </div>
            ))
          ) : (
            <EmptyBlock title="尚未生成学习路径" hint="完成一次诊断后会自动生成。" />
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>考期倒排（F-08）</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-end gap-3">
            <div className="space-y-2">
              <Label htmlFor="exam-date">考试日期</Label>
              <Input
                id="exam-date"
                type="date"
                value={examDate}
                onChange={(event) => setExamDate(event.target.value)}
              />
            </div>
            <Button disabled={busy} onClick={() => void handleCountdown()}>
              生成倒排计划
            </Button>
          </div>
          {countdown ? (
            <div className="space-y-3" data-testid="countdown-result">
              <p className="text-sm text-muted-foreground">
                共 {countdown.total_days} 天{countdown.compressed ? "（已压缩）" : ""}，分 {countdown.phases.length} 个阶段
              </p>
              {countdown.warning ? (
                <p className="text-sm text-warning" data-testid="countdown-warning">
                  {countdown.warning}
                </p>
              ) : null}
              <ol className="space-y-2">
                {countdown.phases.map((phase) => (
                  <li key={phase.name} className="rounded-lg border border-border px-4 py-3 text-sm">
                    <p className="font-medium">
                      {phase.title} · {phase.days} 天
                    </p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {phase.start} ~ {phase.end} · {phase.focus}
                    </p>
                  </li>
                ))}
              </ol>
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
