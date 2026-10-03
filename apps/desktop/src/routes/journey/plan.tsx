"use client";

/** 阶段页：规划（第 3 站） */
import { Button, Card, CardContent, CardHeader, CardTitle, MasteryBar } from "@xueban/ui";

import { AsyncFeedback, JourneyStepper } from "../../components/journey-blocks";
import { StageShell } from "../../components/stage-shell";
import { useJourney } from "../../journey/journey-context";
import { GRADE_BANDS } from "../../journey/stages";
import { useAsync, useMastery } from "../../journey/use-journey-data";
import { api, type PathPhase } from "../../lib/api";
import { KnowledgeMapCard } from "./knowledge-map-card";

export default function PlanStagePage() {
  const { band, theme, mark, goTo } = useJourney();
  const preset = band ? GRADE_BANDS[band] : GRADE_BANDS.primary;
  const path = useAsync(() => api.path(preset.subject), [preset.subject]);
  const mastery = useMastery(preset.subject);
  const phases = path.data?.phases ?? [];
  const hasPath = Boolean(path.data?.has_path) && phases.length > 0;

  return (
    <StageShell
      stage="plan"
      title="学习规划"
      description="按你的掌握度排出来的学习顺序，先补最薄弱的。"
      speakable={theme === "kids"}
      data-testid="stage-plan"
    >
      <div className="flex flex-col gap-md">
        <AsyncFeedback
          loading={path.loading}
          error={path.error}
          empty={!path.loading && !hasPath}
          emptyTitle="还没有学习规划"
          emptyHint="完成一次诊断后，系统会按薄弱知识点排出一条学习路径。"
          onRetry={path.reload}
        >
          <ol className="flex flex-col gap-sm" data-testid="plan-phases">
            {phases.map((phase: PathPhase, index: number) => (
              <li key={phase.name}>
                <Card>
                  <CardHeader>
                    <CardTitle className="text-app">{phase.title}</CardTitle>
                  </CardHeader>
                  <CardContent className="flex flex-col gap-xs">
                    {phase.knowledge_points.map((point) => (
                      <div
                        key={point.id}
                        className="flex items-center justify-between gap-sm"
                      >
                        <span className="text-app-sm text-foreground">{point.name}</span>
                        <div className="w-32">
                          <MasteryBar
                            value={point.mastery}
                            label={`${point.name} 掌握度`}
                            showValue
                          />
                        </div>
                      </div>
                    ))}
                    <p className="text-app-xs text-muted-foreground">
                      第 {index + 1} 阶段 · 共 {phase.knowledge_points.length} 个知识点
                    </p>
                  </CardContent>
                </Card>
              </li>
            ))}
          </ol>
        </AsyncFeedback>

        <Card>
          <CardHeader>
            <CardTitle>知识掌握总览</CardTitle>
          </CardHeader>
          <CardContent>
            <AsyncFeedback
              loading={mastery.loading}
              error={mastery.error}
              empty={!mastery.loading && !mastery.data?.has_data}
              emptyTitle="还没有掌握度数据"
              onRetry={mastery.reload}
            >
              <p className="text-app-sm text-foreground">
                平均掌握度{" "}
                {Math.round((mastery.data?.average_mastery ?? 0) * 100)}%，
                薄弱 {mastery.data?.red_count ?? 0} 项，待巩固{" "}
                {mastery.data?.yellow_count ?? 0} 项。
              </p>
            </AsyncFeedback>
          </CardContent>
        </Card>

        {/* 场景 3（§5.1）：知识地图节点 → 已预生成的讲解直接秒开。
            放在这一站是因为侧边栏在儿童模式下没有地图——那是妹妹真正用的主题。 */}
        <KnowledgeMapCard subject={preset.subject} speakable={theme === "kids"} />

        {hasPath ? (
          <Button
            type="button"
            data-testid="plan-to-unit"
            onClick={() => {
              mark({ planReady: true });
              goTo("unit");
            }}
          >
            开始学习单元
          </Button>
        ) : null}

        <JourneyStepper />
      </div>
    </StageShell>
  );
}
