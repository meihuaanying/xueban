"use client";

/** 阶段页：今日任务（第 1 站） */
import { Badge, Button, Card, CardContent, CardHeader, CardTitle, Progress, StreakFlame } from "@xueban/ui";

import { AsyncFeedback, JourneyStepper } from "../../components/journey-blocks";
import { StageShell } from "../../components/stage-shell";
import { useJourney } from "../../journey/journey-context";
import { useToday } from "../../journey/use-journey-data";

const TASK_LABEL: Record<string, string> = {
  diagnosis: "诊断测评",
  lesson: "学习单元",
  practice: "练习",
  review: "错题复习",
  reflect: "复盘",
};

export default function TodayStagePage() {
  const { theme, mark } = useJourney();
  const today = useToday();
  const tasks = today.data?.tasks ?? [];
  const done = today.data?.completed_count ?? 0;
  const total = today.data?.total ?? 0;

  return (
    <StageShell
      stage="today"
      title="今日任务"
      description="今天要学什么、练什么、复习什么，都在这里按顺序排好。"
      speakable={theme === "kids"}
      data-testid="stage-today"
    >
      <div className="flex flex-col gap-md">
        <div className="flex flex-wrap items-center justify-between gap-sm">
          <StreakFlame
            days={today.data?.streak_days ?? 0}
            goal={7}
            doneToday={today.data?.all_completed ?? false}
          />
          <div className="flex items-center gap-sm">
            <span className="text-app-sm text-muted-foreground">
              今日进度 {done} / {total}
            </span>
            <div className="w-40">
              <Progress
                value={done}
                max={Math.max(total, 1)}
                label="今日任务进度"
                aria-valuetext={`${done} / ${total}`}
              />
            </div>
          </div>
        </div>

        <AsyncFeedback
          loading={today.loading}
          error={today.error}
          empty={!today.loading && tasks.length === 0}
          emptyTitle="今天还没有任务"
          emptyHint="完成首次诊断后，系统会按你的掌握度自动排出今天的学习计划。"
          onRetry={today.reload}
        >
          <ol className="flex flex-col gap-sm" data-testid="today-tasks">
            {tasks.map((task) => (
              <li key={task.id}>
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center justify-between gap-sm text-app">
                      {task.title}
                      <Badge variant={task.status === "done" ? "success" : "outline"}>
                        {task.status === "done" ? "已完成" : (TASK_LABEL[task.task_type] ?? "学习")}
                      </Badge>
                    </CardTitle>
                  </CardHeader>
                  {task.status !== "done" ? (
                    <CardContent>
                      <Button
                        type="button"
                        data-testid={`today-complete-${task.id}`}
                        onClick={() => void today.complete(task.id)}
                      >
                        标记完成
                      </Button>
                    </CardContent>
                  ) : null}
                </Card>
              </li>
            ))}
          </ol>
        </AsyncFeedback>

        {today.data?.all_completed ? (
          <Card className="border-success">
            <CardHeader>
              <CardTitle className="text-success">今天全部完成</CardTitle>
            </CardHeader>
            <CardContent className="text-app-sm text-foreground">
              明天会按复习算法安排新的内容，记得先看错题。
              <Button
                type="button"
                className="ml-sm"
                variant="outline"
                onClick={() => mark({ reviewDone: true })}
              >
                去复盘
              </Button>
            </CardContent>
          </Card>
        ) : null}

        <JourneyStepper />
      </div>
    </StageShell>
  );
}
