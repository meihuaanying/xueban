import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

import { KnowledgeMapCard } from "./knowledge-map-card";

const generateExplainer = vi.fn();
const mastery = vi.fn();

vi.mock("@/lib/api", () => ({
  api: {
    mastery: (...args: unknown[]) => mastery(...args),
    // 复刻真实签名：mode 有默认值 "interactive"，调用方只传 knowledgeId
    generateExplainer: (id: string) => generateExplainer(id, "interactive"),
  },
}));

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

function overview(points: unknown[]) {
  return {
    has_data: points.length > 0,
    average_mastery: 0.6,
    red_count: 0,
    yellow_count: points.length,
    green_count: 0,
    points,
  };
}

beforeEach(() => {
  mastery.mockReset();
  generateExplainer.mockReset();
  // 默认走「缓存命中」：直接带 content 返回，不进轮询（§5.1 场景 3 的秒开路径）。
  // 若返回 content=null，useExplainer 会去轮询 explainerJob，那不在本用例关注范围。
  generateExplainer.mockResolvedValue({
    job_id: "job-1",
    content: {
      id: "c1",
      knowledge_id: "g1m-add-within-10",
      stage: "grade1_2",
      title: "10 以内加法",
      status: "ready",
      html: "<h1>凑十法</h1>",
      degraded: false,
      byte_size: 20,
      script: { acts: [] },
      render_timeout_seconds: 60,
    },
  });
});

describe("KnowledgeMapCard（§5.1 场景 3）", () => {
  it("点节点就把课程编码交给讲解接口——用编码而不是显示名，否则后端 404", async () => {
    mastery.mockResolvedValue(overview([point()]));
    render(<KnowledgeMapCard subject="math" />);
    await waitFor(() => expect(screen.getByTestId("kmap-node-g1m-add-within-10")).toBeTruthy());
    screen.getByTestId("kmap-node-g1m-add-within-10").click();
    await waitFor(() =>
      expect(generateExplainer).toHaveBeenCalledWith("g1m-add-within-10", "interactive"),
    );
  });

  it("按科目取数并带上 include_unseen", async () => {
    mastery.mockResolvedValue(overview([point()]));
    render(<KnowledgeMapCard subject="math" />);
    await waitFor(() => expect(mastery).toHaveBeenCalledWith("math", { includeUnseen: true }));
  });

  it("接口失败时说失败并给重试，不能谎称「还没有知识点」", async () => {
    mastery.mockRejectedValue(new Error("网络断了"));
    render(<KnowledgeMapCard subject="math" />);
    await waitFor(() => expect(screen.getByText(/网络断了/)).toBeTruthy());
    expect(screen.queryByText("还没有知识点")).toBeNull();
  });

  it("一个知识点都没有时才显示空态引导", async () => {
    mastery.mockResolvedValue(overview([]));
    render(<KnowledgeMapCard subject="math" />);
    await waitFor(() => expect(screen.getByText("还没有知识点")).toBeTruthy());
  });

  it("方块里放短名，完整名留给无障碍——中文长名会撑破 64px 方块", async () => {
    mastery.mockResolvedValue(overview([point({ name: "20 以内数的认识" })]));
    render(<KnowledgeMapCard subject="math" />);
    await waitFor(() => expect(screen.getByTestId("kmap-node-g1m-add-within-10")).toBeTruthy());
    const node = screen.getByTestId("kmap-node-g1m-add-within-10");
    // 无障碍名用完整名
    expect(node.getAttribute("aria-label")).toContain("20 以内数的认识");
    // 视觉层（aria-hidden 的那个 span）是短名
    const visual = node.querySelector("span.block");
    expect(visual?.textContent).toBe("以内数的");
  });
});