import js from "@eslint/js";
import globals from "globals";
import tseslint from "typescript-eslint";

const GLOBAL_IGNORES = {
  ignores: [
    "**/node_modules/**",
    "**/dist/**",
    "**/build/**",
    "**/.next/**",
    "**/.expo/**",
    "**/.turbo/**",
    "**/coverage/**",
    "**/src-tauri/target/**",
    "**/next-env.d.ts",
    "**/*.config.js",
    "**/*.config.cjs",
    "**/*.config.mjs",
  ],
};

/**
 * 通用 ESLint flat config（TypeScript / Node 环境）。
 * 各包按需再传入额外的扁平配置对象。
 */
export default function base(...extra) {
  return tseslint.config(
    GLOBAL_IGNORES,
    js.configs.recommended,
    ...tseslint.configs.recommended,
    {
      languageOptions: {
        globals: { ...globals.node },
      },
      rules: {
        "@typescript-eslint/no-unused-vars": [
          "error",
          { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
        ],
      },
    },
    ...extra,
  );
}
