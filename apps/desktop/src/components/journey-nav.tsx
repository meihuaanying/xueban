/**
 * 旅程导航（REBUILD §7 P0）：左侧主干 + 掌握度可视化。
 * 学院派骨架的知识地图导航，未满足前置条件的阶段不可点击（由状态机判定）。
 */
import { KnowledgeMap, MasteryBar, type KnowledgeNode } from "@xueban/ui";
import { NavLink } from "react-router-dom";

import { useJourney } from "../journey/journey-context";
import { STAGES, stageDefinition, type JourneyStage } from "../journey/stages";

function StageItem({ id, current }: { id: JourneyStage; current: boolean }) {
  const { canEnter, pathOf, state } = useJourney();
  const def = stageDefinition(id);
  const enabled = canEnter(id);
  const blockedBy = def.requires
    .filter((condition) => !state[condition.key])
    .map((condition) => condition.label)
    .join("、");
  const base =
    "flex min-h-[var(--tap-min)] items-center gap-sm rounded-control px-sm py-xs text-app transition-colors";

  if (!enabled) {
    return (
      <li aria-disabled="true" className={`${base} cursor-not-allowed opacity-50`}>
        <span aria-hidden="true" className="text-app-xs font-semibold text-muted-foreground">
          {def.order}
        </span>
        <span className="flex flex-col">
          <span className="text-app-sm">{def.label}</span>
          <span className="text-app-xs text-muted-foreground">需先完成：{blockedBy}</span>
        </span>
      </li>
    );
  }

  return (
    <li>
      <NavLink
        to={pathOf(id)}
        aria-current={current ? "step" : undefined}
        className={({ isActive }) =>
          `${base} ${isActive ? "bg-primary text-primary-foreground" : "text-foreground hover:bg-surface-sunken"}`
        }
      >
        <span
          aria-hidden="true"
          className={`text-app-xs font-semibold ${current ? "text-primary-foreground" : "text-muted-foreground"}`}
        >
          {def.order}
        </span>
        <span className="flex flex-col">
          <span className="text-app-sm font-medium">{def.label}</span>
          <span className={`text-app-xs ${current ? "text-primary-foreground" : "text-muted-foreground"}`}>
            {def.hint}
          </span>
        </span>
      </NavLink>
    </li>
  );
}

export interface JourneyNavProps {
  nodes?: KnowledgeNode[];
  overallMastery?: number;
  /** 点知识节点（场景 3：已预生成的讲解直接秒开）。不传则地图只读。 */
  onSelectNode?: (id: string) => void;
  speakable?: boolean;
  loading?: boolean;
  error?: string | null;
  /** 该学科知识点总数（地图只展示最薄弱的若干个，用它说明「还有多少」） */
  total?: number;
  onRetryNodes?: () => void;
}

export function JourneyNav({
  nodes = [],
  overallMastery = 0,
  onSelectNode,
  speakable = false,
  loading = false,
  error = null,
  total = 0,
  onRetryNodes,
}: JourneyNavProps) {
  const { stage } = useJourney();
  return (
    <nav
      aria-label="学习旅程"
      className="flex h-full w-[var(--sidebar-width)] shrink-0 flex-col gap-md border-r border-sidebar-border bg-sidebar px-sm py-md text-sidebar-foreground"
    >
      <div className="flex items-center gap-xs">
        <span
          aria-hidden="true"
          className="flex size-md items-center justify-center rounded-control bg-primary text-app font-semibold text-primary-foreground"
        >
          学
        </span>
        <span className="flex flex-col">
          <span className="text-app font-semibold">学伴</span>
          <span className="text-app-xs text-muted-foreground">桌面端</span>
        </span>
      </div>

      <ol className="flex flex-col gap-hair">
        {STAGES.map((def) => (
          <StageItem key={def.id} id={def.id} current={stage === def.id} />
        ))}
      </ol>

      <div className="mt-auto flex flex-col gap-xs">
        <span className="text-app-xs font-semibold text-muted-foreground">知识地图</span>
        {/* 「没数据」「还没学」「接口挂了」是三件事，必须分开说。把加载失败说成
            「完成诊断后显示」会让人以为是自己没诊断，白跑一趟。 */}
        {error ? (
          <div className="flex flex-col gap-hair" data-testid="kmap-error">
            <p className="text-app-xs text-destructive-foreground">知识点掌握度加载失败：{error}</p>
            {onRetryNodes ? (
              <button
                type="button"
                onClick={onRetryNodes}
                className="min-h-[var(--tap-min)] self-start rounded-control border border-border px-xs text-app-xs"
              >
                重试
              </button>
            ) : null}
          </div>
        ) : loading && nodes.length === 0 ? (
          <p className="text-app-xs text-muted-foreground" data-testid="kmap-loading">
            正在加载知识点掌握度…
          </p>
        ) : nodes.length > 0 ? (
          <KnowledgeMap
            title="知识点掌握度"
            nodes={nodes}
            onSelect={onSelectNode}
            speakable={speakable}
            caption={
              total > nodes.length ? (
                <span className="text-app-xs text-muted-foreground">
                  最该补的 {nodes.length} 个（共 {total}）
                </span>
              ) : null
            }
          />
        ) : (
          <p className="text-app-xs text-muted-foreground">完成诊断后显示知识点掌握度</p>
        )}
        <div className="flex items-center gap-xs">
          <span className="shrink-0 text-app-xs text-muted-foreground">总掌握度</span>
          <MasteryBar value={overallMastery} label="总掌握度" />
        </div>
      </div>
    </nav>
  );
}
