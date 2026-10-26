"""广东 2026 考卷结构数据与接口契约。"""

from __future__ import annotations

from typing import Any

from httpx import AsyncClient

from app.data.exam_blueprints import get_exam, load_blueprints


def _exam(exam_id: str) -> dict[str, Any]:
    exam = get_exam(exam_id)
    assert exam is not None, f"缺少考卷结构 {exam_id}"
    return exam


def test_blueprints_load_with_four_exams() -> None:
    data = load_blueprints()
    assert data["region"] == "guangdong"
    assert data["year"] == 2026
    ids = [exam["id"] for exam in data["exams"]]
    assert ids == [
        "gaokao_2026_gd",
        "zhongkao_2026_gd_province",
        "zhongkao_2026_guangzhou",
        "zhongkao_2026_shenzhen",
    ]


def test_gaokao_total_and_math_structure() -> None:
    gaokao = _exam("gaokao_2026_gd")
    assert gaokao["total_score"] == 750
    subjects = {item["subject"]: item for item in gaokao["subjects"]}
    math = subjects["math"]
    assert math["score"] == 150
    parts = {part["part"]: part for part in math["structure"]}
    assert parts["单项选择题"]["score"] == 40
    assert parts["多项选择题"]["score"] == 18
    assert parts["填空题"]["score"] == 15
    assert parts["解答题"]["score"] == 77
    assert sum(part["score"] for part in math["structure"]) == 150
    # 广东独有：英语听说 20 分
    english = subjects["english"]
    assert sum(part["score"] for part in english["structure"]) == 150
    assert any("听说" in part["part"] for part in english["structure"])


def test_zhongkao_totals_match_subject_sums() -> None:
    guangzhou = _exam("zhongkao_2026_guangzhou")
    assert guangzhou["total_score"] == 810
    assert sum(item["score"] for item in guangzhou["subjects"]) == 810

    shenzhen = _exam("zhongkao_2026_shenzhen")
    assert shenzhen["total_score"] == 630
    assert sum(item["score"] for item in shenzhen["subjects"]) == 630

    province = _exam("zhongkao_2026_gd_province")
    assert len(province["subjects"]) == 9


async def test_meta_endpoint_serves_blueprints(client: AsyncClient) -> None:
    response = await client.get("/v1/meta/exam-blueprints")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["region"] == "guangdong"
    assert len(body["exams"]) == 4

    single = await client.get("/v1/meta/exam-blueprints/gaokao_2026_gd")
    assert single.status_code == 200, single.text
    assert single.json()["total_score"] == 750

    missing = await client.get("/v1/meta/exam-blueprints/nope")
    assert missing.status_code == 404
    assert missing.json()["code"] == "EXAM_BLUEPRINT_NOT_FOUND"
