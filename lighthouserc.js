/**
 * Lighthouse CI 配置（M4 / T4.2）。
 * 使用 `next start` 提供生产构建，首页四项指标全部作为错误级断言。
 * 本机无 Chrome 时：`CHROME_PATH` 指向 Edge 可执行文件即可运行。
 */
module.exports = {
  ci: {
    collect: {
      url: ["http://localhost:3000/"],
      // 默认移动端仿真（Lighthouse 标准口径）；3 次取中位数，降低单次抖动。
      numberOfRuns: 3,
      startServerCommand: "pnpm --filter @xueban/web start",
      startServerReadyPattern: "Local:",
      startServerReadyTimeout: 120000,
      settings: {
        // Windows 下关闭 crashpad，避免 chrome-launcher 清理临时目录时 EPERM（不影响指标口径）
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
