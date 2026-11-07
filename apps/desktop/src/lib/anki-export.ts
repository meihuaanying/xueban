/**
 * 复习卡导出 Anki（吸收 DeepTutor「闪卡导出到 Anki」）。
 *
 * 为什么不走 lib/api 的 get<T>：导出是带鉴权的文件下载（text/plain blob），
 * 不是 JSON 契约；鉴权复用同一套 accessToken，后端地址复用同一运行时覆盖键。
 */

import { API_BASE_URL, ApiError, getAccessToken } from "./api";

const EXPORT_PATH = "/v1/review/export.anki";

export const ANKI_FILENAME = "xueban-review-anki.txt";

export interface AnkiDownload {
  filename: string;
  blob: Blob;
}

/** 纯函数：从响应构造下载负载；错误响应翻译成 ApiError 契约。 */
export async function buildAnkiDownload(response: Response): Promise<AnkiDownload> {
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as {
      code?: string;
      message?: string;
      trace_id?: string | null;
    };
    throw new ApiError(response.status, body);
  }
  const text = await response.text();
  return {
    filename: ANKI_FILENAME,
    blob: new Blob([text], { type: "text/plain;charset=utf-8" }),
  };
}

/** 触发浏览器下载（DOM 交互很薄，不进单测）。 */
function triggerDownload({ filename, blob }: AnkiDownload): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

/** 拉取并下载 Anki 导出文件；失败抛 ApiError，由调用方决定提示。 */
export async function downloadReviewAnki(): Promise<void> {
  const headers: Record<string, string> = {};
  const token = getAccessToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(`${API_BASE_URL}${EXPORT_PATH}`, { headers });
  triggerDownload(await buildAnkiDownload(response));
}
