"""OCR 服务占位实现。

M8 将替换为 PaddleOCR + Pix2Text 的真实实现；
当前仅提供健康检查与 501 占位响应，保证编排链路可运行。
"""

from fastapi import FastAPI, HTTPException

app = FastAPI(title="学伴 OCR 服务", version="0.1.0")


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    """健康检查。"""
    return {"status": "ok", "service": "xueban-ocr", "version": "0.1.0"}


@app.post("/v1/ocr")
async def recognize() -> dict[str, str]:
    """识别接口占位：M8 接入 PaddleOCR/Pix2Text。"""
    raise HTTPException(status_code=501, detail="OCR 识别能力将在 M8 里程碑接入")
