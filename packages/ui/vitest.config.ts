import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.{ts,tsx}"],
    setupFiles: ["./src/test/setup.ts"],
    coverage: {
      provider: "v8",
      reporter: ["text"],
      include: ["src/**/*.{ts,tsx}"],
      exclude: ["src/**/*.test.{ts,tsx}", "src/stories/**", "src/test/**"],
      thresholds: {
        // 规格书 §7/T10.1：packages ≥85%
        lines: 85,
        statements: 85,
      },
    },
  },
});
