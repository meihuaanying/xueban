/**
 * 桌面端 API 客户端：统一错误契约（code/message/trace_id）与类型化端点。
 */

export const API_BASE_URL =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://localhost:8000";

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

export function getAccessToken(): string | null {
  return accessToken;
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
  if (!response.ok) {
    throw new ApiError(response.status, (body ?? {}) as ApiErrorBody);
  }
  return body as T;
}

function get<T>(path: string): Promise<T> {
  return request<T>(path);
}

function post<T>(path: string, payload?: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    body: payload === undefined ? undefined : JSON.stringify(payload),
  });
}

function del<T>(path: string): Promise<T> {
  return request<T>(path, { method: "DELETE" });
}

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
  created_at: string;
}

export interface SubscriptionState {
  plan: string;
  started_at: string | null;
  expires_at: string | null;
  trial_used: boolean;
  auto_renew: boolean;
}

export interface DiagnosisProgress {
  answered: number;
  total: number;
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
  status: string;
  progress: DiagnosisProgress;
  question: DiagnosisQuestion;
}

export interface DiagnosisAnswer {
  exam_id: string;
  is_correct: boolean;
  correct_answer: string;
  progress: DiagnosisProgress;
  finished: boolean;
  next_question: DiagnosisQuestion | null;
}

export interface MasteryPoint {
  knowledge_point_id: string;
  code: string;
  name: string;
  subject: string;
  stage: string;
  mastery: number;
  level: "red" | "yellow" | "green" | string;
  total_attempts: number;
  correct_attempts: number;
  last_practiced_at: string | null;
}

export interface MasteryOverview {
  has_data: boolean;
  average_mastery: number | null;
  red_count: number;
  yellow_count: number;
  green_count: number;
  points: MasteryPoint[];
}

export interface DiagnosisReport {
  exam_id: string;
  finished: boolean;
  summary: Record<string, unknown>;
  points: MasteryPoint[];
  has_data: boolean;
}

export interface PathPoint {
  id: string;
  name: string;
  mastery: number;
}

export interface PathPhase {
  name: string;
  title: string;
  knowledge_points: PathPoint[];
}

export interface PathResponse {
  has_path: boolean;
  plan_id: string | null;
  generated_at: string | null;
  phases: PathPhase[];
}

export interface TodayTask {
  id: string;
  title: string;
  task_type: string;
  status: string;
  ref_type: string | null;
  ref_id: string | null;
}

export interface TodayResponse {
  date: string;
  tasks: TodayTask[];
  completed_count: number;
  total: number;
  all_completed: boolean;
  streak_days: number;
}

export interface CompleteTaskResponse {
  task: TodayTask;
  today: TodayResponse;
}

export interface CountdownPhase {
  name: string;
  title: string;
  start: string;
  end: string;
  days: number;
  focus: string;
}

export interface ExamCountdown {
  plan_id: string;
  exam_date: string;
  total_days: number;
  compressed: boolean;
  warning: string | null;
  phases: CountdownPhase[];
}

export interface TutorQuestion {
  id: string;
  stem: string;
  qtype: string;
  options: Record<string, string> | null;
  difficulty: number;
  knowledge_points: string[];
}

export interface TutorSession {
  session_id: string;
  question: TutorQuestion;
  hint_level: number;
  hint_level_name: string;
  max_hint_level: number;
}

export interface TutorHint {
  session_id: string;
  level: number;
  level_name: string;
  content: string;
  next_level: number | null;
}

export interface Variant {
  question_id: string;
  stem: string;
  options: Record<string, string> | null;
  difficulty: number;
}

export interface AltSolution {
  title: string;
  steps: string[];
  scenario: string;
  answer_verified: boolean;
}

export interface AnalogyResult {
  session_id: string;
  analogy: string;
  mapping: string;
  caveat: string;
}

export interface VariantAnswerResponse {
  is_correct: boolean;
  correct_answer: string;
  back_to_tutor: { session_id?: string; reason?: string } | null;
}

export interface PracticeQuestion {
  id: string;
  stem: string;
  qtype: string;
  options: Record<string, string> | null;
  difficulty: number;
  knowledge_points: string[];
  reason: string;
}

export interface PracticeGenerate {
  count: number;
  weak_count: number;
  weak_ratio: number;
  questions: PracticeQuestion[];
}

export interface PracticeAnswer {
  is_correct: boolean;
  correct_answer: string;
  next_difficulty: number;
  mistake_collected: boolean;
  mistake_removed: boolean;
  card_due_at: string | null;
  explanation: string | null;
}

export interface QuestionBrief {
  id: string;
  stem: string;
  qtype: string;
  options: Record<string, string> | null;
  difficulty: number;
  knowledge_points: string[];
}

export interface MistakeEntry {
  id: string;
  question: QuestionBrief;
  wrong_answer: string | null;
  error_reason: string | null;
  error_reason_label: string | null;
  state: string;
  review_count: number;
  created_at: string;
}

export interface MistakeSummaryItem {
  reason: string;
  reason_label: string;
  count: number;
}

export interface MistakeList {
  active_count: number;
  mastered_count: number;
  summary: MistakeSummaryItem[];
  entries: MistakeEntry[];
}

export interface MistakeRepractice {
  count: number;
  questions: QuestionBrief[];
}

export interface ReviewCard {
  card_id: string;
  question: QuestionBrief;
  state: string;
  reps: number;
  lapses: number;
  difficulty: number;
  due_at: string | null;
}

export interface ReviewDue {
  due_count: number;
  cards: ReviewCard[];
}

export interface ReviewGrade {
  card_id: string;
  state: string;
  interval_days: number;
  due_at: string;
  reps: number;
  lapses: number;
  difficulty: number;
}

export interface WeeklyReport {
  week_start: string;
  week_end: string;
  report: Record<string, unknown>;
}

export interface ShareResult {
  token: string;
  url_path: string;
  expires_at: string;
}

export interface CalendarDay {
  day: string;
  practice_count: number;
  correct_count: number;
  tasks_total: number;
  tasks_done: number;
  studied: boolean;
}

export interface CalendarMonth {
  year: number;
  month: number;
  streak_days: number;
  max_practice: number;
  days: CalendarDay[];
}

export interface SprintPack {
  exam_date: string;
  remaining_days: number;
  high_freq_mistakes: Record<string, unknown>[];
  unmastered_knowledge_points: Record<string, unknown>[];
  predicted_paper: Record<string, unknown>[];
  generated_at: string;
}

export interface DimensionScore {
  score: number;
  max_score: number;
  comment: string;
}

export interface SubjectiveGrading {
  total_score: number;
  max_score: number;
  steps: { step: string; score: number; comment: string; lost_points: string }[];
  rewrite: string;
  summary: string;
}

export interface EssayGrading {
  total_score: number;
  max_score: number;
  rubric: string;
  structure: DimensionScore;
  ideas: DimensionScore;
  language: DimensionScore;
  paragraphs: { index: number; comment: string }[];
  upgrade_sample: string;
  summary: string;
}

export interface MicroLesson {
  lesson_id: string;
  title: string;
  status: string;
  char_count: number;
  retries: number;
  error: string | null;
}

export interface ExamQuestion {
  id: string;
  stem: string;
  qtype: string;
  options: Record<string, string> | null;
  difficulty: number;
  knowledge_points: string[];
}

export interface ExamCreate {
  exam_id: string;
  kind: string;
  title: string;
  time_limit_minutes: number;
  deadline: string | null;
  questions: ExamQuestion[];
}

export interface ExamReport {
  exam_id: string;
  kind: string;
  status: string;
  auto_submitted: boolean;
  summary: Record<string, unknown>;
  diagnoses: Record<string, unknown>[];
  submitted_at: string | null;
}

export interface SyncState {
  version: string;
  summary: {
    completed_today: number;
    total_today: number;
    streak_days: number;
    mistakes_active: number;
  };
  server_time: string;
  channel: string;
}

export interface BehaviorProfile {
  learning_style: string;
  learning_style_label: string;
  evidence: Record<string, unknown>;
  independent_score: number | null;
  assisted_score: number | null;
}

/* ---------------------------------- 端点 ---------------------------------- */

export const api = {
  // 认证
  register: (payload: { phone: string; password: string; nickname?: string }) =>
    post<TokenPair>("/v1/auth/register", { role: "student", ...payload }),
  login: (payload: { phone: string; password: string }) =>
    post<TokenPair>("/v1/auth/login", payload),
  me: () => get<UserProfile>("/v1/auth/me"),
  logout: (refreshToken: string) => post<void>("/v1/auth/logout", { refresh_token: refreshToken }),

  // 诊断与画像
  startDiagnosis: (payload: { subject: string; stage: string; target_count: number }) =>
    post<DiagnosisStart>("/v1/diagnosis/start", payload),
  answerDiagnosis: (examId: string, payload: { question_id: string; answer: string }) =>
    post<DiagnosisAnswer>(`/v1/diagnosis/${examId}/answer`, payload),
  diagnosisReport: (examId: string) => get<DiagnosisReport>(`/v1/diagnosis/${examId}/report`),
  mastery: (subject?: string) =>
    get<MasteryOverview>(`/v1/profile/mastery${subject ? `?subject=${subject}` : ""}`),
  behavior: () => get<BehaviorProfile>("/v1/profile/behavior"),

  // 规划
  path: (subject?: string) => get<PathResponse>(`/v1/plan/path${subject ? `?subject=${subject}` : ""}`),
  regeneratePath: () => post<PathResponse>("/v1/plan/path/regenerate"),
  today: () => get<TodayResponse>("/v1/plan/today"),
  completeTask: (taskId: string) => post<CompleteTaskResponse>(`/v1/plan/tasks/${taskId}/complete`),
  examCountdown: (payload: { exam_date: string; target_score?: number }) =>
    post<ExamCountdown>("/v1/plan/exam-countdown", payload),

  // 讲解
  createTutorSession: (questionId: string) =>
    post<TutorSession>("/v1/tutor/session", { question_id: questionId }),
  tutorHint: (sessionId: string, level?: number) =>
    post<TutorHint>(`/v1/tutor/${sessionId}/hint`, level === undefined ? {} : { level }),
  tutorVariants: (sessionId: string) =>
    post<{ session_id: string; variants: Variant[] }>(`/v1/tutor/${sessionId}/variants`),
  answerVariant: (sessionId: string, variantId: string, answer: string) =>
    post<VariantAnswerResponse>(`/v1/tutor/${sessionId}/variants/${variantId}/answer`, { answer }),
  tutorAnalogy: (sessionId: string) =>
    post<AnalogyResult>(`/v1/tutor/${sessionId}/analogy`),
  tutorAltSolutions: (sessionId: string) =>
    post<{ session_id: string; solutions: AltSolution[]; checked_count: number; verified_count: number }>(
      `/v1/tutor/${sessionId}/alt-solutions`,
    ),

  // 练习与错题
  generatePractice: (payload: { subject: string; count: number; knowledge_point_ids?: string[] }) =>
    post<PracticeGenerate>("/v1/practice/generate", payload),
  answerPractice: (payload: { question_id: string; answer: string; source: string }) =>
    post<PracticeAnswer>("/v1/practice/answer", payload),
  mistakes: (params?: { state?: string; error_reason?: string; limit?: number }) => {
    const query = new URLSearchParams();
    if (params?.state) query.set("state", params.state);
    if (params?.error_reason) query.set("error_reason", params.error_reason);
    if (params?.limit) query.set("limit", String(params.limit));
    const suffix = query.toString() ? `?${query.toString()}` : "";
    return get<MistakeList>(`/v1/mistakes${suffix}`);
  },
  repractice: (payload: { count?: number; error_reason?: string } = {}) =>
    post<MistakeRepractice>("/v1/mistakes/repractice", payload),

  // 复习（FSRS）
  reviewDue: (limit = 10) => get<ReviewDue>(`/v1/review/due?limit=${limit}`),
  reviewGrade: (cardId: string, grade: number) =>
    post<ReviewGrade>(`/v1/review/${cardId}/grade`, { grade }),

  // 模考（F-20）
  createExam: (payload: {
    subject: string;
    count: number;
    time_limit_minutes?: number;
    title?: string;
  }) => post<ExamCreate>("/v1/exams", payload),
  getExam: (examId: string) => get<ExamReport>(`/v1/exams/${examId}`),
  submitExam: (examId: string, answers: { question_id: string; answer: string }[]) =>
    post<ExamReport>(`/v1/exams/${examId}/submit`, { answers }),

  // 复盘
  weeklyReport: () => get<WeeklyReport>("/v1/reports/weekly"),
  shareWeekly: () => post<ShareResult>("/v1/reports/weekly/share"),
  revokeShare: (token: string) => del<void>(`/v1/reports/shares/${token}`),
  calendar: (year: number, month: number) =>
    get<CalendarMonth>(`/v1/stats/calendar?year=${year}&month=${month}`),
  sprint: () => get<SprintPack>("/v1/exam-prep/sprint"),

  // 批改
  gradeSubjective: (payload: {
    question_id?: string;
    stem?: string;
    criteria?: string;
    student_answer: string;
  }) => post<SubjectiveGrading>("/v1/grading/subjective", payload),
  gradeEssay: (payload: { rubric: string; content: string; prompt?: string }) =>
    post<EssayGrading>("/v1/grading/essay", payload),
  objectiveGrading: (payload: { question_id: string; answer: string }) =>
    post<{ is_correct: boolean; correct_answer: string; analysis: string | null }>(
      "/v1/grading/objective",
      payload,
    ),

  // 微课（工具）
  createMicroLesson: (knowledgePointId: string) =>
    post<MicroLesson>("/v1/micro-lessons", { knowledge_point_id: knowledgePointId }),
  microLessonAudio: (lessonId: string) =>
    get<{ lesson_id: string; url: string; mime: string; expires_in: number }>(
      `/v1/micro-lessons/${lessonId}/audio`,
    ),

  // 多端同步（F-39）
  syncState: () =>
    get<{
      version: string;
      summary: {
        completed_today: number;
        total_today: number;
        streak_days: number;
        mistakes_active: number;
      };
      server_time: string;
      channel: string;
    }>("/v1/sync/state"),

  // 防沉迷（F-40：服务端判定）
  guardianStatus: () =>
    get<{
      locked: boolean;
      reasons: string[];
      used_minutes: number;
      limit_minutes: number | null;
      suggest_break: boolean;
      curfew_active: boolean;
      available_from: string | null;
    }>("/v1/guardian/status"),

  // 订阅
  subscription: () => get<SubscriptionState>("/v1/billing/subscription"),
  startTrial: () => post<SubscriptionState>("/v1/billing/trial"),
};

/* ------------------------------ SSE 流式提示 ------------------------------ */

export interface StreamHandlers {
  onStart?: (payload: { level: number; level_name: string }) => void;
  onDelta?: (content: string) => void;
  onDone?: (payload: { level: number; level_name: string; content: string }) => void;
}

export async function streamTutorHint(
  sessionId: string,
  level: number | undefined,
  handlers: StreamHandlers,
): Promise<void> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  const response = await fetch(`${API_BASE_URL}/v1/tutor/${sessionId}/hint/stream`, {
    method: "POST",
    headers,
    body: JSON.stringify(level === undefined ? {} : { level }),
  });
  if (!response.ok || !response.body) {
    const body = parseBody(await response.text());
    throw new ApiError(response.status, (body ?? {}) as ApiErrorBody);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
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

  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let index = buffer.indexOf("\n\n");
    while (index >= 0) {
      const block = buffer.slice(0, index);
      buffer = buffer.slice(index + 2);
      if (block.trim()) handleBlock(block);
      index = buffer.indexOf("\n\n");
    }
  }
  if (buffer.trim()) handleBlock(buffer);
  if (!sawDone) {
    throw new ApiError(503, {
      code: "LLM_STREAM_INTERRUPTED",
      message: "讲解流式输出中断，请重试。",
    });
  }
}

/* ------------------------------ M8 V3 能力 ------------------------------ */

export interface CoachTurn {
  session_id: string;
  scene: string;
  reply: string;
  corrections: { original: string; suggestion: string; note: string }[];
  followups: string[];
  crisis: boolean;
  crisis_resources: string[];
}

export interface WritingAssist {
  suggestions: string[];
  annotations: { excerpt: string; issue: string; suggestion: string }[];
  polished_excerpt: string;
  integrity_notice: string;
}

export interface LibraryDoc {
  id: string;
  title: string;
  page_count: number;
  chunk_count: number;
  status: string;
}

export interface LibraryAsk {
  answer: string;
  citations: { page: number; chunk_id: string; excerpt: string }[];
}

export interface KnowledgeCardItem {
  id: string;
  front: string;
  back: string;
  tags: string[];
}

export interface JudgeOutcome {
  verdict: string;
  passed: number;
  total: number;
  results: { index: number; passed: boolean; status: string; stdout: string; expected: string; stderr: string }[];
  feedback: Record<string, string[]>;
  blocked_reason: string | null;
}

export interface PhotoSearchResult {
  recognized_text: string;
  confidence: number;
  degraded: boolean;
  degradation_hint: string | null;
  match_found: boolean;
  question_id: string | null;
  tutor_entry: string;
  knowledge_points: string[];
}

export interface HandwritingResult {
  steps: { index: number; content: string; is_error: boolean; note: string }[];
  first_error_step: number | null;
  confidence: number;
  degraded: boolean;
  degradation_hint: string | null;
  advice: string;
}

export const coachApi = {
  scenes: () => get<{ key: string; title: string; opening: string; focus: string[] }[]>("/v1/coach/scenes"),
  companion: (payload: { message: string; session_id?: string | null }) =>
    post<CoachTurn>("/v1/coach/companion", payload),
  roleplay: (payload: { message: string; scene: string; session_id?: string | null }) =>
    post<CoachTurn>("/v1/coach/roleplay", payload),
  interview: (payload: { message: string; session_id?: string | null }) =>
    post<CoachTurn>("/v1/coach/interview", payload),
  writing: (payload: { kind: string; text: string }) =>
    post<WritingAssist>("/v1/coach/writing", payload),
};

export const v3Api = {
  photoSearch: (payload: { ocr_text: string; subject?: string; image_key?: string }) =>
    post<PhotoSearchResult>("/v1/tools/photo-search", payload),
  handwriting: (payload: { ocr_text: string; reference_solution: string }) =>
    post<HandwritingResult>("/v1/diagnosis/handwriting", payload),
  libraryList: () => get<LibraryDoc[]>("/v1/library/docs"),
  libraryAsk: (documentId: string, question: string) =>
    post<LibraryAsk>(`/v1/library/${documentId}/ask`, { question, top_k: 3 }),
  librarySelfTest: (documentId: string) =>
    get<{ questions: { question: string; answer: string; page: number }[] }>(
      `/v1/library/${documentId}/self-test`,
    ),
  cards: () => get<{ cards: KnowledgeCardItem[]; total: number }>("/v1/cards"),
  createCard: (payload: { front: string; back: string; tags: string[] }) =>
    post<KnowledgeCardItem>("/v1/cards", { ...payload, source_type: "manual" }),
  exportCards: async (): Promise<Blob> => {
    const headers: Record<string, string> = {};
    const token = getAccessToken();
    if (token) headers.Authorization = `Bearer ${token}`;
    const response = await fetch(`${API_BASE_URL}/v1/cards/export.apkg`, { headers });
    if (!response.ok) throw new ApiError(response.status, (await response.json()) as ApiErrorBody);
    return response.blob();
  },
  judge: (payload: { code: string; tests: { input: string; expected: string }[] }) =>
    post<JudgeOutcome>("/v1/grading/code", { language: "python", ...payload }),
};
