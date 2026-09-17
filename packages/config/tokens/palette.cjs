/**
 * 设计令牌：色板（供移动端 NativeWind 与图表等 JS 场景使用）
 * Web/Desktop 以 tokens/theme.css 为准，二者保持数值一致。
 */

const palette = {
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
  success: "#16a34a",
  warning: "#d97706",
  danger: "#dc2626",
  dark: {
    background: "#0b1220",
    card: "#121a2b",
    border: "#24304a",
  },
};

module.exports = { palette };
