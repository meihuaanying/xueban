import path from "node:path";

import { defineConfig, devices } from "@playwright/test";

// 配置文件以 CJS 加载（apps/web 无 "type":"module"），使用 __dirname 定位仓库根目录。
const rootDir = path.resolve(__dirname, "../..");
const apiDir = path.join(rootDir, "services", "api");
const isWindows = process.platform === "win32";

// 本机无 Chrome，仅有 Edge：Windows 下走 msedge 通道；CI 安装 chromium 后不指定通道。
const channel = process.env.PLAYWRIGHT_CHANNEL ?? (isWindows ? "msedge" : undefined);

// API 端口：Windows 本机 8000 落在 Hyper-V 保留端口段（7930-8029）无法监听，改用 8090。
const apiPort = process.env.PLAYWRIGHT_API_PORT ?? (isWindows ? "8090" : "8000");
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
  // 本地同样保留 1 次重试并限制并发：预览服务器在 24 条用例并发下偶发 ERR_ABORTED
  retries: 1,
  workers: process.env.CI ? 1 : 4,
  reporter: [["list"], ["html", { open: "never", outputFolder: "playwright-report" }]],
  outputDir: "test-results",
  timeout: 90_000,
  expect: { timeout: 15_000 },
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3000",
    ...(channel ? { channel } : {}),
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    locale: "zh-CN",
    timezoneId: "Asia/Shanghai",
  },
  projects: [
    {
      name: "web",
      use: { ...devices["Desktop Chrome"], ...(channel ? { channel } : {}) },
    },
  ],
  // 官网 E2E 依赖本机 API（需 PostgreSQL 已启动且已迁移）与 Next 生产服务器。
  // 注意：使用 `next start`（而非 `next dev`），E2E 直接验证构建产物，
  // 且不会像 dev 模式那样清空 .next 导致后续 lhci 无法启动。
  // 构建时请确保 NEXT_PUBLIC_API_BASE_URL 指向 E2E 的 API 端口（默认 8000）。
  webServer: [
    {
      command: "pnpm --filter @xueban/web start",
      url: "http://127.0.0.1:3000",
      cwd: rootDir,
      env: { NEXT_PUBLIC_API_BASE_URL: apiOrigin },
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
    {
      command: `"${apiPython}" -m uvicorn app.main:app --port ${apiPort}`,
      url: `${apiOrigin}/healthz`,
      cwd: apiDir,
      env: {
        LLM_PROVIDER: "mock",
        // 开发/CI 环境按配置创建管理员（M7 后台 E2E 登录用）
        DEV_ADMIN_PHONE: process.env.E2E_ADMIN_PHONE ?? "13900000000",
        DEV_ADMIN_PASSWORD: process.env.E2E_ADMIN_PASSWORD ?? "admin-dev-123",
      },
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
  ],
});
