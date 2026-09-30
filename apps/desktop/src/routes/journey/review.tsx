"use client";

/** 旅程第 6 站 · 复盘：本周学习报告 + 旅程收尾。 */
import { Button, Card, CardContent, CardHeader, CardTitle, StatCard } from "@xueban/ui";
import { useCallback } from "react";

import { AsyncFeedback, JourneyStepper } from "@/components/journey-blocks";
import { StageShell } from "@/components/stage-shell";
import { useJourney } from "@/journey/journey-context";
import { useWeeklyReport } from "@/journey/use-journey-data";

type Report = Record<string, unknown>;

/**
 * 按点分路径读取周报指标，例如 `practice.total`、`mastery.green_count`。
 * 后端 `build_weekly_report` 返回的是嵌套结构（见 services/api/app/services/report_service.py），
 * 顶层没有扁平 key，所以不能直接 `report[key]`。
 */
function readNumber(report: Report, path: string): number | null {
  const value = path.split(".").reduce<unknown>((node, key) => {
    if (node && typeof node === "object") return (node as Record<string, unknown>)[key];
    return undefined;
  }, report);
  return typeof value === "number" ? value : null;
}

function Metric({
  label,
  report,
  path,
  suffix,
}: {
  label: string;
  report: Report;
  path: string;
  suffix?: string;
}) {
  const value = readNumber(report, path);
  return (
    <StatCard
      title={label}
      value={value === null ? "—" : `${value}${suffix ?? ""}`}
      hint={value === null ? "本周暂无数据" : undefined}
    />
  );
}

export default function ReviewStagePage() {
  const { mark, advance } = useJourney();
  const weekly = useWeeklyReport();

  const finish = useCallback(() => {
    mark({ reviewDone: true });
    advance();
  }, [advance, mark]);

  const report = (weekly.data?.report ?? {}) as Report;
  const suggestions = Array.isArray(report.suggestions)
    ? report.suggestions.filter((item): item is string => typeof item === "string")
    : [];

  return (
    <StageShell
      stage="review"
      title="学习复盘"
      description="看看这一周学了什么、掌握到什么程度，明天从今日任务继续。"
      speakable
      data-testid="stage-review"
    >
      <div className="flex flex-col gap-md">
        <AsyncFeedback
          loading={weekly.loading}
          error={weekly.error}
          onRetry={() => void weekly.reload()}
        >
          <section aria-label="本周概览" className="flex flex-col gap-sm" data-testid="weekly-report">
            <h3 className="text-app-lg font-semibold">本周概览</h3>
            <p className="text-app-xs text-muted-foreground">
              {weekly.data?.week_start} ~ {weekly.data?.week_end}
            </p>
            <div className="grid grid-cols-2 gap-sm md:grid-cols-4">
              <Metric label="练习题量" report={report} path="practice.total" />
              <Metric label="答对题数" report={report} path="practice.correct" />
              <Metric label="掌握知识点" report={report} path="mastery.green_count" />
              <Metric label="本周完成任务" report={report} path="tasks.done" />
            </div>
            <Card>
              <CardHeader>
                <CardTitle>下一步</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-xs">
                {suggestions.length > 0 ? (
                  <ul aria-label="本周建议" className="flex flex-col gap-xs">
                    {suggestions.map((item) => (
                      <li key={item} className="text-app-sm">
                        {item}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-app-sm text-muted-foreground">
                    掌握度不足的知识点会优先出现在「学习规划」里；错题会在 24 小时后进入复习卡。
                  </p>
                )}
                <p className="text-app-sm">守护型讲解：先自己想一想，卡住了再看提示，不直接给答案。</p>
              </CardContent>
            </Card>
          </section>
        </AsyncFeedback>

        <Button onClick={finish} data-testid="review-finish">
          完成今天的学习
        </Button>
        <JourneyStepper />
      </div>
    </StageShell>
  );
}
