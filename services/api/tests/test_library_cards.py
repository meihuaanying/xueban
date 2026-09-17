"""文档问答（F-37）与知识卡片 / Anki 导出（F-38）测试。"""

from __future__ import annotations

import io
import sqlite3
import zipfile

from fpdf import FPDF
from httpx import AsyncClient

from tests.helpers import headers_of, register

FONT_PATH = "app/assets/fonts/ZCOOLXiaoWei-Regular.ttf"


def build_pdf() -> bytes:
    """生成含中文与页码信息的多页 PDF（模拟讲义）。"""
    pdf = FPDF()
    pdf.add_font("ZCOOL", "", FONT_PATH)
    pdf.set_font("ZCOOL", size=14)
    pdf.add_page()
    pdf.multi_cell(
        0,
        10,
        "第一章 有理数。有理数包括正数、负数和零。数轴上的点与有理数一一对应。",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.add_page()
    pdf.multi_cell(
        0,
        10,
        "第二章 一元一次方程。等式两边同时加上或减去同一个数，等式仍然成立。",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    output = pdf.output()
    return bytes(output)


async def test_library_upload_ask_with_citations(client: AsyncClient) -> None:
    user = await register(client)
    files = {"file": ("textbook.pdf", build_pdf(), "application/pdf")}
    uploaded = await client.post(
        "/v1/library/docs",
        data={"title": "数学讲义（测试）"},
        files=files,
        headers=headers_of(user),
    )
    assert uploaded.status_code == 200, uploaded.text
    document = uploaded.json()
    assert document["status"] in ("ready", "parsing")
    assert document["page_count"] >= 2
    assert document["chunk_count"] >= 1

    listed = await client.get("/v1/library/docs", headers=headers_of(user))
    assert listed.status_code == 200
    assert any(item["id"] == document["id"] for item in listed.json())

    asked = await client.post(
        f"/v1/library/{document['id']}/ask",
        json={"question": "等式两边同时加上同一个数会怎样？", "top_k": 2},
        headers=headers_of(user),
    )
    assert asked.status_code == 200, asked.text
    body = asked.json()
    assert body["citations"], "回答必须带页码引用"
    assert all(citation["page"] >= 1 for citation in body["citations"])
    assert body["answer"]

    self_test = await client.get(
        f"/v1/library/{document['id']}/self-test", headers=headers_of(user)
    )
    assert self_test.status_code == 200
    questions = self_test.json()["questions"]
    assert questions
    assert all(item["answer"] and item["page"] >= 1 for item in questions)


async def test_library_rbac_other_user_denied(client: AsyncClient) -> None:
    owner = await register(client)
    other = await register(client)
    uploaded = await client.post(
        "/v1/library/docs",
        data={"title": "私有讲义"},
        files={"file": ("private.pdf", build_pdf(), "application/pdf")},
        headers=headers_of(owner),
    )
    document_id = uploaded.json()["id"]

    denied = await client.post(
        f"/v1/library/{document_id}/ask",
        json={"question": "这份讲义讲了什么？"},
        headers=headers_of(other),
    )
    assert denied.status_code == 404
    assert denied.json()["code"] == "LIBRARY_DOC_NOT_FOUND"


async def test_cards_crud_and_anki_export(client: AsyncClient) -> None:
    user = await register(client)
    created = await client.post(
        "/v1/cards",
        json={
            "front": "一元一次方程两边同时加同一个数？",
            "back": "等式仍然成立。",
            "source_type": "manual",
            "tags": ["数学", "方程"],
        },
        headers=headers_of(user),
    )
    assert created.status_code == 201, created.text
    card = created.json()

    await client.post(
        "/v1/cards",
        json={"front": "有理数包括？", "back": "正数、负数和零。", "tags": ["数学"]},
        headers=headers_of(user),
    )
    listed = await client.get("/v1/cards", headers=headers_of(user))
    assert listed.status_code == 200
    assert listed.json()["total"] >= 2

    exported = await client.get("/v1/cards/export.apkg", headers=headers_of(user))
    assert exported.status_code == 200, exported.text
    assert exported.headers["content-type"].startswith("application/apkg")
    assert exported.headers["x-card-count"] in ("2", "3", str(listed.json()["total"]))
    data = exported.content

    # .apkg 是 zip（含 collection.anki2 = SQLite）；用 stdlib 校验结构可导入
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = archive.namelist()
        assert "collection.anki2" in names
        with archive.open("collection.anki2") as collection:
            payload = collection.read()
    # 把 SQLite 文件写入临时目录进行结构校验（Windows 需显式关闭连接后才能清理）
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "collection.anki2"
        db_path.write_bytes(payload)
        connection = sqlite3.connect(str(db_path))
        try:
            tables = {
                row[0]
                for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
            assert {"notes", "cards", "col"} <= tables
            note_count = connection.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
            assert note_count >= 2
        finally:
            connection.close()

    deleted = await client.delete(f"/v1/cards/{card['id']}", headers=headers_of(user))
    assert deleted.status_code == 204
    after = await client.get("/v1/cards", headers=headers_of(user))
    assert all(item["id"] != card["id"] for item in after.json()["cards"])


async def test_cards_export_requires_cards(client: AsyncClient) -> None:
    user = await register(client)
    response = await client.get("/v1/cards/export.apkg", headers=headers_of(user))
    assert response.status_code == 404
    assert response.json()["code"] == "CARD_EMPTY"
