// T10.2 LLM 流式首 token 压测（记录实测，门禁 p95 ≤3s）
// 注意：本机无真实模型 Key（B-003/B-005），当前以 LLM_PROVIDER=mock 记录测法与基线；
// Key 到位后同脚本直连真实模型复测即可。
//
// 运行：
//   "C:/Program Files/k6/k6.exe" run infra/k6/llm_stream.js \
//     -e K6_BASE_URL=http://127.0.0.1:8090 -e K6_QUESTION_ID=<uuid>
import http from "k6/http";
import { check, fail } from "k6";

const BASE = (__ENV.K6_BASE_URL || "http://127.0.0.1:8090").replace(/\/+$/, "");
const PHONE = __ENV.K6_PHONE || "17136015493";
const PASSWORD = __ENV.K6_PASSWORD || "load-test-123";

const VUS = Number(__ENV.K6_VUS || 20);
const DURATION = __ENV.K6_DURATION || "2m";

export const options = {
  scenarios: {
    llm_stream: {
      executor: "constant-vus",
      vus: VUS,
      duration: DURATION,
      gracefulStop: "30s",
      tags: { scenario: "llm_stream" },
    },
  },
  thresholds: {
    // http_req_waiting 即首字节时延（SSE 首 token 的近似）
    http_req_waiting: ["p(95)<3000"],
    http_req_failed: ["rate<0.01"],
  },
  summaryTrendStats: ["avg", "min", "med", "p(90)", "p(95)", "p(99)", "max"],
};

function jsonAuth(token) {
  return {
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
  };
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

  let questionId = __ENV.K6_QUESTION_ID || null;
  if (!questionId) {
    const today = http.get(`${BASE}/v1/plan/today`, {
      headers: { Authorization: `Bearer ${token}` },
      tags: { name: "setup_today" },
    });
    if (today.status === 200) {
      const tasks = today.json("tasks") || [];
      const q = tasks.find((t) => t.ref_type === "question" && t.ref_id);
      if (q) {
        questionId = q.ref_id;
      }
    }
  }
  if (!questionId) {
    fail("缺少 K6_QUESTION_ID 且今日任务无题目引用");
  }
  return { token, questionId };
}

export default function (data) {
  const created = http.post(
    `${BASE}/v1/tutor/session`,
    JSON.stringify({ question_id: data.questionId }),
    { ...jsonAuth(data.token), tags: { name: "tutor_session" } },
  );
  if (created.status !== 201) {
    check(created, { "创建讲解会话 201": (r) => r.status === 201 });
    return;
  }
  const sessionId = created.json("session_id");
  const stream = http.post(
    `${BASE}/v1/tutor/${sessionId}/hint/stream`,
    JSON.stringify({ level: 1 }),
    {
      headers: { Authorization: `Bearer ${data.token}`, "Content-Type": "application/json" },
      tags: { name: "hint_stream" },
      timeout: "60s",
    },
  );
  check(stream, {
    "SSE 200": (r) => r.status === 200,
    "SSE 含 done 事件": (r) => String(r.body).includes("event: done"),
  });
}
