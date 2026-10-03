import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";

import { MAX_MAP_NODES, shortLabelOf, toMasteryLevel, useKnowledgeMastery } from "./use-knowledge-mastery";
import { api } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  api: { mastery: vi.fn() },
}));

const mastery = vi.mocked(api.mastery);

function point(overrides: Record<string, unknown> = {}) {
  return {
    knowledge_point_id: "11111111-1111-1111-1111-111111111111",
    code: "g1m-add-within-10",
    name: "10 以内加法",
    subject: "math",
    stage: "grade1_2",
    mastery: 0.6,
    level: "yellow",
    total_attempts: 5,
    correct_attempts: 3,
    last_practiced_at: null,
    ...overrides,
  };
}

beforeEach(() => {
  mastery.mockReset();
});

describe("toMasteryLevel", () => {
  it("0 归到最低档", () => {
    expect(toMasteryLevel(0)).toBe(1);
  });

  it("用 ceil 而不是 round：刚学会一点也该显示「入门」而不是「未接触」", () => {
    expect(toMasteryLevel(0.21)).toBe(2);
    expect(toMasteryLevel(0.2)).toBe(1);
  });

  it("上限封在 5", () => {
    expect(toMasteryLevel(1)).toBe(5);
    expect(toMasteryLevel(2)).toBe(5);
  });
});

describe("shortLabelOf", () => {
  it("去掉「10 以内」这类数字前缀——对一年级孩子反而是噪音", () => {
    expect(shortLabelOf("10 以内加法")).toBe("以内加法");
    expect(shortLabelOf("20 以内数的认识")).toBe("以内数的");
  });

  it("没有数字前缀时直接截到 4 个字", () => {
    expect(shortLabelOf("认识钟表")).toBe("认识钟表");
    expect(shortLabelOf("认识钟表和时分")).toBe("认识钟表");
  });
});

describe("useKnowledgeMastery", () => {
  it("把掌握度点转成知识地图节点，id 用课程编码（可直接喂讲解接口）", async () => {
    mastery.mockResolvedValue({
      has_data: true,
      average_mastery: 0.6,
      red_count: 0,
      yellow_count: 1,
      green_count: 0,
      points: [point()],
    });
    const { result } = renderHook(() => useKnowledgeMastery());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.nodes).toEqual([
      {
        id: "g1m-add-within-10",
        label: "10 以内加法",
        // 方块里放短名（「以内加法」），完整名留给无障碍与朗读，
        // 否则 6 个字会直接撑破 52/64px 的方块。
        shortLabel: "以内加法",
        subject: "math",
        level: 3,
        progress: 0.6,
      },
    ]);
  });

  it("没练过时返回空数组，而不是编一批 level=1 的假节点", async () => {
    mastery.mockResolvedValue({
      has_data: false,
      average_mastery: null,
      red_count: 0,
      yellow_count: 0,
      green_count: 0,
      points: [],
    });
    const { result } = renderHook(() => useKnowledgeMastery());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.nodes).toEqual([]);
  });

  it("接口失败时给错误文案且不留半截数据", async () => {
    mastery.mockRejectedValue(new Error("网络断了"));
    const { result } = renderHook(() => useKnowledgeMastery());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).toBe("网络断了");
    expect(result.current.nodes).toEqual([]);
  });

  it("记录当前选中的知识点（场景 3 的讲解入口）", async () => {
    mastery.mockResolvedValue({
      has_data: true,
      average_mastery: 0.6,
      red_count: 0,
      yellow_count: 1,
      green_count: 0,
      points: [point()],
    });
    const { result } = renderHook(() => useKnowledgeMastery());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.selected).toBe("");
    result.current.select("g1m-add-within-10");
    await waitFor(() => expect(result.current.selected).toBe("g1m-add-within-10"));
  });

  it("按学段科目取数，并带上 include_unseen（新用户才有节点可点）", async () => {
    mastery.mockResolvedValue({
      has_data: false,
      average_mastery: null,
      red_count: 0,
      yellow_count: 0,
      green_count: 0,
      points: [],
    });
    renderHook(() => useKnowledgeMastery("math"));
    await waitFor(() => expect(mastery).toHaveBeenCalledWith("math", { includeUnseen: true }));
  });

  it("侧边栏只放最薄弱的 MAX_MAP_NODES 个，但 total 如实报告总数", async () => {
    // include_unseen 会把整个学段的知识点全列出来（小学数学一二年级 38 个），
    // 全铺进侧边栏没人看得完。掌握度接口已按掌握度升序排，截前 N 个即最该补的。
    const many = Array.from({ length: MAX_MAP_NODES + 5 }, (_, i) =>
      point({ code: `g1m-p${i}`, name: `知识点${i}` }),
    );
    mastery.mockResolvedValue({
      has_data: true,
      average_mastery: 0.6,
      red_count: 0,
      yellow_count: many.length,
      green_count: 0,
      points: many,
    });
    const { result } = renderHook(() => useKnowledgeMastery("math"));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.nodes).toHaveLength(MAX_MAP_NODES);
    expect(result.current.total).toBe(many.length);
    // 截的是前 N 个（最薄弱的），不是随机取
    expect(result.current.nodes[0]?.id).toBe("g1m-p0");
  });
});
