/** 浏览器/服务端共用的 API 请求工具（错误契约：code/message/trace_id）。 */

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

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

function parseBody(text: string): unknown {
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

export async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init.headers ?? {}),
    },
  });
  const body = parseBody(await response.text());
  if (!response.ok) {
    throw new ApiError(response.status, (body ?? {}) as ApiErrorBody);
  }
  return body as T;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface SubscriptionState {
  plan: string;
  started_at: string | null;
  expires_at: string | null;
  trial_used: boolean;
  auto_renew: boolean;
}

export interface Plan {
  cycle: string;
  title: string;
  price_cents: number;
  days: number;
}

export function registerAccount(payload: {
  phone: string;
  password: string;
  nickname?: string;
  is_k12?: boolean;
  role?: "student" | "parent";
}): Promise<TokenPair> {
  const { role = "student", ...rest } = payload;
  return apiRequest<TokenPair>("/v1/auth/register", {
    method: "POST",
    body: JSON.stringify({ ...rest, role }),
  });
}

export function startTrial(accessToken: string): Promise<SubscriptionState> {
  return apiRequest<SubscriptionState>("/v1/billing/trial", {
    method: "POST",
    headers: { Authorization: `Bearer ${accessToken}` },
  });
}

export function fetchSubscription(accessToken: string): Promise<SubscriptionState> {
  return apiRequest<SubscriptionState>("/v1/billing/subscription", {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
}

export function fetchPlans(): Promise<Plan[]> {
  return apiRequest<Plan[]>("/v1/billing/plans");
}

/* ------------------------------ 家长端 / 后台 ------------------------------ */

export interface ChildInfo {
  id: string;
  phone: string;
  nickname: string | null;
}

export interface ParentDashboard {
  child_id: string;
  child_nickname: string | null;
  mastery: {
    red_count: number;
    yellow_count: number;
    green_count: number;
    average_mastery: number | null;
    points: { knowledge_point_id: string; mastery: number }[];
  };
  streak_days: number;
  practice_7d: number;
  task_completion_7d: number;
  mistakes_active: number;
  behavior_style: string | null;
  generated_at: string;
}

export interface ParentControls {
  child_id: string;
  is_enabled: boolean;
  daily_limit_minutes: number;
  allowed_start: string | null;
  allowed_end: string | null;
  rest_after_minutes: number;
}

export interface SafetyReport {
  week_start: string;
  week_end: string;
  blocked_count: number;
  total_events: number;
  events: { id: string; scene: string; action: string; snippet: string | null; created_at: string }[];
  traces: { id: string; role: string; hint_level: number | null; excerpt: string }[];
  trace_total: number;
}

export interface ParentTask {
  id: string;
  child_id: string;
  title: string;
  description: string | null;
  status: string;
  source: string;
  due_date: string | null;
}

function authHeaders(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}` };
}

export const parentApi = {
  me: (token: string) =>
    apiRequest<{ id: string; phone: string; nickname: string | null; role: string }>("/v1/auth/me", {
      headers: authHeaders(token),
    }),
  children: (token: string) =>
    apiRequest<ChildInfo[]>("/v1/auth/parents/children", { headers: authHeaders(token) }),
  bindChild: (token: string, childPhone: string) =>
    apiRequest<ChildInfo>("/v1/auth/parents/children", {
      method: "POST",
      headers: authHeaders(token),
      body: JSON.stringify({ child_phone: childPhone }),
    }),
  dashboard: (token: string, childId: string) =>
    apiRequest<ParentDashboard>(`/v1/parents/children/${childId}/dashboard`, {
      headers: authHeaders(token),
    }),
  controls: (token: string, childId: string) =>
    apiRequest<ParentControls>(`/v1/parents/children/${childId}/controls`, {
      headers: authHeaders(token),
    }),
  updateControls: (
    token: string,
    payload: {
      child_id: string;
      parent_password: string;
      is_enabled: boolean;
      daily_limit_minutes: number;
      allowed_start?: string | null;
      allowed_end?: string | null;
      rest_after_minutes: number;
    },
  ) =>
    apiRequest<ParentControls>("/v1/parents/controls", {
      method: "PUT",
      headers: authHeaders(token),
      body: JSON.stringify(payload),
    }),
  safety: (token: string, childId: string) =>
    apiRequest<SafetyReport>(`/v1/parents/children/${childId}/safety`, {
      headers: authHeaders(token),
    }),
  tasks: (token: string, childId: string) =>
    apiRequest<{ tasks: ParentTask[] }>(`/v1/parents/tasks?child_id=${childId}`, {
      headers: authHeaders(token),
    }),
  confirmTask: (token: string, taskId: string) =>
    apiRequest<ParentTask>(`/v1/parents/tasks/${taskId}/confirm`, {
      method: "POST",
      headers: authHeaders(token),
    }),
  createLink: (token: string, childId: string) =>
    apiRequest<{ token: string; url_path: string; expires_at: string }>(
      `/v1/parents/dashboard/links?child_id=${childId}`,
      { method: "POST", headers: authHeaders(token) },
    ),
  revokeLink: (token: string, shareToken: string) =>
    apiRequest<null>(`/v1/parents/dashboard/links/${shareToken}`, {
      method: "DELETE",
      headers: authHeaders(token),
    }),
  sharedDashboard: (shareToken: string) =>
    apiRequest<ParentDashboard>(`/v1/parents/dashboard/${shareToken}`, {}),
};

export interface Coverage {
  total: number;
  with_analysis: number;
  coverage_rate: number;
  published: number;
  draft: number;
  review: number;
  by_subject: { subject: string; total: number; with_analysis: number; coverage_rate: number }[];
}

export interface AdminQuestion {
  id: string;
  subject: string;
  stage: string;
  qtype: string;
  stem: string;
  answer: string;
  analysis: string | null;
  status: string;
  difficulty: number;
}

export interface InspectionReport {
  id: string;
  run_date: string;
  sample_size: number;
  flagged_count: number;
  wrong_rate: number;
  redline_hits: number;
  alerted: boolean;
}

export interface MetricsOverview {
  users_total: number;
  users_active_7d: number;
  retention_d1: number;
  retention_d7: number;
  task_completion_rate_7d: number;
  renewal_rate: number;
  mastery_improvement: number;
}

export interface ExperimentReport {
  experiment_id: string;
  key: string;
  metric: string;
  total_participants: number;
  conclusion: string;
  variants: {
    name: string;
    participants: number;
    successes: number;
    conversion_rate: number;
    p_value: number | null;
    significant: boolean;
  }[];
}

export const adminApi = {
  me: (token: string) =>
    apiRequest<{ id: string; role: string; phone: string }>("/v1/auth/me", {
      headers: authHeaders(token),
    }),
  login: (phone: string, password: string) =>
    apiRequest<{ access_token: string }>("/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ phone, password }),
    }),
  questions: (token: string, params?: { status?: string; keyword?: string }) => {
    const query = new URLSearchParams();
    if (params?.status) query.set("status", params.status);
    if (params?.keyword) query.set("keyword", params.keyword);
    query.set("page_size", "20");
    return apiRequest<{ total: number; items: AdminQuestion[] }>(
      `/v1/admin/questions?${query.toString()}`,
      { headers: authHeaders(token) },
    );
  },
  coverage: (token: string) =>
    apiRequest<Coverage>("/v1/admin/questions/coverage", { headers: authHeaders(token) }),
  createQuestion: (
    token: string,
    payload: { subject: string; stem: string; answer: string; analysis: string; difficulty?: number },
  ) =>
    apiRequest<AdminQuestion>("/v1/admin/questions", {
      method: "POST",
      headers: authHeaders(token),
      body: JSON.stringify({ qtype: "choice", options: { A: payload.answer, B: "占位" }, ...payload }),
    }),
  transition: (token: string, questionId: string, target: string) =>
    apiRequest<AdminQuestion>(`/v1/admin/questions/${questionId}/transition`, {
      method: "POST",
      headers: authHeaders(token),
      body: JSON.stringify({ target }),
    }),
  versions: (token: string, questionId: string) =>
    apiRequest<{ version: number; change_note: string | null }[]>(
      `/v1/admin/questions/${questionId}/versions`,
      { headers: authHeaders(token) },
    ),
  inspect: (token: string, sampleSize = 50) =>
    apiRequest<InspectionReport>("/v1/admin/quality/inspect", {
      method: "POST",
      headers: authHeaders(token),
      body: JSON.stringify({ sample_size: sampleSize, threshold: 0.03 }),
    }),
  inspectionReports: (token: string) =>
    apiRequest<InspectionReport[]>("/v1/admin/quality/reports", { headers: authHeaders(token) }),
  metrics: (token: string) =>
    apiRequest<MetricsOverview>("/v1/admin/metrics/overview", { headers: authHeaders(token) }),
  experiments: (token: string) =>
    apiRequest<{ id: string; key: string; name: string; status: string }[]>("/v1/admin/experiments", {
      headers: authHeaders(token),
    }),
  createExperiment: (
    token: string,
    payload: { key: string; name: string; variants: { name: string; weight: number }[] },
  ) =>
    apiRequest<{ id: string; key: string }>("/v1/admin/experiments", {
      method: "POST",
      headers: authHeaders(token),
      body: JSON.stringify({ ...payload, metric: "accuracy" }),
    }),
  experimentReport: (token: string, experimentId: string) =>
    apiRequest<ExperimentReport>(`/v1/admin/experiments/${experimentId}/report`, {
      headers: authHeaders(token),
    }),
};

