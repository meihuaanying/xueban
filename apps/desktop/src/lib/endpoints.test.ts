import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, api, coachApi, setAccessToken, v3Api } from "./api";

function mockFetch(payload: unknown, status = 200) {
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(JSON.stringify(payload), {
      status,
      headers: { "Content-Type": "application/json" },
    }),
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

beforeEach(() => {
  setAccessToken(null);
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("桌面端 API 端点拼装", () => {
  const cases: [string, () => Promise<unknown>, string, string?][] = [
    ["register", () => api.register({ phone: "13900000000", password: "password123" }), "/v1/auth/register", "POST"],
    ["login", () => api.login({ phone: "13900000000", password: "password123" }), "/v1/auth/login", "POST"],
    ["me", () => api.me(), "/v1/auth/me", "GET"],
    ["logout", () => api.logout("refresh-1"), "/v1/auth/logout", "POST"],
    ["startDiagnosis", () => api.startDiagnosis({ subject: "math", stage: "junior", target_count: 20 }), "/v1/diagnosis/start", "POST"],
    ["answerDiagnosis", () => api.answerDiagnosis("exam-1", { question_id: "q1", answer: "A" }), "/v1/diagnosis/exam-1/answer", "POST"],
    ["diagnosisReport", () => api.diagnosisReport("exam-1"), "/v1/diagnosis/exam-1/report", "GET"],
    ["mastery", () => api.mastery("math"), "/v1/profile/mastery?subject=math", "GET"],
    ["behavior", () => api.behavior(), "/v1/profile/behavior", "GET"],
    ["path", () => api.path(), "/v1/plan/path", "GET"],
    ["regeneratePath", () => api.regeneratePath(), "/v1/plan/path/regenerate", "POST"],
    ["today", () => api.today(), "/v1/plan/today", "GET"],
    ["completeTask", () => api.completeTask("t1"), "/v1/plan/tasks/t1/complete", "POST"],
    ["examCountdown", () => api.examCountdown({ exam_date: "2027-01-01" }), "/v1/plan/exam-countdown", "POST"],
    ["createTutorSession", () => api.createTutorSession("q1"), "/v1/tutor/session", "POST"],
    ["tutorHint", () => api.tutorHint("s1", 1), "/v1/tutor/s1/hint", "POST"],
    ["tutorVariants", () => api.tutorVariants("s1"), "/v1/tutor/s1/variants", "POST"],
    ["answerVariant", () => api.answerVariant("s1", "v1", "A"), "/v1/tutor/s1/variants/v1/answer", "POST"],
    ["tutorAnalogy", () => api.tutorAnalogy("s1"), "/v1/tutor/s1/analogy", "POST"],
    ["tutorAltSolutions", () => api.tutorAltSolutions("s1"), "/v1/tutor/s1/alt-solutions", "POST"],
    ["generatePractice", () => api.generatePractice({ subject: "math", count: 5 }), "/v1/practice/generate", "POST"],
    ["answerPractice", () => api.answerPractice({ question_id: "q1", answer: "A", source: "practice" }), "/v1/practice/answer", "POST"],
    ["mistakes", () => api.mistakes({ state: "active", limit: 20 }), "/v1/mistakes?state=active&limit=20", "GET"],
    ["repractice", () => api.repractice({ count: 5 }), "/v1/mistakes/repractice", "POST"],
    ["reviewDue", () => api.reviewDue(5), "/v1/review/due?limit=5", "GET"],
    ["reviewGrade", () => api.reviewGrade("c1", 3), "/v1/review/c1/grade", "POST"],
    ["createExam", () => api.createExam({ subject: "math", count: 5 }), "/v1/exams", "POST"],
    ["getExam", () => api.getExam("exam-1"), "/v1/exams/exam-1", "GET"],
    ["submitExam", () => api.submitExam("exam-1", [{ question_id: "q1", answer: "A" }]), "/v1/exams/exam-1/submit", "POST"],
    ["weeklyReport", () => api.weeklyReport(), "/v1/reports/weekly", "GET"],
    ["shareWeekly", () => api.shareWeekly(), "/v1/reports/weekly/share", "POST"],
    ["revokeShare", () => api.revokeShare("tok"), "/v1/reports/shares/tok", "DELETE"],
    ["calendar", () => api.calendar(2026, 9), "/v1/stats/calendar?year=2026&month=9", "GET"],
    ["sprint", () => api.sprint(), "/v1/exam-prep/sprint", "GET"],
    ["gradeSubjective", () => api.gradeSubjective({ student_answer: "x" }), "/v1/grading/subjective", "POST"],
    ["gradeEssay", () => api.gradeEssay({ rubric: "gaokao", content: "作文" }), "/v1/grading/essay", "POST"],
    ["objectiveGrading", () => api.objectiveGrading({ question_id: "q1", answer: "A" }), "/v1/grading/objective", "POST"],
    ["createMicroLesson", () => api.createMicroLesson("kp-1"), "/v1/micro-lessons", "POST"],
    ["microLessonAudio", () => api.microLessonAudio("l1"), "/v1/micro-lessons/l1/audio", "GET"],
    ["syncState", () => api.syncState(), "/v1/sync/state", "GET"],
    ["guardianStatus", () => api.guardianStatus(), "/v1/guardian/status", "GET"],
    ["subscription", () => api.subscription(), "/v1/billing/subscription", "GET"],
    ["startTrial", () => api.startTrial(), "/v1/billing/trial", "POST"],
  ];

  it.each(cases)("%s 请求 %s", async (_name, call, path, method) => {
    const fetchMock = mockFetch({});
    await call();
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain(path);
    if (method) {
      expect((init.method ?? "GET").toUpperCase()).toBe(method);
    }
  });

  it("携带 Bearer 令牌并支持 refresh 重放", async () => {
    setAccessToken("token-abc");
    const fetchMock = mockFetch({ ok: true });
    await api.me();
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer token-abc");
  });

  it("非 2xx 抛 ApiError", async () => {
    mockFetch({ code: "TEST_ERROR", message: "失败", trace_id: "t-9" }, 400);
    await expect(api.me()).rejects.toBeInstanceOf(ApiError);
  });
});

describe("陪练与 V3 端点", () => {
  it("coachApi 场景/陪伴/角色扮演/面试/文书", async () => {
    for (const [call, path] of [
      [() => coachApi.scenes(), "/v1/coach/scenes"],
      [() => coachApi.companion({ message: "hi" }), "/v1/coach/companion"],
      [() => coachApi.roleplay({ message: "hi", scene: "restaurant" }), "/v1/coach/roleplay"],
      [() => coachApi.interview({ message: "hi" }), "/v1/coach/interview"],
      [() => coachApi.writing({ kind: "resume", text: "文本" }), "/v1/coach/writing"],
    ] as [() => Promise<unknown>, string][]) {
      const fetchMock = mockFetch({});
      await call();
      expect((fetchMock.mock.calls[0] as [string, RequestInit])[0]).toContain(path);
    }
  });

  it("v3Api 端点与 .apkg 下载", async () => {
    for (const [call, path] of [
      [() => v3Api.photoSearch({ ocr_text: "题目" }), "/v1/tools/photo-search"],
      [() => v3Api.handwriting({ ocr_text: "a", reference_solution: "b" }), "/v1/diagnosis/handwriting"],
      [() => v3Api.libraryList(), "/v1/library/docs"],
      [() => v3Api.libraryAsk("doc-1", "问题"), "/v1/library/doc-1/ask"],
      [() => v3Api.librarySelfTest("doc-1"), "/v1/library/doc-1/self-test"],
      [() => v3Api.cards(), "/v1/cards"],
      [() => v3Api.createCard({ front: "f", back: "b", tags: [] }), "/v1/cards"],
      [() => v3Api.judge({ code: "print(1)", tests: [] }), "/v1/grading/code"],
    ] as [() => Promise<unknown>, string][]) {
      const fetchMock = mockFetch({});
      await call();
      expect((fetchMock.mock.calls[0] as [string, RequestInit])[0]).toContain(path);
    }

    setAccessToken("tok");
    const blobMock = vi.fn().mockResolvedValue(
      new Response(new Blob(["zip-bytes"]), { status: 200 }),
    );
    vi.stubGlobal("fetch", blobMock);
    const blob = await v3Api.exportCards();
    expect(blob.size).toBeGreaterThan(0);
    const [, init] = blobMock.mock.calls[0] as [string, RequestInit];
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer tok");
  });

  it(".apkg 下载失败抛 ApiError", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ code: "CARD_EMPTY", message: "暂无卡片" }), { status: 404 }),
      ),
    );
    await expect(v3Api.exportCards()).rejects.toBeInstanceOf(ApiError);
  });
});
