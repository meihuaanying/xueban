/** 产品常量（全端共享） */

export const APP_NAME = "学伴";
export const APP_SLOGAN = "把每一道题，教到你自己会做";
export const DEFAULT_LOCALE = "zh-CN";
export const API_PREFIX = "/v1" as const;

/** 客户端可访问的 API 基地址（由各端注入环境变量） */
export function getApiBaseUrl(fallback = "http://localhost:8000"): string {
  return process.env.NEXT_PUBLIC_API_BASE_URL ?? process.env.EXPO_PUBLIC_API_BASE_URL ?? fallback;
}
