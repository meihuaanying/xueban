/**
 * 设计令牌：色板（供移动端 NativeWind 与图表等 JS 场景使用）
 *
 * 与 tokens/theme.css 保持数值一致，三层结构对应关系：
 *   primitive  → 本文件的 scales / brand / neutral / indigo / sun / azure / grass / status / bark / coral
 *   semantic   → 本文件的 themes[theme]
 *   component  → 见 theme.css 第 3 层（纯 CSS 变量，不在 JS 侧重复）
 *
 * 主题（挂 data-theme）：
 *   focus（默认）少年/成人：中性灰底 + 靛蓝单一强调色
 *   kids             儿童：暖纸底 + 明黄/天蓝/草绿
 *   深色仅 focus 支持：themes.focusDark
 */

const palette = {
  // -- 品牌蓝（信任蓝）：品牌资产与图表/JS 场景取色 --
  brand: {
    50: "#eef6ff",
    100: "#d9ecff",
    200: "#bcdcff",
    300: "#8ec7ff",
    400: "#59a8ff",
    500: "#3386ff",
    600: "#1f66f5",
    700: "#1a52e1",
    800: "#1c45b6",
    900: "#1c3d8f",
    950: "#152656",
  },

  // -- 中性灰（focus 主题骨架）--
  neutral: {
    50: "#f7f9fc",
    100: "#f1f5f9",
    200: "#e2e8f0",
    300: "#cbd5e1",
    400: "#94a3b8",
    500: "#64748b",
    600: "#475569",
    700: "#334155",
    800: "#1e293b",
    900: "#0f172a",
  },

  // -- 靛蓝：focus 强调色 --
  indigo: {
    50: "#eef2ff",
    100: "#e0e7ff",
    200: "#c7d2fe",
    300: "#a5b4fc",
    400: "#818cf8",
    500: "#6366f1",
    600: "#4f46e5",
    700: "#4338ca",
    800: "#3730a3",
    900: "#1e1b4b",
  },

  // -- 明黄：kids 主色 --
  sun: {
    50: "#fffbeb",
    100: "#fff4cc",
    200: "#ffe9a0",
    300: "#ffda66",
    400: "#ffc53d",
    500: "#f2a81d",
    600: "#c97f0a",
    700: "#9a5f06",
    800: "#6e4404",
    900: "#4a2e03",
  },

  // -- 天蓝：kids 信息色 --
  azure: {
    50: "#eff9ff",
    100: "#d9f0ff",
    200: "#b4e2ff",
    300: "#7fcbff",
    400: "#38aef5",
    500: "#1e90e0",
    600: "#0f73bd",
    700: "#0b5a96",
    800: "#094473",
    900: "#062f4f",
  },

  // -- 草绿：kids 成长色 --
  grass: {
    50: "#f0fdf4",
    100: "#dcfce7",
    200: "#bbf7d0",
    300: "#86efac",
    400: "#4ade80",
    500: "#22c55e",
    600: "#16a34a",
    700: "#15803d",
    800: "#166534",
    900: "#14532d",
  },

  // -- 状态色阶 --
  success: "#16a34a",
  warning: "#d97706",
  danger: "#dc2626",
  status: {
    success: { 50: "#f0fdf4", 200: "#bbf7d0", 500: "#22c55e", 600: "#16a34a", 700: "#15803d" },
    warning: { 50: "#fffbeb", 200: "#fde68a", 500: "#f59e0b", 600: "#d97706", 700: "#b45309" },
    danger: { 50: "#fef2f2", 200: "#fecaca", 500: "#ef4444", 600: "#dc2626", 700: "#b91c1c" },
  },

  // -- 暖棕（kids 文字）/ 珊瑚（kids 掌握度五段）--
  bark: { 500: "#8a6d3b", 700: "#5c4620", 900: "#3a2f14" },
  coral: { 500: "#ff8a5b" },

  // -- 间距：8pt 网格 --
  space: {
    hair: 4,
    xs: 8,
    sm: 16,
    md: 24,
    lg: 32,
    xl: 40,
    "2xl": 48,
    "3xl": 64,
    "4xl": 96,
  },

  dark: {
    background: "#0b1220",
    card: "#121a2b",
    border: "#24304a",
  },

  // -- 语义层：掌握度五档 / 三层提示（两主题各自取值）--
  masteryLabels: ["未接触", "初识", "入门", "熟练", "精通"],
  hintLabels: ["一层·轻推", "二层·举一反三", "三层·微支架"],

  // -- 第 2 层 SEMANTIC（随主题切换）--
  themes: {
    // 少年/成人（默认）
    focus: {
      background: "#f7f8fa",
      foreground: "#0f172a",
      card: "#ffffff",
      cardForeground: "#0f172a",
      surfaceRaised: "#ffffff",
      surfaceSunken: "#f1f5f9",
      sidebar: "#ffffff",
      sidebarForeground: "#0f172a",
      sidebarBorder: "#e2e8f0",
      primary: "#4f46e5",
      primaryForeground: "#ffffff",
      primaryHover: "#4338ca",
      primarySoft: "#eef2ff",
      secondary: "#f1f5f9",
      secondaryForeground: "#1e293b",
      muted: "#f1f5f9",
      mutedForeground: "#5c6b7f",
      accent: "#eef2ff",
      accentForeground: "#4338ca",
      success: "#16a34a",
      warning: "#d97706",
      destructive: "#dc2626",
      danger: "#dc2626",
      info: "#2563eb",
      border: "#e2e8f0",
      input: "#e2e8f0",
      ring: "#6366f1",
      mastery: ["#cbd5e1", "#60a5fa", "#34d399", "#f59e0b", "#4f46e5"],
      hint: ["#0ea5e9", "#d97706", "#16a34a"],
      dials: { font: 1, radius: 1, control: 1 },
      tapMin: 32,
    },
    // 儿童
    kids: {
      background: "#fffcf2",
      foreground: "#3a2f14",
      card: "#ffffff",
      cardForeground: "#3a2f14",
      surfaceRaised: "#ffffff",
      surfaceSunken: "#fff4d6",
      sidebar: "#fffdf5",
      sidebarForeground: "#3a2f14",
      sidebarBorder: "#ffe4a3",
      primary: "#ffc53d",
      primaryForeground: "#4a2e03",
      primaryHover: "#f5b824",
      primarySoft: "#fff4cc",
      secondary: "#e8f5ff",
      secondaryForeground: "#0b5a96",
      muted: "#fff4d6",
      mutedForeground: "#7f6334",
      accent: "#d9f0ff",
      accentForeground: "#0b5a96",
      success: "#22c55e",
      warning: "#f59e0b",
      destructive: "#ef4444",
      danger: "#ef4444",
      info: "#1e90e0",
      border: "#f0dfae",
      input: "#f0dfae",
      ring: "#38aef5",
      mastery: ["#e2e8f0", "#7fcbff", "#4ade80", "#ffc53d", "#ff8a5b"],
      hint: ["#38aef5", "#f2a81d", "#22c55e"],
      dials: { font: 1.2857, radius: 1.6, control: 1.18 },
      tapMin: 48,
    },
  },

  // -- focus 深色（.dark / data-mode="dark"）--
  focusDark: {
    background: "#0b1220",
    foreground: "#e8eefc",
    card: "#121a2b",
    cardForeground: "#e8eefc",
    surfaceRaised: "#16203a",
    surfaceSunken: "#0d1524",
    sidebar: "#0f1729",
    sidebarForeground: "#e8eefc",
    sidebarBorder: "#24304a",
    primary: "#818cf8",
    primaryForeground: "#0b1220",
    primaryHover: "#a5b4fc",
    primarySoft: "#1e2749",
    secondary: "#1b2740",
    secondaryForeground: "#d6e2fb",
    muted: "#172136",
    mutedForeground: "#93a4c3",
    accent: "#1a2a4a",
    accentForeground: "#a5b4fc",
    success: "#34d399",
    warning: "#fbbf24",
    destructive: "#f87171",
    danger: "#f87171",
    info: "#60a5fa",
    border: "#24304a",
    input: "#24304a",
    ring: "#818cf8",
    mastery: ["#334155", "#3b82f6", "#10b981", "#f59e0b", "#a5b4fc"],
    hint: ["#38bdf8", "#fbbf24", "#34d399"],
  },
};

module.exports = { palette };
