"use client";

/**
 * 知识点掌握度（场景 3 的数据源）。
 *
 * 之前 `JourneyNav` 的 `KnowledgeMap` 拿不到任何节点——`app-layout.tsx` 是裸
 * `<JourneyNav />`，不传 `nodes`，于是地图永远不渲染。这个 hook 把它接上：
 * `GET /v1/profile/mastery` → `KnowledgeNode[]`。
 *
 * 「未接触」和「没数据」是两回事，所以「请求失败」绝不退化成空数组充数——那会让
 * 地图看起来像「你什么都没学」，实际是接口挂了。
 *
 * 请求带 `include_unseen=true`：知识地图要列出该学段全部知识点（没练过的标记为
 * 未接触），否则新用户一打开就是一片空白，根本无从点进讲解（§5.1 场景 3）。
 * 雷达图/画像那边不传，保持「我学过什么」的语义。
 */

import { useCallback, useEffect, useState } from "react";

import type { MasteryLevel, KnowledgeNode } from "@xueban/ui";
import { api } from "../lib/api";

/** 掌握度 0~1 → 1~5 档。用 ceil 而不是 round：刚学会一点也该显示「入门」而不是「未接触」。 */
export function toMasteryLevel(mastery: number): MasteryLevel {
  if (mastery <= 0) return 1;
  return Math.min(5, Math.max(1, Math.ceil(mastery * 5))) as MasteryLevel;
}

/** 侧边栏只放得下这么多节点。
 *
 * 后端 `include_unseen` 会把该学科**整个学段**的知识点全列出来（小学数学一二年级
 * 就有 38 个），全铺进侧边栏既挤又没人看得完。掌握度接口已按掌握度升序排
 * （最弱在前），所以截前 N 个正好是「最该补的那几个」，不是随手截断。
 */
export const MAX_MAP_NODES = 12;

/** 方块里显示的短名：去掉「20 以内」这类数字前缀，再截到 4 个字。
 *
 * 「20 以内数的认识」→「以内数的」，比直接截成「20 以内」信息量大——
 * 数字前缀对认字量有限的一年级孩子反而是噪音。完整名仍交给无障碍与朗读。 */
export function shortLabelOf(name: string): string {
  const core = name.replace(/^[0-9]+\s*/, "");
  return core.length > 4 ? core.slice(0, 4) : core;
}

export interface KnowledgeMasteryState {
  nodes: KnowledgeNode[];
  /** 实际拿到的知识点总数（可能被 MAX_MAP_NODES 截断，用于提示「还有 N 个」）。 */
  total: number;
  loading: boolean;
  error: string | null;
  /** 当前打开讲解的知识点编码；空 = 还没点任何节点。 */
  selected: string;
  select: (code: string) => void;
  clear: () => void;
  reload: () => Promise<void>;
}

export function useKnowledgeMastery(subject?: string): KnowledgeMasteryState {
  const [nodes, setNodes] = useState<KnowledgeNode[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState("");

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const overview = await api.mastery(subject, { includeUnseen: true });
      setTotal(overview.points.length);
      setNodes(
        overview.points.slice(0, MAX_MAP_NODES).map((point) => ({
          // 节点 id 用课程编码（如 g1m-add-within-10）：讲解接口两种都收，
          // 编码比库内 UUID 更可读，调试时一眼能认出是哪个知识点。
          id: point.code,
          label: point.name,
          shortLabel: shortLabelOf(point.name),
          subject: point.subject,
          level: toMasteryLevel(point.mastery),
          progress: point.mastery,
        })),
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "知识地图加载失败。");
      setNodes([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [subject]);

  useEffect(() => {
    void reload();
  }, [reload]);

  return {
    nodes,
    total,
    loading,
    error,
    selected,
    select: setSelected,
    clear: () => setSelected(""),
    reload,
  };
}
