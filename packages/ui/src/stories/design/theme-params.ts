/**
 * 设计稿走查参数读取
 *
 * Ladle 按 `f` 进入全屏时会重写 URL（丢弃 theme/mode 等自定义 query），
 * 组件若每次 render 都读 `location.search` 就会退回默认皮肤——
 * 这正是「深色截图与亮色截图完全一致」的根因。
 * 解决办法：模块首次加载时把原始 search 存进 sessionStorage，之后一律以它为准。
 */
const CACHE_KEY = "xueban-design-params";

function snapshot(): string {
  if (typeof window === "undefined") return "";
  const search = window.location.search;
  const params = new URLSearchParams(search);
  // URL 里带 theme/mode ⇒ 是一次新的走查指令，刷新缓存
  if (params.has("theme") || params.has("mode")) {
    try {
      window.sessionStorage.setItem(CACHE_KEY, search);
    } catch {
      /* 隐私模式下忽略 */
    }
    return search;
  }
  // URL 已被 Ladle 全屏重写（只剩 ?story=）⇒ 沿用上一次指令
  try {
    return window.sessionStorage.getItem(CACHE_KEY) ?? search;
  } catch {
    return search;
  }
}

snapshot();

/** 读取 ?theme= / ?mode= 等走查参数（对全屏重写免疫） */
export function readParam(name: string): string | null {
  if (typeof window === "undefined") return null;
  return new URLSearchParams(snapshot()).get(name);
}

/** 清除走查参数缓存（截图脚本切换 story 时用） */
export function clearParamCache(): void {
  try {
    window.sessionStorage.removeItem(CACHE_KEY);
  } catch {
    /* 忽略 */
  }
}

/** 当前走查皮肤：focus=少年/成人（可深色），kids=儿童（恒亮色） */
export function currentTheme(): { theme: "focus" | "kids"; mode: "light" | "dark" } {
  return {
    theme: readParam("theme") === "kids" ? "kids" : "focus",
    mode: readParam("mode") === "dark" ? "dark" : "light",
  };
}
