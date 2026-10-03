"use client";

/**
 * 知识地图讲解面板（REBUILD §5.1 触发场景 3）。
 *
 * 「知识地图节点 → 已预生成的讲解直接秒开」这条路径原本只有侧边栏一处，而侧边栏
 * 在儿童模式（§4.1）下是 `KidsNavBar`，**没有地图**——也就是说妹妹实际用的那套
 * 主题里，场景 3 根本进不去。所以把地图放进「规划」这一站：两套主题都能到，
 * 而且「规划」本来就是一张地图该待的地方。
 *
 * 与侧边栏那份的关系是刻意重复的：侧边栏给已经在学的孩子一个常驻入口，这份给
 * 专门来「看看哪个知识点不会」的时刻。两者都只读同一个接口，互不影响。
 */

import { Card, CardContent, CardHeader, CardTitle, KnowledgeMap } from "@xueban/ui";

import { AsyncFeedback } from "@/components/journey-blocks";
import { useKnowledgeMastery } from "@/journey/use-knowledge-mastery";
import { useExplainer } from "@/journey/use-explainer";
import { ExplainerDock } from "./explainer-launcher";

export interface KnowledgeMapCardProps {
  subject: string;
  /** kids 主题下朗读节点名（7 岁可用性：一切文本可朗读） */
  speakable?: boolean;
}

export function KnowledgeMapCard({ subject, speakable = false }: KnowledgeMapCardProps) {
  const mastery = useKnowledgeMastery(subject);
  const explainer = useExplainer();

  return (
    <Card data-testid="knowledge-map-card">
      <CardHeader>
        <CardTitle>知识地图</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-sm">
        <p className="text-app-xs text-muted-foreground">
          点一个方块，就能看这个知识点的动画讲解。越红的越是需要补的。
        </p>
        <AsyncFeedback
          loading={mastery.loading}
          error={mastery.error}
          empty={!mastery.loading && !mastery.error && mastery.nodes.length === 0}
          emptyTitle="还没有知识点"
          emptyHint="先做一次诊断，系统会把这门课的知识点摆出来。"
          onRetry={() => void mastery.reload()}
        >
          <KnowledgeMap
            title="知识点掌握度"
            nodes={mastery.nodes}
            onSelect={(id) => {
              mastery.select(id);
              void explainer.open(id);
            }}
            speakable={speakable}
            caption={
              mastery.total > mastery.nodes.length ? (
                <span className="text-app-xs text-muted-foreground">
                  最该补的 {mastery.nodes.length} 个（共 {mastery.total}）
                </span>
              ) : null
            }
          />
          <ExplainerDock
            explainer={explainer}
            knowledgeId={mastery.selected}
            speakable={speakable}
            testId="kmap-card-explainer"
          />
        </AsyncFeedback>
      </CardContent>
    </Card>
  );
}