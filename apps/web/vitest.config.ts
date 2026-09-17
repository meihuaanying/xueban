import { fileURLToPath } from "node:url";

import { defineConfig } from "vitest/config";

export default defineConfig({
  // Next 构建会把 tsconfig 的 jsx 改为 preserve（由 Next 自己完成转换），
  // 测试环境需显式使用 automatic 运行时，否则报 "React is not defined"。
  esbuild: {
    jsx: "automatic",
  },
  test: {
    environment: "jsdom",
    include: ["tests/**/*.test.{ts,tsx}"],
    setupFiles: ["./tests/setup.ts"],
    coverage: {
      provider: "v8",
      reporter: ["text"],
      include: ["src/lib/**/*.ts", "src/components/**/*.tsx"],
      exclude: ["src/**/*.test.{ts,tsx}"],
      thresholds: {
        lines: 80,
        statements: 80,
      },
    },
  },
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
});
