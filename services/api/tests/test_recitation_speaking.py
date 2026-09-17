"""背诵助手（F-21）与口语评测（F-25）测试。"""

from __future__ import annotations

from httpx import AsyncClient

from app.services import recitation_service, speaking_service
from tests.helpers import headers_of, register

REFERENCE = "先帝创业未半而中道崩殂，今天下三分，益州疲弊，此诚危急存亡之秋也。"
TRANSCRIPT_OK = "先帝创业未半而中道崩殂，今天下三分，益州疲弊，此诚危急存亡之秋也。"
TRANSCRIPT_WRONG = "先帝创业未半而中道崩阻，今天下三分，益州疲弊，此诚危急存亡之秋也。"


def test_recitation_full_match() -> None:
    result = recitation_service.check_recitation(REFERENCE, TRANSCRIPT_OK)
    assert result.accuracy == 1.0
    assert result.errors == []
    assert result.masked_preview == recitation_service._clean(REFERENCE)


def test_recitation_wrong_char_marked() -> None:
    result = recitation_service.check_recitation(REFERENCE, TRANSCRIPT_WRONG)
    assert 0 < result.accuracy < 1
    assert any(error.kind == "wrong_char" for error in result.errors)
    assert recitation_service.MASK_CHAR in result.masked_preview
    assert result.quiz_points


def test_recitation_missing_and_extra() -> None:
    missing = recitation_service.check_recitation("甲乙丙丁戊", "甲乙丁戊")
    assert any(error.kind == "missing" for error in missing.errors)
    extra = recitation_service.check_recitation("甲乙丙", "甲乙丙丁")
    assert any(error.kind == "extra" for error in extra.errors)


def test_mask_reference_keeps_punctuation() -> None:
    masked = recitation_service.mask_reference("床前明月光，疑是地上霜。")
    assert "，" in masked
    assert recitation_service.MASK_CHAR in masked


def test_speaking_scores_and_errors() -> None:
    result = speaking_service.grade_speaking(
        reference="I would like a cup of coffee please",
        transcript="I would like a cup of coffe please",
        duration_seconds=3.0,
    )
    assert result.provider == "mock"
    assert 0 < result.pronunciation <= 1
    assert result.completeness < 1
    assert any(error.word == "coffee" for error in result.errors)
    assert 1.2 <= 5 / 3.0 <= 3.2  # 语速落在自然带内


def test_speaking_fluency_bands() -> None:
    slow = speaking_service.grade_speaking(
        reference="one two three four five", transcript="one two", duration_seconds=5.0
    )
    fast = speaking_service.grade_speaking(
        reference="one two three", transcript="one two three", duration_seconds=0.5
    )
    assert slow.fluency < fast.fluency or fast.fluency >= 0.65


async def test_recitation_and_speaking_api(client: AsyncClient) -> None:
    user = await register(client)
    recitation = await client.post(
        "/v1/grading/recitation/check",
        json={"reference": REFERENCE, "transcript": TRANSCRIPT_WRONG},
        headers=headers_of(user),
    )
    assert recitation.status_code == 200, recitation.text
    body = recitation.json()
    assert body["error_count"] >= 1
    assert body["masked_preview"]

    speaking = await client.post(
        "/v1/grading/speaking",
        json={
            "reference": "I would like a cup of coffee please",
            "transcript": "I would like a cup of coffe please",
            "duration_seconds": 3.0,
        },
        headers=headers_of(user),
    )
    assert speaking.status_code == 200, speaking.text
    payload = speaking.json()
    assert payload["provider"] == "mock"
    assert payload["pronunciation"]["score"] > 0
    assert payload["errors"]


async def test_code_judge_api(client: AsyncClient) -> None:
    user = await register(client)
    response = await client.post(
        "/v1/grading/code",
        json={
            "language": "python",
            "code": "import sys\nprint(sum(int(x) for x in sys.stdin.read().split()))\n",
            "tests": [{"input": "1 2 3", "expected": "6"}],
        },
        headers=headers_of(user),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["verdict"] == "accepted"
    assert body["feedback"]["boundary"]

    blocked = await client.post(
        "/v1/grading/code",
        json={
            "language": "python",
            "code": "import socket\nprint('net')",
            "tests": [{"input": "", "expected": "net"}],
        },
        headers=headers_of(user),
    )
    assert blocked.status_code == 200
    assert blocked.json()["verdict"] == "blocked"
