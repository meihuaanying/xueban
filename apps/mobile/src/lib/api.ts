/** 移动端 API 客户端（与 Web/桌面端同一后端契约）。 */

import { getApiBaseUrl } from "@xueban/core";

export const API_BASE_URL = getApiBaseUrl("http://localhost:8000");

export interface ApiErrorBody {
  code?: string;
  message?: string;
  trace_id?: string | null;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly traceId: string | null;

  constructor(status: number, body: ApiErrorBody) {
    super(body.message ?? "请求失败，请稍后重试");
    this.name = "ApiError";
    this.status = status;
    this.code = body.code ?? `HTTP_${status}`;
    this.traceId = body.trace_id ?? null;
  }
}

let accessToken: string | null = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

function parseBody(text: string): unknown {
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((init.headers as Record<string, string> | undefined) ?? {}),
  };
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  const response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });
  const body = parseBody(await response.text());
  if (!response.ok) throw new ApiError(response.status, (body ?? {}) as ApiErrorBody);
  return body as T;
}

const get = <T,>(path: string) => request<T>(path);
const post = <T,>(path: string, payload?: unknown) =>
  request<T>(path, {
    method: "POST",
    body: payload === undefined ? undefined : JSON.stringify(payload),
  });

/* ---------------------------------- 类型 ---------------------------------- */

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface UserProfile {
  id: string;
  phone: string;
  nickname: string | null;
  role: string;
  is_k12: boolean;
}

export interface DiagnosisQuestion {
  id: string;
  stem: string;
  qtype: string;
  options: Record<string, string> | null;
  difficulty: number;
  knowledge_points: string[];
}

export interface DiagnosisStart {
  exam_id: string;
  progress: { answered: number; total: number };
  question: DiagnosisQuestion;
}

export interface DiagnosisAnswer {
  is_correct: boolean;
  correct_answer: string;
  progress: { answered: number; total: number };
  finished: boolean;
  next_question: DiagnosisQuestion | null;
}

export interface MasteryPoint {
  knowledge_point_id: string;
  name: string;
  mastery: number;
  level: string;
}

export interface DiagnosisReport {
  has_data: boolean;
  points: MasteryPoint[];
}

export interface PathPhase {
  name: string;
  title: string;
  knowledge_points: { id: string; name: string; mastery: number }[];
}

export interface PathResponse {
  has_path: boolean;
  phases: PathPhase[];
}

export interface TodayTask {
  id: string;
  title: string;
  task_type: string;
  status: string;
}

export interface TodayResponse {
  date: string;
  tasks: TodayTask[];
  completed_count: number;
  total: number;
  all_completed: boolean;
  streak_days: number;
}

export interface TutorSession {
  session_id: string;
  question: { id: string; stem: string; difficulty: number; knowledge_points: string[] };
  hint_level: number;
  hint_level_name: string;
}

export interface PracticeQuestion {
  id: string;
  stem: string;
  qtype: string;
  options: Record<string, string> | null;
  difficulty: number;
  reason: string;
}

export interface PracticeAnswer {
  is_correct: boolean;
  correct_answer: string;
  mistake_collected: boolean;
  mistake_removed: boolean;
  explanation: string | null;
  duplicate?: boolean;
}

export interface MistakeEntry {
  id: string;
  question: { id: string; stem: string };
  error_reason_label: string | null;
  state: string;
  review_count: number;
}

export interface CalendarMonth {
  year: number;
  month: number;
  streak_days: number;
  days: { day: string; practice_count: number; studied: boolean }[];
}

export interface SubscriptionState {
  plan: string;
  expires_at: string | null;
  trial_used: boolean;
}

export interface BehaviorProfile {
  learning_style_label: string;
  evidence: Record<string, unknown>;
}

/* ---------------------------------- 端点 ---------------------------------- */

export const api = {
  register: (payload: { phone: string; password: string; nickname?: string }) =>
    post<TokenPair>("/v1/auth/register", { role: "student", ...payload }),
  login: (payload: { phone: string; password: string }) =>
    post<TokenPair>("/v1/auth/login", payload),
  me: () => get<UserProfile>("/v1/auth/me"),

  startDiagnosis: (payload: { subject: string; stage: string; target_count: number }) =>
    post<DiagnosisStart>("/v1/diagnosis/start", payload),
  answerDiagnosis: (examId: string, payload: { question_id: string; answer: string }) =>
    post<DiagnosisAnswer>(`/v1/diagnosis/${examId}/answer`, payload),
  diagnosisReport: (examId: string) => get<DiagnosisReport>(`/v1/diagnosis/${examId}/report`),
  mastery: () => get<{ has_data: boolean; points: MasteryPoint[] }>("/v1/profile/mastery"),
  behavior: () => get<BehaviorProfile>("/v1/profile/behavior"),

  path: () => get<PathResponse>("/v1/plan/path"),
  today: () => get<TodayResponse>("/v1/plan/today"),
  completeTask: (taskId: string) =>
    post<{ today: TodayResponse }>(`/v1/plan/tasks/${taskId}/complete`),

  createTutorSession: (questionId: string) =>
    post<TutorSession>("/v1/tutor/session", { question_id: questionId }),
  tutorHint: (sessionId: string, level?: number) =>
    post<{ level: number; level_name: string; content: string }>(
      `/v1/tutor/${sessionId}/hint`,
      level === undefined ? {} : { level },
    ),

  generatePractice: (payload: { subject: string; count: number }) =>
    post<{ questions: PracticeQuestion[]; weak_ratio: number }>("/v1/practice/generate", payload),
  answerPractice: (payload: {
    question_id: string;
    answer: string;
    source: string;
    client_event_id?: string;
  }) => post<PracticeAnswer>("/v1/practice/answer", payload),
  mistakes: () => get<{ active_count: number; entries: MistakeEntry[] }>("/v1/mistakes?limit=20"),
  repractice: () =>
    post<{ questions: { id: string; stem: string; options: Record<string, string> | null }[] }>(
      "/v1/mistakes/repractice",
      { count: 5 },
    ),

  calendar: (year: number, month: number) =>
    get<CalendarMonth>(`/v1/stats/calendar?year=${year}&month=${month}`),
  weeklyReport: () => get<{ week_start: string; week_end: string; report: Record<string, unknown> }>(
    "/v1/reports/weekly",
  ),
  sprint: () =>
    get<{ exam_date: string; remaining_days: number } | null>("/v1/exam-prep/sprint").catch(() => null),

  guardianStatus: () =>
    get<{
      locked: boolean;
      reasons: string[];
      used_minutes: number;
      limit_minutes: number | null;
      available_from: string | null;
    }>("/v1/guardian/status"),

  subscription: () => get<SubscriptionState>("/v1/billing/subscription"),
  startTrial: () => post<SubscriptionState>("/v1/billing/trial"),

  presignUpload: (payload: { filename: string; content_type: string; size_bytes: number }) =>
    post<{ key: string; url: string; fields: Record<string, string>; expires_in: number }>(
      "/v1/storage/presign-upload",
      payload,
    ),
};

/* ------------------------- SSE 流式提示（XHR，RN 兼容） ------------------------- */

export interface StreamHandlers {
  onStart?: (payload: { level: number; level_name: string }) => void;
  onDelta?: (content: string) => void;
  onDone?: (payload: { level: number; level_name: string; content: string }) => void;
}

export function streamTutorHint(
  sessionId: string,
  level: number | undefined,
  handlers: StreamHandlers,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE_URL}/v1/tutor/${sessionId}/hint/stream`);
    xhr.setRequestHeader("Content-Type", "application/json");
    if (accessToken) xhr.setRequestHeader("Authorization", `Bearer ${accessToken}`);
    let processed = 0;
    let buffer = "";
    let sawDone = false;

    const handleBlock = (block: string) => {
      let event = "message";
      let data = "";
      for (const line of block.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data += line.slice(5).trim();
      }
      if (!data) return;
      const payload = parseBody(data) as Record<string, unknown> | null;
      if (!payload) return;
      if (event === "start") handlers.onStart?.(payload as never);
      else if (event === "delta") handlers.onDelta?.(String(payload.content ?? ""));
      else if (event === "done") {
        sawDone = true;
        handlers.onDone?.(payload as never);
      }
    };

    xhr.onprogress = () => {
      buffer += xhr.responseText.slice(processed);
      processed = xhr.responseText.length;
      let index = buffer.indexOf("\n\n");
      while (index >= 0) {
        const block = buffer.slice(0, index);
        buffer = buffer.slice(index + 2);
        if (block.trim()) handleBlock(block);
        index = buffer.indexOf("\n\n");
      }
    };
    xhr.onload = () => {
      if (xhr.status >= 400) {
        reject(new ApiError(xhr.status, (parseBody(xhr.responseText) ?? {}) as ApiErrorBody));
        return;
      }
      if (buffer.trim()) handleBlock(buffer);
      if (sawDone) resolve();
      else reject(new ApiError(503, { code: "LLM_STREAM_INTERRUPTED", message: "讲解流式输出中断，请重试。" }));
    };
    xhr.onerror = () => reject(new Error("网络异常，请稍后重试。"));
    xhr.send(JSON.stringify(level === undefined ? {} : { level }));
  });
}

/* ------------------------------ 陪练（F-32~F-34） ------------------------------ */

export interface CoachTurn {
  session_id: string;
  scene: string;
  reply: string;
  corrections: { original: string; suggestion: string; note: string }[];
  followups: string[];
  crisis: boolean;
  crisis_resources: string[];
}

export const coachApi = {
  companion: (payload: { message: string; session_id?: string | null }) =>
    post<CoachTurn>("/v1/coach/companion", payload),
  roleplay: (payload: { message: string; scene: string; session_id?: string | null }) =>
    post<CoachTurn>("/v1/coach/roleplay", payload),
};
