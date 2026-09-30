/**
 * 设计稿走查框架（Ladle）
 * 同一 story 内并排渲染 focus / kids 两套主题容器，一张截图即可对比双主题。
 * 注意：本文件仅用于 P0 设计评审，评审放行后其中的示意块将替换为 packages/ui 正式组件。
 */
import type { ReactNode } from "react";

import { currentTheme } from "./theme-params";

export const THEME_LABELS: Record<string, string> = {
  focus: "focus · 少年/成人（中性灰 + 靛蓝，高密度）",
  kids: "kids · 儿童（暖纸底 + 明黄/天蓝/草绿，大字号大圆角）",
};

function ThemeBox({
  theme,
  mode,
  children,
  width,
}: {
  theme: "focus" | "kids";
  mode?: "light" | "dark";
  children: ReactNode;
  width?: number;
}) {
  return (
    <div style={{ width, flex: "0 0 auto" }}>
      <div
        style={{
          fontSize: 12,
          color: "#6b7280",
          marginBottom: 6,
          fontFamily: "system-ui, sans-serif",
        }}
      >
        {THEME_LABELS[theme]}
        {mode === "dark" ? " · 深色" : ""}
      </div>
      <div
        data-theme={theme}
        data-mode={mode ?? "light"}
        className={mode === "dark" ? "dark" : undefined}
        style={{
          background: "var(--background)",
          color: "var(--foreground)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius-card)",
          padding: "var(--space-md)",
          fontFamily: '"PingFang SC", "Microsoft YaHei", system-ui, sans-serif',
          fontSize: "var(--text-app)",
          lineHeight: "var(--leading-app)",
          boxShadow: "var(--shadow-card)",
        }}
      >
        {children}
      </div>
    </div>
  );
}

/** 读取走查参数（对 Ladle 全屏重写 URL 免疫，见 theme-params.ts） */
export { currentTheme, readParam } from "./theme-params";

/** 像素标注：走查证据要求「差异肉眼可辨或直接标注像素值」 */
export function Px({ children }: { children: ReactNode }) {
  return (
    <span
      style={{
        fontSize: 11,
        fontWeight: 600,
        color: "var(--muted-foreground)",
        border: "1px solid var(--border-strong)",
        borderRadius: "var(--radius-sm)",
        padding: "1px 5px",
        whiteSpace: "nowrap",
      }}
    >
      {children}
    </span>
  );
}

/** 双主题并排容器 */
export function ThemePair({
  children,
  width = 560,
  gap = "var(--space-lg)",
}: {
  children: (theme: "focus" | "kids") => ReactNode;
  width?: number;
  gap?: string;
}) {
  const { theme, mode } = currentTheme();
  // kids 恒亮色（§4 无深色）；focus 跟随 ?mode=dark
  return (
    <div style={{ display: "flex", gap, alignItems: "flex-start", flexWrap: "wrap" }}>
      <ThemeBox theme="focus" mode={theme === "focus" ? mode : "light"} width={width}>
        {children("focus")}
      </ThemeBox>
      <ThemeBox theme="kids" mode="light" width={width}>
        {children("kids")}
      </ThemeBox>
    </div>
  );
}

/** 区块标题 */
export function Row({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <section style={{ marginBottom: "var(--space-md)" }}>
      <h3
        style={{
          fontSize: "var(--text-app-md)",
          fontWeight: 600,
          margin: "0 0 var(--space-xs)",
          color: "var(--foreground)",
        }}
      >
        {title}
      </h3>
      {children}
    </section>
  );
}

/** 色卡：色块在上、名称在下，保证浅色块上的文字始终可读 */
export function Swatches({ items }: { items: { name: string; varName: string }[] }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "var(--space-xs)" }}>
      {items.map((item) => (
        <div key={item.name} style={{ display: "grid", gap: 2 }}>
          <div
            style={{
              height: 38,
              background: `var(${item.varName})`,
              borderRadius: "var(--radius-sm)",
              border: "1px solid var(--border)",
            }}
          />
          <span
            style={{
              fontSize: "var(--text-app-xs)",
              color: "var(--muted-foreground)",
              fontWeight: 600,
            }}
          >
            {item.name}
          </span>
        </div>
      ))}
    </div>
  );
}
