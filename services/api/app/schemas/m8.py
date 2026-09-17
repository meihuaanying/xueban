"""M8 V3 功能契约（F-04/F-21/F-25/F-26/F-32~F-38）。"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# ------------------------------- F-21 背诵助手 -------------------------------


class RecitationCheckRequest(BaseModel):
    """背诵校验：ASR 转写与原文比对。"""

    reference: str = Field(min_length=1, max_length=5000)
    transcript: str = Field(max_length=5000, description="ASR 识别结果（mock 供应商可用原文模拟）")


class RecitationErrorMark(BaseModel):
    """错字/漏字标记。"""

    position: int
    expected: str
    got: str
    kind: Literal["wrong_char", "missing", "extra"]


class RecitationCheckResponse(BaseModel):
    """背诵结果：正确率 + 错字标记 + 易错点抽考建议。"""

    accuracy: float
    total_chars: int
    error_count: int
    errors: list[RecitationErrorMark]
    masked_preview: str
    quiz_points: list[str]


# ------------------------------- F-25 口语评测 -------------------------------


class DimensionScore(BaseModel):
    """维度得分。"""

    score: float
    comment: str


class SpeakingGradeRequest(BaseModel):
    """口语评测请求（音频在 M8 由客户端上传，mock 供应商直接比对文本）。"""

    reference: str = Field(min_length=1, max_length=2000)
    transcript: str = Field(max_length=2000)
    duration_seconds: float | None = Field(default=None, ge=0, le=600)


class SpeakingError(BaseModel):
    """音素级/单词级纠错。"""

    word: str
    expected: str
    pronunciation: str


class SpeakingGradeResponse(BaseModel):
    """口语评测结果：三维分数 + 纠错词列表。"""

    provider: str
    pronunciation: DimensionScore
    fluency: DimensionScore
    completeness: DimensionScore
    errors: list[SpeakingError]


# ------------------------------- F-26 判题 -------------------------------


class JudgeTestCaseIn(BaseModel):
    """判题用例。"""

    input: str = Field(default="", max_length=2000)
    expected: str = Field(default="", max_length=2000)


class CodeJudgeRequest(BaseModel):
    """编程题判题请求。"""

    language: Literal["python"] = "python"
    code: str = Field(min_length=1, max_length=20000)
    tests: list[JudgeTestCaseIn] = Field(min_length=1, max_length=20)
    timeout_seconds: float = Field(default=3.0, ge=0.5, le=10.0)


class JudgeCaseOut(BaseModel):
    """单用例结果。"""

    index: int
    passed: bool
    status: str
    stdout: str = ""
    expected: str = ""
    stderr: str = ""
    runtime_ms: int = 0


class CodeJudgeResponse(BaseModel):
    """判题结果 + 评审式反馈。"""

    verdict: str
    passed: int
    total: int
    results: list[JudgeCaseOut]
    feedback: dict[str, list[str]]
    blocked_reason: str | None = None


# -------------------------- F-32~F-35 陪练四件套 --------------------------


class CoachTurnRequest(BaseModel):
    """陪练对话一轮。"""

    session_id: uuid.UUID | None = None
    message: str = Field(min_length=1, max_length=2000)
    scene: str | None = Field(default=None, max_length=32, description="角色扮演场景名（F-32）")


class CoachCorrection(BaseModel):
    """纠错标注。"""

    original: str
    suggestion: str
    note: str


class CoachTurnResponse(BaseModel):
    """陪练回复（含纠错与追问）。"""

    session_id: uuid.UUID
    scene: str
    reply: str
    corrections: list[CoachCorrection]
    followups: list[str]
    crisis: bool = False
    crisis_resources: list[str] = Field(default_factory=list)


class WritingAssistRequest(BaseModel):
    """文书辅助（F-35：只改表达不代写）。"""

    kind: Literal["resume", "cover_letter", "paper_outline", "custom"] = "custom"
    text: str = Field(min_length=1, max_length=8000)
    goal: str | None = Field(default=None, max_length=200)


class WritingAnnotation(BaseModel):
    """批注。"""

    excerpt: str
    issue: str
    suggestion: str


class WritingAssistResponse(BaseModel):
    """修改建议 + 批注 + 诚信提示。"""

    suggestions: list[str]
    annotations: list[WritingAnnotation]
    polished_excerpt: str
    integrity_notice: str


# ------------------------------- F-37 文档问答 -------------------------------


class LibraryDocOut(BaseModel):
    """文档条目。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    page_count: int
    chunk_count: int
    status: str
    created_at: datetime


class LibraryAskRequest(BaseModel):
    """文档提问。"""

    question: str = Field(min_length=2, max_length=500)
    top_k: int = Field(default=3, ge=1, le=10)


class LibraryCitation(BaseModel):
    """页码引用。"""

    page: int
    chunk_id: uuid.UUID
    excerpt: str


class LibraryAskResponse(BaseModel):
    """带页码引用的回答。"""

    answer: str
    citations: list[LibraryCitation]


class LibrarySelfTestResponse(BaseModel):
    """基于文档生成的自测题。"""

    questions: list[dict[str, Any]]


# ------------------------------- F-38 知识卡片 -------------------------------


class CardCreateRequest(BaseModel):
    """创建知识卡片。"""

    front: str = Field(min_length=1, max_length=500)
    back: str = Field(min_length=1, max_length=2000)
    source_type: Literal["manual", "chat", "mistake"] = "manual"
    source_id: uuid.UUID | None = None
    tags: list[str] = Field(default_factory=list, max_length=10)


class CardOut(BaseModel):
    """知识卡片。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    front: str
    back: str
    tags: list[str]
    source_type: str
    created_at: datetime


class CardListResponse(BaseModel):
    """卡片列表。"""

    cards: list[CardOut]
    total: int


# --------------------------- F-36 / F-04 OCR 流程 ---------------------------


class PhotoSearchRequest(BaseModel):
    """拍照搜题（红线：结果页默认只给引导入口）。"""

    image_key: str | None = Field(default=None, max_length=512)
    ocr_text: str | None = Field(
        default=None, max_length=2000, description="人工确认后的文本（降级路径）"
    )
    subject: str = Field(default="math", max_length=32)


class PhotoSearchResponse(BaseModel):
    """拍照搜题结果（答案藏在三层提示之后）。"""

    recognized_text: str
    confidence: float
    degraded: bool
    degradation_hint: str | None = None
    match_found: bool
    question_id: uuid.UUID | None = None
    tutor_entry: str
    knowledge_points: list[str]


class HandwritingStep(BaseModel):
    """识别出的解题步骤。"""

    index: int
    content: str
    is_error: bool
    note: str


class HandwritingDiagnosisRequest(BaseModel):
    """手写步骤诊断（F-04）。"""

    image_key: str | None = Field(default=None, max_length=512)
    ocr_text: str | None = Field(default=None, max_length=4000)
    reference_solution: str | None = Field(default=None, max_length=4000)


class HandwritingDiagnosisResponse(BaseModel):
    """定位出错步骤（含降级提示）。"""

    steps: list[HandwritingStep]
    first_error_step: int | None
    confidence: float
    degraded: bool
    degradation_hint: str | None = None
    advice: str


# ------------------------------- F-31 家长周报 -------------------------------


class ParentWeeklyResponse(BaseModel):
    """家长端周报（F-31）：时长/进度/薄弱点 + ≥2 条亲子建议。"""

    child_id: uuid.UUID
    week_start: str
    week_end: str
    study_minutes: int
    tasks_done: int
    tasks_total: int
    mastery_average: float | None = None
    weak_points: list[str]
    suggestions: list[str]
