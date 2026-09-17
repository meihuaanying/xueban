// T10.2 核心 API 压测（非 LLM 端点）
// 规格：200 并发 × 5 分钟；p95 ≤300ms；错误率 ≤0.1%
//
// 运行（本机，API 需先在 8090 端口以 mock LLM 启动）：
//   "C:/Program Files/k6/k6.exe" run infra/k6/core_api.js \
//     -e K6_BASE_URL=http://127.0.0.1:8090
// 可选环境变量：K6_PHONE / K6_PASSWORD / K6_VUS / K6_DURATION
import http from "k6/http";
import { check, fail } from "k6";

const BASE = (__ENV.K6_BASE_URL || "http://127.0.0.1:8090").replace(/\/+$/, "");
const PHONE = __ENV.K6_PHONE || "17136015493";
const PASSWORD = __ENV.K6_PASSWORD || "load-test-123";

const VUS = Number(__ENV.K6_VUS || 200);
const DURATION = __ENV.K6_DURATION || "5m";

export const options = {
  scenarios: {
    core_api: {
      executor: "constant-vus",
      vus: VUS,
      duration: DURATION,
      gracefulStop: "30s",
      tags: { scenario: "core_api" },
    },
  },
  thresholds: {
    http_req_duration: ["p(95)<300"],
    http_req_failed: ["rate<0.001"],
    checks: ["rate>0.999"],
  },
  summaryTrendStats: ["avg", "min", "med", "p(90)", "p(95)", "p(99)", "max"],
};

const ENDPOINTS = [
  { name: "healthz", path: "/healthz", auth: false },
  { name: "mastery", path: "/v1/profile/mastery", auth: true },
  { name: "plan_today", path: "/v1/plan/today", auth: true },
  { name: "mistakes", path: "/v1/mistakes", auth: true },
  { name: "sync_state", path: "/v1/sync/state", auth: true },
];

function authHeaders(token) {
  return { headers: { Authorization: `Bearer ${token}` } };
}

export function setup() {
  const login = http.post(
    `${BASE}/v1/auth/login`,
    JSON.stringify({ phone: PHONE, password: PASSWORD }),
    { headers: { "Content-Type": "application/json" }, tags: { name: "setup_login" } },
  );
  if (login.status !== 200) {
    fail(`setup 登录失败: ${login.status} ${login.body}`);
  }
  const token = login.json("access_token");
  if (!token) {
    fail("setup 未拿到 access_token");
  }
  return { token };
}

export default function (data) {
  const ep = ENDPOINTS[Math.floor(Math.random() * ENDPOINTS.length)];
  const res = http.get(`${BASE}${ep.path}`, {
    ...(ep.auth ? authHeaders(data.token) : {}),
    tags: { name: ep.name },
  });
  check(res, {
    [`${ep.name} 2xx`]: (r) => r.status >= 200 && r.status < 300,
  });
}
