/** 学习 Tab：主页（今日任务/打卡）+ 诊断 + 规划 + 复盘（T6.2）。 */

import { useCallback, useEffect, useState } from "react";
import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { Text, View } from "react-native";

import { Badge, Card, EmptyBlock, ErrorBlock, Loading, PrimaryButton, Screen } from "../components/ui";
import {
  ApiError,
  api,
  type CalendarMonth,
  type DiagnosisQuestion,
  type DiagnosisReport,
  type MasteryPoint,
  type PathResponse,
  type TodayResponse,
} from "../lib/api";
import type { LearnStackParamList } from "../navigation";

type Nav = NativeStackNavigationProp<LearnStackParamList>;

export function LearnHomeScreen() {
  const navigation = useNavigation<Nav>();
  const [today, setToday] = useState<TodayResponse | null>(null);
  const [points, setPoints] = useState<MasteryPoint[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [todayData, mastery] = await Promise.all([api.today(), api.mastery()]);
      setToday(todayData);
      setPoints(mastery.points);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "加载学习数据失败。");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function complete(taskId: string) {
    setBusy(true);
    try {
      const result = await api.completeTask(taskId);
      setToday(result.today);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "打卡失败，请重试。");
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <Loading label="加载学习数据" />;

  const red = points.filter((point) => point.level === "red").length;
  const yellow = points.filter((point) => point.level === "yellow").length;
  const green = points.filter((point) => point.level === "green").length;

  return (
    <Screen title="学习" hint="今日任务完成后计入连续打卡；先诊断，再规划，再练习。">
      {error ? <ErrorBlock message={error} onRetry={() => void load()} /> : null}

      <Card testID="today-card">
        <View className="flex-row items-center justify-between">
          <Text className="font-semibold text-foreground">今日任务</Text>
          <Badge label={`连续 ${today?.streak_days ?? 0} 天`} tone={(today?.streak_days ?? 0) > 0 ? "success" : "default"} />
        </View>
        <Text className="mt-1 text-sm text-muted">
          完成 {today?.completed_count ?? 0} / {today?.total ?? 0}
          {today?.all_completed ? " · 今日已全部完成" : ""}
        </Text>
        <View className="mt-3 gap-2">
          {today?.tasks.map((task) => (
            <View
              key={task.id}
              testID="today-task"
              className="flex-row items-center justify-between rounded-xl border border-border px-3 py-2"
            >
              <Text className="flex-1 pr-2 text-sm text-foreground">{task.title}</Text>
              {task.status === "done" ? (
                <Badge label="已完成" tone="success" />
              ) : (
                <PrimaryButton label="打卡" disabled={busy} onPress={() => void complete(task.id)} />
              )}
            </View>
          ))}
          {today && today.tasks.length === 0 ? (
            <EmptyBlock title="今天还没有任务" hint="先完成一次诊断，系统会生成今日任务。" />
          ) : null}
        </View>
      </Card>

      <Card testID="mastery-card">
        <Text className="font-semibold text-foreground">学情画像</Text>
        <Text className="mt-1 text-sm text-muted">
          红 {red} · 黄 {yellow} · 绿 {green}（共 {points.length} 个知识点）
        </Text>
        <View className="mt-2 gap-1">
          {points.slice(0, 5).map((point) => (
            <Text key={point.knowledge_point_id} className="text-sm text-foreground">
              {point.name} · {Math.round(point.mastery * 100)}%
            </Text>
          ))}
        </View>
      </Card>

      <View className="flex-row flex-wrap gap-2">
        <View className="min-w-[45%] flex-1">
          <PrimaryButton label="开始诊断" onPress={() => navigation.navigate("Diagnosis")} />
        </View>
        <View className="min-w-[45%] flex-1">
          <PrimaryButton label="学习规划" variant="outline" onPress={() => navigation.navigate("Plan")} />
        </View>
        <View className="min-w-[45%] flex-1">
          <PrimaryButton label="学习复盘" variant="outline" onPress={() => navigation.navigate("Review")} />
        </View>
        <View className="min-w-[45%] flex-1">
          <PrimaryButton label="拍照搜题" variant="outline" onPress={() => navigation.navigate("Camera")} />
        </View>
        <View className="min-w-[45%] flex-1">
          <PrimaryButton label="语音助手" variant="outline" onPress={() => navigation.navigate("Voice")} />
        </View>
        <View className="min-w-[45%] flex-1">
          <PrimaryButton label="陪练中心" variant="outline" onPress={() => navigation.navigate("Coach")} />
        </View>
      </View>
    </Screen>
  );
}

export function DiagnosisScreen() {
  const [examId, setExamId] = useState<string | null>(null);
  const [question, setQuestion] = useState<DiagnosisQuestion | null>(null);
  const [answer, setAnswer] = useState("");
  const [feedback, setFeedback] = useState<{ is_correct: boolean; correct_answer: string } | null>(null);
  const [progress, setProgress] = useState<{ answered: number; total: number } | null>(null);
  const [report, setReport] = useState<DiagnosisReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function start() {
    setBusy(true);
    setError(null);
    try {
      const started = await api.startDiagnosis({ subject: "math", stage: "junior", target_count: 20 });
      setExamId(started.exam_id);
      setQuestion(started.question);
      setProgress(started.progress);
      setFeedback(null);
      setAnswer("");
      setReport(null);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "无法开始诊断。");
    } finally {
      setBusy(false);
    }
  }

  async function submit() {
    if (!examId || !question || !answer.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const result = await api.answerDiagnosis(examId, { question_id: question.id, answer: answer.trim() });
      setProgress(result.progress);
      if (result.finished) {
        setReport(await api.diagnosisReport(examId));
        setQuestion(null);
      } else {
        setFeedback(result);
        setQuestion(result.next_question);
      }
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "提交失败。");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Screen title="诊断" hint="自适应诊断 20 题；答对加难、答错降难。">
      {error ? <ErrorBlock message={error} onRetry={() => setError(null)} /> : null}

      {!examId && !report ? (
        <Card>
          <Text className="text-sm text-muted">将进行 20 道自适应题目，预计 8~12 分钟。</Text>
          <View className="mt-3">
            <PrimaryButton label="开始诊断" disabled={busy} onPress={() => void start()} testID="start-diagnosis" />
          </View>
        </Card>
      ) : null}

      {question ? (
        <Card testID="diagnosis-question">
          <Text className="text-sm text-muted">
            第 {(progress?.answered ?? 0) + 1} / {progress?.total ?? 20} 题 · 难度 {question.difficulty}
          </Text>
          <Text className="mt-2 text-base text-foreground">{question.stem}</Text>
          <View className="mt-3 gap-2">
            {question.options
              ? Object.entries(question.options).map(([key, label]) => (
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
          {!question.options ? (
            <View className="mt-3">
              <PrimaryButton label="输入答案" variant="outline" onPress={() => setAnswer("1")} testID="fill-answer" />
            </View>
          ) : null}
          {feedback ? (
            <View className="mt-3" testID="diagnosis-feedback">
              <Text className={feedback.is_correct ? "text-sm text-success" : "text-sm text-danger"}>
                {feedback.is_correct ? "回答正确" : `回答错误 · 正确答案 ${feedback.correct_answer}`}
              </Text>
            </View>
          ) : null}
          <View className="mt-3">
            <PrimaryButton
              label={busy ? "提交中…" : "提交答案"}
              disabled={busy || !answer.trim()}
              onPress={() => void submit()}
              testID="submit-answer"
            />
          </View>
        </Card>
      ) : null}

      {report ? (
        <Card testID="diagnosis-report">
          <Text className="font-semibold text-foreground">诊断报告</Text>
          <Text className="mt-1 text-sm text-muted">共 {report.points.length} 个知识点纳入画像</Text>
          <View className="mt-3 gap-1">
            {report.points.slice(0, 10).map((point) => (
              <Text key={point.knowledge_point_id} className="text-sm text-foreground">
                {point.name} · {Math.round(point.mastery * 100)}% · {point.level}
              </Text>
            ))}
          </View>
          <View className="mt-3">
            <PrimaryButton label="再测一次" variant="outline" onPress={() => void start()} />
          </View>
        </Card>
      ) : null}
    </Screen>
  );
}

export function PlanScreen() {
  const [path, setPath] = useState<PathResponse | null>(null);
  const [today, setToday] = useState<TodayResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [pathData, todayData] = await Promise.all([api.path(), api.today()]);
      setPath(pathData);
      setToday(todayData);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "加载规划失败。");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) return <Loading label="加载学习路径" />;

  return (
    <Screen title="规划" hint="路径按前置依赖排序；每日任务卡 3~5 个。">
      {error ? <ErrorBlock message={error} onRetry={() => void load()} /> : null}
      <Card testID="plan-today">
        <Text className="font-semibold text-foreground">
          今日任务 {today ? `${today.completed_count}/${today.total}` : ""}
        </Text>
        <Text className="mt-1 text-sm text-muted">连续打卡 {today?.streak_days ?? 0} 天</Text>
        <View className="mt-2 gap-2">
          {today?.tasks.map((task) => (
            <Text key={task.id} className="text-sm text-foreground">
              {task.status === "done" ? "✓ " : "· "}
              {task.title}
            </Text>
          ))}
        </View>
      </Card>
      {path?.has_path ? (
        path.phases.map((phase) => (
          <Card key={phase.name} testID="path-phase">
            <Text className="font-semibold text-foreground">{phase.title}</Text>
            <View className="mt-2 gap-1">
              {phase.knowledge_points.slice(0, 5).map((point) => (
                <Text key={point.id} className="text-sm text-muted">
                  {point.name} · {Math.round(point.mastery * 100)}%
                </Text>
              ))}
            </View>
          </Card>
        ))
      ) : (
        <EmptyBlock title="尚未生成学习路径" hint="完成一次诊断后自动生成。" />
      )}
    </Screen>
  );
}

export function ReviewScreen() {
  const now = new Date();
  const [calendar, setCalendar] = useState<CalendarMonth | null>(null);
  const [report, setReport] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const [calendarData, weekly] = await Promise.all([
          api.calendar(now.getFullYear(), now.getMonth() + 1),
          api.weeklyReport().catch(() => null),
        ]);
        setCalendar(calendarData);
        setReport(weekly?.report ?? null);
      } catch (caught) {
        setError(caught instanceof ApiError ? caught.message : "加载复盘数据失败。");
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <Screen title="复盘" hint="日历热力图与周报数据来自同一 API。">
      {error ? <ErrorBlock message={error} /> : null}
      <Card testID="review-calendar">
        <Text className="font-semibold text-foreground">
          {now.getFullYear()} 年 {now.getMonth() + 1} 月 · 连续打卡 {calendar?.streak_days ?? 0} 天
        </Text>
        <View className="mt-3 flex-row flex-wrap gap-1">
          {calendar?.days.map((day) => (
            <View
              key={day.day}
              className={`h-6 w-6 items-center justify-center rounded ${
                day.studied ? "bg-primary" : "bg-secondary"
              }`}
            >
              <Text className={day.studied ? "text-[10px] text-white" : "text-[10px] text-muted"}>
                {Number(day.day.slice(-2))}
              </Text>
            </View>
          ))}
        </View>
      </Card>
      <Card testID="review-weekly">
        <Text className="font-semibold text-foreground">本周周报</Text>
        {report ? (
          Object.entries(report)
            .slice(0, 6)
            .map(([key, value]) => (
              <Text key={key} className="mt-1 text-sm text-muted">
                {key}：{typeof value === "object" ? JSON.stringify(value).slice(0, 60) : String(value)}
              </Text>
            ))
        ) : (
          <Text className="mt-1 text-sm text-muted">本周暂无学习记录。</Text>
        )}
      </Card>
    </Screen>
  );
}
