/**
 * promptfoo 自定义 provider：直连本机 XueBan API（LLM_PROVIDER=mock）。
 *
 * 用途：在无真实模型 Key（B-005）的环境下，把「红线断言可运行」纳入 CI/证据：
 * - vars.question_id    → 走 /v1/tutor/session + /{id}/hint（第 1 层），返回讲解文本；
 * - vars.crisis_message → 走 /v1/coach/companion，返回 {crisis, reply, resources} JSON 字符串。
 *
 * 环境变量：XUEBAN_API_BASE（默认 http://127.0.0.1:8096）、
 *          XUEBAN_EVAL_PHONE / XUEBAN_EVAL_PASSWORD（默认本机压测账号）。
 */
const BASE = (process.env.XUEBAN_API_BASE || "http://127.0.0.1:8096").replace(/\/+$/, "");
const PHONE = process.env.XUEBAN_EVAL_PHONE || "17136015493";
const PASSWORD = process.env.XUEBAN_EVAL_PASSWORD || "load-test-123";

let tokenPromise = null;

async function getToken() {
  if (!tokenPromise) {
    tokenPromise = (async () => {
      const res = await fetch(`${BASE}/v1/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone: PHONE, password: PASSWORD }),
      });
      if (!res.ok) {
        throw new Error(`登录失败: ${res.status} ${await res.text()}`);
      }
      return (await res.json()).access_token;
    })();
  }
  return tokenPromise;
}

async function withAuth() {
  const token = await getToken();
  return { "Content-Type": "application/json", Authorization: `Bearer ${token}` };
}

async function callTutor(vars) {
  const headers = await withAuth();
  const created = await fetch(`${BASE}/v1/tutor/session`, {
    method: "POST",
    headers,
    body: JSON.stringify({ question_id: vars.question_id }),
  });
  if (created.status !== 201) {
    throw new Error(`创建讲解会话失败: ${created.status} ${await created.text()}`);
  }
  const { session_id: sessionId } = await created.json();
  const hint = await fetch(`${BASE}/v1/tutor/${sessionId}/hint`, {
    method: "POST",
    headers,
    body: JSON.stringify({ level: 1 }),
  });
  if (!hint.ok) {
    throw new Error(`请求提示失败: ${hint.status} ${await hint.text()}`);
  }
  return (await hint.json()).content;
}

async function callCrisis(vars) {
  const headers = await withAuth();
  const res = await fetch(`${BASE}/v1/coach/companion`, {
    method: "POST",
    headers,
    body: JSON.stringify({ message: vars.crisis_message }),
  });
  if (!res.ok) {
    throw new Error(`陪伴对话失败: ${res.status} ${await res.text()}`);
  }
  const data = await res.json();
  return JSON.stringify({
    crisis: data.crisis,
    reply: data.reply,
    resources: data.crisis_resources,
  });
}

class XuebanMockApiProvider {
  id() {
    return "xueban-api-mock";
  }

  async callApi(_prompt, context) {
    const vars = context.vars || {};
    if (vars.crisis_message) {
      return { output: await callCrisis(vars) };
    }
    if (vars.question_id) {
      return { output: await callTutor(vars) };
    }
    throw new Error("用例缺少 question_id 或 crisis_message");
  }
}

module.exports = XuebanMockApiProvider;
