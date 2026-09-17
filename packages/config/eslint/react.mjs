import reactHooks from "eslint-plugin-react-hooks";
import globals from "globals";

import base from "./base.mjs";

/**
 * React 应用/组件库的 ESLint flat config 工厂。
 */
export default function react(...extra) {
  return base(
    {
      files: ["**/*.{ts,tsx,jsx}"],
      languageOptions: {
        globals: { ...globals.browser },
      },
      plugins: {
        "react-hooks": reactHooks,
      },
      rules: {
        "react-hooks/rules-of-hooks": "error",
        "react-hooks/exhaustive-deps": "warn",
      },
    },
    ...extra,
  );
}
