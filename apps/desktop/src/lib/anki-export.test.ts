import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, setAccessToken } from "./api";
import { ANKI_FILENAME, buildAnkiDownload, downloadReviewAnki } from "./anki-export";

function textResponse(ok: boolean, body: string, status = ok ? 200 : 400): Response {
  return new Response(body, {
    status,
    headers: { "Content-Type": "text/plain;charset=utf-8" },
  });
}

afterEach(() => {
  vi.restoreAllMocks();
  setAccessToken(null);
});

describe("buildAnkiDownload（纯函数）", () => {
  it("成功响应 → 文件名与 text/plain blob", async () => {
    const text = "#separator:tab\n";
    const { filename, blob } = await buildAnkiDownload(textResponse(true, text));
    expect(filename).toBe(ANKI_FILENAME);
    // jsdom 的 Blob 没有 .text()：用 size/type 断言内容进入 blob
    expect(blob.size).toBe(text.length);
    expect(blob.type).toBe("text/plain;charset=utf-8");
  });

  it("错误响应 → 抛 ApiError 并保留 code", async () => {
    await expect(
      buildAnkiDownload(
        new Response(JSON.stringify({ code: "X", message: "无权访问" }), { status: 403 }),
      ),
    ).rejects.toMatchObject({ name: "ApiError", status: 403, code: "X" });
  });
});

describe("downloadReviewAnki（DOM 接线）", () => {
  it("带 Bearer 请求导出接口并触发下载", async () => {
    setAccessToken("token-abc");
    const fetchMock = vi.fn().mockResolvedValue(textResponse(true, "#deck:学伴::复习\n"));
    vi.stubGlobal("fetch", fetchMock);
    const objectUrl = "blob:mock";
    const createObjectURL = vi.fn(() => objectUrl);
    vi.stubGlobal("URL", { ...URL, createObjectURL, revokeObjectURL: vi.fn() });

    const anchor = { href: "", download: "", click: vi.fn() };
    const createElement = vi
      .spyOn(document, "createElement")
      .mockReturnValue(anchor as unknown as HTMLAnchorElement);

    await downloadReviewAnki();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/v1/review/export.anki");
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer token-abc");
    expect(createObjectURL).toHaveBeenCalledTimes(1);
    expect(anchor.download).toBe(ANKI_FILENAME);
    expect(anchor.click).toHaveBeenCalledTimes(1);
    createElement.mockRestore();
  });

  it("无令牌时不带 Authorization 头", async () => {
    const fetchMock = vi.fn().mockResolvedValue(textResponse(true, ""));
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("URL", { ...URL, createObjectURL: vi.fn(() => "blob:x"), revokeObjectURL: vi.fn() });
    vi.spyOn(document, "createElement").mockReturnValue({
      href: "",
      download: "",
      click: vi.fn(),
    } as unknown as HTMLAnchorElement);

    await downloadReviewAnki();
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect((init.headers as Record<string, string>).Authorization).toBeUndefined();
  });

  it("失败时抛 ApiError（由按钮组件转提示）", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ code: "HTTP_500", message: "服务器错误" }), { status: 500 }),
      ),
    );
    await expect(downloadReviewAnki()).rejects.toBeInstanceOf(ApiError);
  });
});
