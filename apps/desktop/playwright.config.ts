import path from "node:path";
import { fileURLToPath } from "node:url";

import { defineConfig, devices } from "@playwright/test";

// apps/desktop 为 ESM（package.json type=module），配置文件同样以 ESM 加载。
const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const apiDir = path.join(rootDir, "services", "api");
const isWindows = process.platform === "win32";

// 本机无 Chrome，仅有 Edge：Windows 下走 msedge 通道；CI 安装 chromium 后不指定通道。
const channel = process.env.PLAYWRIGHT_CHANNEL ?? (isWindows ? "msedge" : undefined);

// API 端口：Windows 本机 8000 落在 Hyper-V 保留端口段（7930-8029）无法监听；
// 桌面 E2E 固定用 8091，与官网 E2E（8090）隔离，避免复用未启用 mock LLM 的实例。
const apiPort = process.env.PLAYWRIGHT_API_PORT ?? (isWindows ? "8091" : "8000");
const apiOrigin = `http://127.0.0.1:${apiPort}`;

// 后端解释器：默认取仓库虚拟环境；CI 无 .venv，通过 PLAYWRIGHT_PYTHON=python 覆盖。
const apiPython =
  process.env.PLAYWRIGHT_PYTHON ??
  (isWindows
    ? path.join(apiDir, ".venv", "Scripts", "python")
    : path.join(apiDir, ".venv", "bin", "python"));

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  // 桌面端用例较长且共享 API：本地也保留 1 次重试，降低系统负载抖动带来的假失败。
  retries: 1,
  workers: process.env.CI ? 1 : 4,
  reporter: [
    ["list"],
    ["html", { open: "never", outputFolder: "playwright-report" }],
  ],
  outputDir: "test-results",
  timeout: 180_000,
  expect: { timeout: 20_000 },
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:4173",
    ...(channel ? { channel } : {}),
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    locale: "zh-CN",
    timezoneId: "Asia/Shanghai",
  },
  projects: [
    {
      name: "desktop",
      use: { ...devices["Desktop Chrome"], ...(channel ? { channel } : {}) },
    },
  ],
  // 桌面端 E2E：Vite 生产构建预览（4173） + 本机 API（8090/8000，LLM 走 mock 保证确定性）。
  webServer: [
    {
      command: "pnpm --filter @xueban/desktop preview",
      url: "http://127.0.0.1:4173",
      cwd: rootDir,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
    {
      command: `"${apiPython}" -m uvicorn app.main:app --port ${apiPort}`,
      url: `${apiOrigin}/healthz`,
      cwd: apiDir,
      env: { LLM_PROVIDER: "mock" },
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
  ],
});
