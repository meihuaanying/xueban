/** 复盘页（T5.6 / F-27~F-30）：周报、学习日历热力图、冲刺包。 */

import { useCallback, useEffect, useState } from "react";
import {
  Alert,
  Badge,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  StatCard,
  cn,
} from "@xueban/ui";

import { EmptyBlock, ErrorBlock, LoadingBlock, SectionTitle } from "@/components/state";
import { ApiError, api, type CalendarMonth, type ShareResult, type SprintPack, type WeeklyReport } from "@/lib/api";

function renderReportValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (Array.isArray(value)) return `${value.length} 项`;
  if (typeof value === "object") return JSON.stringify(value).slice(0, 120);
  return String(value);
}

export default function ReviewPage() {
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [calendar, setCalendar] = useState<CalendarMonth | null>(null);
  const [weekly, setWeekly] = useState<WeeklyReport | null>(null);
  const [share, setShare] = useState<ShareResult | null>(null);
  const [sprint, setSprint] = useState<SprintPack | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [calendarData, weeklyData, sprintData] = await Promise.all([
        api.calendar(year, month),
        api.weeklyReport().catch(() => null),
        api.sprint().catch(() => null),
      ]);
      setCalendar(calendarData);
      setWeekly(weeklyData);
      setSprint(sprintData);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "加载复盘数据失败。");
    } finally {
      setLoading(false);
    }
  }, [year, month]);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleShare() {
    setBusy(true);
    setError(null);
    try {
      setShare(await api.shareWeekly());
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "分享链接生成失败。");
    } finally {
      setBusy(false);
    }
  }

  async function handleRevoke(token: string) {
    setBusy(true);
    try {
      await api.revokeShare(token);
      setShare(null);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "吊销失败。");
    } finally {
      setBusy(false);
    }
  }

  function shiftMonth(delta: number) {
    const date = new Date(year, month - 1 + delta, 1);
    setYear(date.getFullYear());
    setMonth(date.getMonth() + 1);
  }

  if (loading) return <LoadingBlock rows={4} label="加载复盘数据" />;

  const maxPractice = calendar?.max_practice ?? 0;

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <SectionTitle hint="周报每周日自动生成且可分享（可吊销）；日历热力图展示每日练习强度。">
        学习复盘
      </SectionTitle>

      {error ? <ErrorBlock message={error} onRetry={() => void load()} /> : null}

      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard title="连续打卡" value={`${calendar?.streak_days ?? 0} 天`} tone="success" />
        <StatCard title="本月练习最多的一天" value={`${maxPractice} 题`} />
        <StatCard title="冲刺包" value={sprint ? `${sprint.remaining_days} 天` : "未设置考期"} hint="距考试日" />
      </div>

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <CardTitle>学习日历</CardTitle>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={() => shiftMonth(-1)}>
                上个月
              </Button>
              <span className="text-sm text-muted-foreground" data-testid="calendar-month">
                {year} 年 {month} 月
              </span>
              <Button variant="outline" size="sm" onClick={() => shiftMonth(1)}>
                下个月
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-7 gap-1 text-center text-xs text-muted-foreground" data-testid="calendar-grid">
            {calendar?.days.map((day) => {
              const intensity = maxPractice > 0 ? day.practice_count / maxPractice : 0;
              return (
                <div
                  key={day.day}
                  title={`${day.day}：练习 ${day.practice_count} 题`}
                  data-studied={day.studied ? "true" : "false"}
                  className={cn(
                    "flex aspect-square flex-col items-center justify-center rounded border border-border",
                    day.studied ? "text-foreground" : "text-muted-foreground",
                  )}
                  style={
                    day.practice_count > 0
                      ? { backgroundColor: `rgba(31, 102, 245, ${0.15 + intensity * 0.65})` }
                      : undefined
                  }
                >
                  <span>{Number(day.day.slice(-2))}</span>
                  {day.practice_count > 0 ? <span className="text-[10px]">{day.practice_count}</span> : null}
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <CardTitle>本周学习周报</CardTitle>
            <Button variant="outline" size="sm" disabled={busy} onClick={() => void handleShare()}>
              生成分享链接
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          {weekly ? (
            <>
              <p className="text-muted-foreground" data-testid="weekly-range">
                {weekly.week_start} ~ {weekly.week_end}
              </p>
              <div className="grid gap-3 sm:grid-cols-2">
                {Object.entries(weekly.report).map(([key, value]) => (
                  <div key={key} className="rounded-lg border border-border px-4 py-3">
                    <p className="text-xs text-muted-foreground">{key}</p>
                    <p className="mt-1">{renderReportValue(value)}</p>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <EmptyBlock title="暂无周报" hint="本周有学习记录后会自动生成周报。" />
          )}

          {share ? (
            <Alert variant="success" title="分享链接已生成（免登录只读，可随时吊销）">
              <p className="break-all" data-testid="share-link">
                {share.url_path}
              </p>
              <p className="mt-1 text-xs">有效期至 {share.expires_at}</p>
              <div className="mt-2 flex gap-2">
                <Button size="sm" variant="outline" disabled={busy} onClick={() => void handleRevoke(share.token)}>
                  吊销链接
                </Button>
              </div>
            </Alert>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>考前冲刺包（F-30）</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          {sprint ? (
            <>
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="warning">考试日 {sprint.exam_date}</Badge>
                <Badge variant="outline">剩余 {sprint.remaining_days} 天</Badge>
              </div>
              <p className="text-muted-foreground">
                高频错题 {sprint.high_freq_mistakes.length} 道 · 未掌握知识点{" "}
                {sprint.unmastered_knowledge_points.length} 个 · 预测卷{" "}
                {sprint.predicted_paper.length} 题
              </p>
            </>
          ) : (
            <EmptyBlock title="未设置考期" hint="在「规划」页填写考试日期后，这里会生成冲刺包。" />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
