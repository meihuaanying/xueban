const { palette } = require("@xueban/config/tokens/palette.cjs");

/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./App.tsx", "./src/**/*.{ts,tsx}", "../../packages/core/src/**/*.{ts,tsx}"],
  presets: [require("nativewind/preset")],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        brand: palette.brand,
        primary: palette.brand[600],
        background: palette.neutral[50],
        foreground: palette.neutral[900],
        muted: palette.neutral[500],
      },
    },
  },
  plugins: [],
};
