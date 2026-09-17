"""批改测试（T3.7 / F-22~F-24）：客观秒批、主观逐步给分、作文三口径。"""

from __future__ import annotations

import json
import uuid

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.models import (
    ChatSession,
    GradingRecord,
    KnowledgePoint,
    MasteryRecord,
    Question,
    QuestionKnowledgePoint,
    QuestionStatus,
    QuestionType,
)
from app.services.llm_client import LlmClient
from app.services.observability import ObservabilityService
from tests.helpers import headers_of, register


def _handler(content: str):  # type: ignore[no-untyped-def]
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "test-model",
                "choices": [{"message": {"role": "assistant", "content": content}}],
                "usage": {"total_tokens": 88},
            },
        )

    return handler


def _install_llm(app: object, content: str) -> None:
    settings = Settings(
        litellm_base_url="http://llm.test",
        litellm_master_key="sk-test",
        llm_max_retries=0,
        llm_retry_backoff_seconds=0.0,
    )
    observability = ObservabilityService(settings)
    app.state.llm = LlmClient(  # type: ignore[attr-defined]
        settings, observability, transport=httpx.MockTransport(_handler(content))
    )


async def _seed_question(
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    answer: str = "2",
) -> uuid.UUID:
    async with sessionmaker() as session:
        kp = KnowledgePoint(code="math.test.grade", name="一元一次方程", subject="math")
        session.add(kp)
        await session.flush()
        question = Question(
            subject="math",
            stage="junior",
            qtype=QuestionType.FILL,
            stem="解方程：2x + 3 = 7",
            answer=answer,
            analysis="移项后除以 2。",
            status=QuestionStatus.PUBLISHED,
        )
        session.add(question)
        await session.flush()
        session.add(QuestionKnowledgePoint(question_id=question.id, knowledge_point_id=kp.id))
        await session.commit()
        return question.id


# ---------- F-22 客观题 ----------


async def test_objective_correct(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    question_id = await _seed_question(sessionmaker)
    payload = await register(client)
    response = await client.post(
        "/v1/grading/objective",
        json={"question_id": str(question_id), "answer": "2"},
        headers=headers_of(payload),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["is_correct"] is True
    assert body["tutor_session_id"] is None
    async with sessionmaker() as session:
        records = await session.scalar(select(func.count()).select_from(GradingRecord))
        mastery = await session.scalar(select(func.count()).select_from(MasteryRecord))
    assert records == 1
    assert mastery == 1


async def test_objective_wrong_returns_tutor_entry(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    question_id = await _seed_question(sessionmaker)
    payload = await register(client)
    response = await client.post(
        "/v1/grading/objective",
        json={"question_id": str(question_id), "answer": "错误答案"},
        headers=headers_of(payload),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["is_correct"] is False
    assert body["correct_answer"] == "2"
    assert body["tutor_session_id"] is not None
    async with sessionmaker() as session:
        sessions = await session.scalar(select(func.count()).select_from(ChatSession))
    assert sessions == 1


async def test_objective_unknown_question(client: AsyncClient) -> None:
    payload = await register(client)
    response = await client.post(
        "/v1/grading/objective",
        json={"question_id": str(uuid.uuid4()), "answer": "1"},
        headers=headers_of(payload),
    )
    assert response.status_code == 404


# ---------- F-23 主观题 ----------


SUBJECTIVE_JSON = json.dumps(
    {
        "total_score": 80,
        "max_score": 100,
        "steps": [
            {
                "step": "移项得 2x = 4",
                "score": 40,
                "comment": "思路正确",
                "lost_points": "",
            },
            {
                "step": "得出 x = 2",
                "score": 40,
                "comment": "结论正确",
                "lost_points": "未写出检验步骤，扣 20 分",
            },
        ],
        "rewrite": "两边同减 3 得 $2x = 4$，两边同除以 2 得 $x = 2$。",
        "summary": "步骤完整，注意补充检验。",
    },
    ensure_ascii=False,
)


async def test_subjective_grading_with_machine_check_pass(
    client: AsyncClient, app: object, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    question_id = await _seed_question(sessionmaker)
    payload = await register(client)
    _install_llm(app, SUBJECTIVE_JSON)
    response = await client.post(
        "/v1/grading/subjective",
        json={
            "question_id": str(question_id),
            "student_answer": "移项得 $2x = 4$，所以 $x = 2$。",
        },
        headers=headers_of(payload),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total_score"] == 80
    assert len(body["steps"]) == 2
    assert body["steps"][1]["lost_points"]
    assert body["machine_check"] == {"checked": True, "answer_verified": True}
    async with sessionmaker() as session:
        records = await session.scalar(select(func.count()).select_from(GradingRecord))
    assert records == 1


async def test_subjective_machine_check_flags_wrong_math(
    client: AsyncClient, app: object, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    question_id = await _seed_question(sessionmaker)
    payload = await register(client)
    _install_llm(app, SUBJECTIVE_JSON)
    response = await client.post(
        "/v1/grading/subjective",
        json={"question_id": str(question_id), "student_answer": "解得 $x = 5$。"},
        headers=headers_of(payload),
    )
    assert response.status_code == 200
    assert response.json()["machine_check"]["answer_verified"] is False


async def test_subjective_inline_context_without_question(
    client: AsyncClient, app: object
) -> None:
    payload = await register(client)
    _install_llm(app, SUBJECTIVE_JSON)
    response = await client.post(
        "/v1/grading/subjective",
        json={
            "stem": "求 1+1",
            "answer": "2",
            "student_answer": "等于 2",
        },
        headers=headers_of(payload),
    )
    assert response.status_code == 200
    assert response.json()["machine_check"]["answer_verified"] is True


async def test_subjective_missing_context(client: AsyncClient, app: object) -> None:
    payload = await register(client)
    _install_llm(app, SUBJECTIVE_JSON)
    response = await client.post(
        "/v1/grading/subjective",
        json={"student_answer": "随便写写"},
        headers=headers_of(payload),
    )
    assert response.status_code == 400
    assert response.json()["code"] == "GRADING_MISSING_CONTEXT"


async def test_subjective_bad_output(
    client: AsyncClient, app: object, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    question_id = await _seed_question(sessionmaker)
    payload = await register(client)
    _install_llm(app, "不是 JSON")
    response = await client.post(
        "/v1/grading/subjective",
        json={"question_id": str(question_id), "student_answer": "x = 2"},
        headers=headers_of(payload),
    )
    assert response.status_code == 502
    assert response.json()["code"] == "GRADING_BAD_OUTPUT"


# ---------- F-24 作文 ----------


def _essay_json() -> str:
    return json.dumps(
        {
            "total_score": 42,
            "max_score": 50,
            "structure": {"score": 15, "max_score": 20, "comment": "层次较清晰"},
            "ideas": {"score": 17, "max_score": 20, "comment": "立意积极"},
            "language": {"score": 10, "max_score": 10, "comment": "语言流畅"},
            "paragraphs": [
                {"index": 1, "comment": "开篇点题", "suggestion": "可增加细节"},
                {"index": 2, "comment": "论据单薄", "suggestion": "补充一个具体事例"},
            ],
            "upgrade_sample": "升格示范：在第二段加入具体事例……",
            "summary": "总体不错，注意论据支撑。",
        },
        ensure_ascii=False,
    )


@pytest.mark.parametrize("rubric", ["zhongkao", "gaokao", "cet", "kaoyan"])
async def test_essay_grading_all_rubrics(
    client: AsyncClient, app: object, rubric: str
) -> None:
    payload = await register(client)
    _install_llm(app, _essay_json())
    response = await client.post(
        "/v1/grading/essay",
        json={
            "rubric": rubric,
            "prompt": "以「坚持」为题写一篇作文",
            "content": "坚持是通向成功的必经之路。" * 10,
        },
        headers=headers_of(payload),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["rubric"] == rubric
    assert body["structure"]["score"] == 15
    assert body["ideas"]["comment"] == "立意积极"
    assert len(body["paragraphs"]) == 2
    assert body["upgrade_sample"]


async def test_essay_invalid_rubric(client: AsyncClient, app: object) -> None:
    payload = await register(client)
    _install_llm(app, _essay_json())
    response = await client.post(
        "/v1/grading/essay",
        json={"rubric": "toefl", "content": "内容" * 30},
        headers=headers_of(payload),
    )
    assert response.status_code == 422


async def test_essay_content_too_short(client: AsyncClient, app: object) -> None:
    payload = await register(client)
    _install_llm(app, _essay_json())
    response = await client.post(
        "/v1/grading/essay",
        json={"rubric": "gaokao", "content": "太短"},
        headers=headers_of(payload),
    )
    assert response.status_code == 422


async def test_grading_requires_auth(client: AsyncClient) -> None:
    assert (
        await client.post(
            "/v1/grading/objective", json={"question_id": str(uuid.uuid4()), "answer": "1"}
        )
    ).status_code == 401
    assert (
        await client.post(
            "/v1/grading/subjective",
            json={"stem": "1+1=?", "answer": "2", "student_answer": "2"},
        )
    ).status_code == 401
    assert (
        await client.post(
            "/v1/grading/essay", json={"rubric": "gaokao", "content": "内容" * 30}
        )
    ).status_code == 401
