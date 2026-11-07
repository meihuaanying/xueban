"use client";

/** 复习卡导出 Anki 的按钮（独立文件：复盘页保持 ≤150 行）。 */

import { Button } from "@xueban/ui";
import { useState } from "react";

import { downloadReviewAnki } from "@/lib/anki-export";

/** 导出失败时的学生视角文案；网络/权限错误直接展示后端消息。 */
function toFriendlyError(caught: unknown): string {
  if (caught instanceof Error && caught.message) return caught.message;
  return "导出失败，请稍后重试。";
}

export function AnkiExportButton() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async () => {
    setBusy(true);
    setError(null);
    try {
      await downloadReviewAnki();
    } catch (caught) {
      setError(toFriendlyError(caught));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-sm">
      <Button
        variant="outline"
        data-testid="review-export-anki"
        disabled={busy}
        onClick={() => void run()}
      >
        {busy ? "导出中…" : "导出 Anki 复习卡"}
      </Button>
      {error ? (
        <p role="alert" data-testid="review-export-anki-error" className="text-app-sm text-danger">
          {error}
        </p>
      ) : null}
    </div>
  );
}
