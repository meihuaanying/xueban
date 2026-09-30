import type { Story } from "@ladle/react";

import { currentTheme } from "../src/stories/design/theme-params";
import "../src/styles.css";

/**
 * Ladle 全局容器：令牌驱动的表面与文字色，并按 URL 参数挂 data-theme / data-mode。
 *
 * ⚠️ 本文件受 Ladle 5.1.1 解析器限制，只能 `export const`：
 * Ladle 用 babel AST 扫描具名导出时假设 `declaration.declarations[0].id.name`，
 * 因此 `export function` / `export type` 都会让它抛错，
 * 进而丢掉默认导出的 Provider/StorySourceHeader，页面整页报
 * “does not provide an export named 'StorySourceHeader'”。
 * 新增内容一律写成 `const`（不 export）。
 *
 * 走查地址：
 *   http://localhost:61000/?story=design-tokens--palette&theme=focus
 *   http://localhost:61000/?story=design-tokens--palette&theme=kids
 *   http://localhost:61000/?story=design-tokens--palette&theme=focus&mode=dark
 */

const THEME_LABELS: Record<string, string> = {
  focus: "focus · 少年/成人（中性灰底 + 靛蓝，高密度）",
  kids: "kids · 儿童（暖纸底 + 明黄/天蓝/草绿，大字号大圆角）",
};

export const Global: Story = ({ children }: { children?: React.ReactNode }) => {
  const { theme, mode } = currentTheme();
  return (
    <div
      data-theme={theme}
      data-mode={mode}
      className={mode === "dark" ? "dark" : undefined}
      style={{
        minHeight: "100vh",
        padding: "var(--space-md)",
        background: "var(--background)",
        color: "var(--foreground)",
        fontFamily: '"PingFang SC", "Microsoft YaHei", system-ui, sans-serif',
        fontSize: "var(--text-app)",
        lineHeight: "var(--leading-app)",
      }}
    >
      <div style={{ marginBottom: "var(--space-sm)", fontSize: 12, color: "#6b7280" }}>
        {THEME_LABELS[theme]}
        {mode === "dark" ? " · 深色" : ""}
      </div>
      {children}
    </div>
  );
};
