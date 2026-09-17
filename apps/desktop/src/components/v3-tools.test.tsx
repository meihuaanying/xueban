import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { V3Tools } from "./v3-tools";
import { api, v3Api } from "@/lib/api";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: { ...actual.api, createTutorSession: vi.fn() },
    v3Api: {
      photoSearch: vi.fn(),
      handwriting: vi.fn(),
      libraryList: vi.fn(),
      libraryAsk: vi.fn(),
      librarySelfTest: vi.fn(),
      cards: vi.fn(),
      createCard: vi.fn(),
      exportCards: vi.fn(),
      judge: vi.fn(),
    },
  };
});

const mockedV3 = vi.mocked(v3Api);
const mockedApi = vi.mocked(api);

beforeEach(() => {
  vi.clearAllMocks();
  mockedV3.libraryList.mockResolvedValue([
    { id: "doc-1", title: "数学讲义", page_count: 2, chunk_count: 3, status: "ready" },
  ]);
  mockedV3.cards.mockResolvedValue({
    cards: [{ id: "c1", front: "问题", back: "答案", tags: ["学伴"] }],
    total: 1,
  });
});

describe("V3 学习工具（桌面）", () => {
  it("拍照搜题只返回引导入口并可创建讲解会话", async () => {
    mockedV3.photoSearch.mockResolvedValue({
      recognized_text: "计算 18 × 5",
      confidence: 0.93,
      degraded: false,
      degradation_hint: null,
      match_found: true,
      question_id: "q1",
      tutor_entry: "/v1/tutor/session",
      knowledge_points: ["有理数乘法"],
    });
    mockedApi.createTutorSession.mockResolvedValue({
      session_id: "11111111-1111-1111-1111-111111111111",
      question: { id: "q1", stem: "计算 18 × 5", qtype: "choice", options: null, difficulty: 2, knowledge_points: [] },
      hint_level: 0,
      hint_level_name: "未开始",
      max_hint_level: 3,
    });
    render(<V3Tools />);
    await waitFor(() => expect(mockedV3.libraryList).toHaveBeenCalled());

    fireEvent.change(screen.getByTestId("photo-text"), { target: { value: "计算 18 × 5" } });
    fireEvent.click(screen.getByTestId("photo-search"));
    await waitFor(() => expect(screen.getByTestId("photo-result")).toBeTruthy());
    expect(screen.getByTestId("photo-result").textContent).toContain("题库已匹配");
    expect(screen.getByTestId("photo-result").textContent).not.toContain("正确选项");

    fireEvent.click(screen.getByTestId("start-guided"));
    await waitFor(() => expect(mockedApi.createTutorSession).toHaveBeenCalledWith("q1"));
  });

  it("拍照搜题降级提示", async () => {
    mockedV3.photoSearch.mockResolvedValue({
      recognized_text: "",
      confidence: 0,
      degraded: true,
      degradation_hint: "请手动确认题目文本",
      match_found: false,
      question_id: null,
      tutor_entry: "/v1/tutor/session",
      knowledge_points: [],
    });
    render(<V3Tools />);
    fireEvent.change(screen.getByTestId("photo-text"), { target: { value: "题目" } });
    fireEvent.click(screen.getByTestId("photo-search"));
    await waitFor(() => expect(screen.getByText("请手动确认题目文本")).toBeTruthy());
  });

  it("手写诊断定位首个出错步骤", async () => {
    mockedV3.handwriting.mockResolvedValue({
      steps: [
        { index: 0, content: "2x = 4", is_error: false, note: "与参考步骤一致" },
        { index: 1, content: "x = 3", is_error: true, note: "数值不一致" },
      ],
      first_error_step: 1,
      confidence: 0.9,
      degraded: false,
      degradation_hint: null,
      advice: "第 2 步开始出现偏差",
    });
    render(<V3Tools />);
    fireEvent.click(screen.getByRole("tab", { name: "手写诊断" }));
    fireEvent.change(screen.getByTestId("handwriting-text"), { target: { value: "2x = 4\nx = 3" } });
    fireEvent.change(screen.getAllByPlaceholderText(/参考解答/)[0]!, {
      target: { value: "2x = 4\nx = 2" },
    });
    fireEvent.click(screen.getByTestId("handwriting-run"));
    await waitFor(() => expect(screen.getByTestId("handwriting-result")).toBeTruthy());
    expect(screen.getByTestId("handwriting-result").textContent).toContain("第 2 步开始出现偏差");
  });

  it("文档问答与自测题", async () => {
    mockedV3.libraryAsk.mockResolvedValue({
      answer: "根据文档内容：等式两边同时加上同一个数仍然成立。",
      citations: [{ page: 2, chunk_id: "chunk-1", excerpt: "第二章 一元一次方程" }],
    });
    mockedV3.librarySelfTest.mockResolvedValue({
      questions: [{ question: "请复述第 2 页要点", answer: "等式性质", page: 2 }],
    });
    render(<V3Tools />);
    fireEvent.click(screen.getByRole("tab", { name: "文档问答" }));
    await waitFor(() => expect(screen.getByText(/数学讲义/)).toBeTruthy());
    fireEvent.change(screen.getByTestId("doc-question"), { target: { value: "等式性质？" } });
    fireEvent.click(screen.getByRole("button", { name: "提问" }));
    await waitFor(() => expect(screen.getByTestId("doc-answer")).toBeTruthy());
    expect(screen.getByTestId("doc-answer").textContent).toContain("第 2 页");
    expect(screen.getByText(/自测/)).toBeTruthy();
  });

  it("知识卡片创建与导出", async () => {
    mockedV3.createCard.mockResolvedValue({ id: "c2", front: "新问题", back: "新答案", tags: [] });
    const blob = new Blob(["apkg"]);
    mockedV3.exportCards.mockResolvedValue(blob);
    const createObjectURL = vi.fn().mockReturnValue("blob:mock");
    const revokeObjectURL = vi.fn();
    vi.stubGlobal("URL", { ...URL, createObjectURL, revokeObjectURL });
    render(<V3Tools />);
    fireEvent.click(screen.getByRole("tab", { name: "知识卡片" }));
    fireEvent.change(screen.getByTestId("card-front"), { target: { value: "新问题" } });
    fireEvent.change(screen.getByTestId("card-back"), { target: { value: "新答案" } });
    fireEvent.click(screen.getByTestId("card-create"));
    await waitFor(() => expect(mockedV3.createCard).toHaveBeenCalled());

    fireEvent.click(screen.getByTestId("card-export"));
    await waitFor(() => expect(mockedV3.exportCards).toHaveBeenCalled());
    vi.unstubAllGlobals();
  });

  it("编程判题展示三维反馈与拦截原因", async () => {
    mockedV3.judge.mockResolvedValue({
      verdict: "blocked",
      passed: 0,
      total: 1,
      results: [],
      feedback: { boundary: ["边界建议"], complexity: ["复杂度建议"], style: ["风格建议"] },
      blocked_reason: "代码包含沙箱禁止的调用：socket.",
    });
    render(<V3Tools />);
    fireEvent.click(screen.getByRole("tab", { name: "编程判题" }));
    fireEvent.click(screen.getByTestId("judge-run"));
    await waitFor(() => expect(screen.getByTestId("judge-result")).toBeTruthy());
    expect(screen.getByTestId("judge-result").textContent).toContain("blocked");
    expect(screen.getByText(/沙箱禁止/)).toBeTruthy();
    expect(screen.getByText("边界条件")).toBeTruthy();
  });
});
