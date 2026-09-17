"use client";

/** 暗色模式切换（T9.3）：主题存 localStorage，首帧前由内联脚本避免闪烁。 */

import { useEffect, useState } from "react";
import { Button } from "@xueban/ui";

export function ThemeToggle() {
  const [dark, setDark] = useState(false);

  useEffect(() => {
    const stored = window.localStorage.getItem("xueban.theme");
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const shouldUseDark = stored ? stored === "dark" : prefersDark;
    setDark(shouldUseDark);
    document.documentElement.classList.toggle("dark", shouldUseDark);
  }, []);

  return (
    <Button
      variant="ghost"
      size="sm"
      data-testid="theme-toggle"
      aria-pressed={dark}
      onClick={() => {
        const next = !dark;
        setDark(next);
        document.documentElement.classList.toggle("dark", next);
        window.localStorage.setItem("xueban.theme", next ? "dark" : "light");
      }}
    >
      {dark ? "浅色" : "深色"}
    </Button>
  );
}
