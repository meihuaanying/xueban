/**
 * Lighthouse CI 配置（M4 / T4.2）。
 * 使用 `next start` 提供生产构建，首页四项指标全部作为错误级断言。
 * 本机无 Chrome 时：`CHROME_PATH` 指向 Edge 可执行文件即可运行。
 *
 * 端口：Next 默认 3000 常被本机其他服务抢占，会导致本配置去测别人的站点。
 * 与 apps/web/playwright.config.ts 保持同一套约定，Windows 下默认 3100。
 */
const isWindows = process.platform === "win32";
const webPort = process.env.PLAYWRIGHT_WEB_PORT ?? process.env.PORT ?? (isWindows ? "3100" : "3000");

// startServerCommand 启动的是 `next start`，只认 PORT 环境变量；不注入就会落回
// Next 默认 3000，与 collect.url 不一致（在 3000 被其他服务占用的机器上直接
// EADDRINUSE 启动失败）。lhci 派生子进程时继承本进程 env，故在此统一设置，
// 无需引入 cross-env。CI（Linux）上 webPort 即 3000，行为与原先一致。
process.env.PORT = webPort;

module.exports = {
  ci: {
    collect: {
      url: ["http://127.0.0.1:" + webPort + "/"],
      // 默认移动端仿真（Lighthouse 标准口径）；3 次取中位数，降低单次抖动。
      numberOfRuns: 3,
      startServerCommand: "pnpm --filter @xueban/web start",
      startServerReadyPattern: "Local:",
      startServerReadyTimeout: 120000,
      settings: {
        // 必须传空格拼接的字符串：lhci 的 node-runner 直接把 settings.chromeFlags
        // 当字符串用（`chromeFlagsAsString += ' --headless=new'`），传数组会被
        // toString() 用逗号连成一个无效 flag。
        chromeFlags: "--no-sandbox --disable-gpu --disable-crash-reporter --disable-breakpad",
      },
    },
    assert: {
      assertions: {
        "categories:performance": ["error", { minScore: 0.9 }],
        "categories:accessibility": ["error", { minScore: 0.95 }],
        "categories:best-practices": ["error", { minScore: 0.95 }],
        "categories:seo": ["error", { minScore: 0.95 }],
      },
    },
    upload: {
      target: "filesystem",
      outputDir: "./.lighthouseci",
    },
  },
};
