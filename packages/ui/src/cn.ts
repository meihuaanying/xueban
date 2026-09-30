import { clsx, type ClassValue } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

/**
 * 设计系统的自定义字号阶梯（`text-app*`）。
 *
 * tailwind-merge 默认把未知的 `text-` 前缀类都归入 `text-color` 组，
 * 于是 size 变体里的 `text-app-md` 会把 variant 的 `text-primary-foreground`
 * 当成同类冲突项删掉 —— 按钮前景色因此掉回浏览器默认黑。
 * 这里把 `text-app*` 显式注册进 `font-size` 组，让两者互不覆盖。
 */
const TW_MERGE = extendTailwindMerge({
  extend: {
    classGroups: {
      "font-size": [{ text: ["app-xs", "app-sm", "app", "app-md", "app-lg", "app-xl", "app-2xl", "app-3xl"] }],
    },
  },
});

/** 合并 Tailwind 类名（处理冲突） */
export function cn(...inputs: ClassValue[]): string {
  return TW_MERGE(clsx(inputs));
}
