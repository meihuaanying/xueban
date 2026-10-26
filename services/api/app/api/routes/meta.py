"""元数据路由：地区考卷结构（只读，供前端说明页与模考蓝图使用）。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.data.exam_blueprints import get_exam, load_blueprints

router = APIRouter(prefix="/v1/meta", tags=["meta"])


@router.get("/exam-blueprints", summary="地区考卷结构（广东 2026 高考/中考）")
def list_exam_blueprints() -> dict[str, Any]:
    """返回全部考卷结构（含来源置信度标注）。"""
    return load_blueprints()


@router.get("/exam-blueprints/{exam_id}", summary="单场考卷结构")
def read_exam_blueprint(exam_id: str) -> dict[str, Any]:
    """按 id 返回单场考卷结构；不存在时 404。"""
    exam = get_exam(exam_id)
    if exam is None:
        from app.errors import NotFoundError

        raise NotFoundError("考卷结构不存在", code="EXAM_BLUEPRINT_NOT_FOUND")
    return exam
