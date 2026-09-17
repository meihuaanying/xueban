"""知识点图谱测试（T2.2）：规模、无环、种子幂等。"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.data.knowledge_graph import GraphEdge, build_graph, topological_order
from app.models import KnowledgeEdge, KnowledgePoint, MistakeTag


def test_graph_scale() -> None:
    nodes, edges = build_graph()
    assert len(nodes) >= 300, "知识点数量须不少于 300"
    assert len(edges) >= len(nodes)
    assert {node.subject for node in nodes} == {"math", "english"}


def test_graph_is_dag() -> None:
    nodes, edges = build_graph()
    order = topological_order(nodes, edges)
    assert len(order) == len(nodes)
    position = {code: index for index, code in enumerate(order)}
    for edge in edges:
        assert position[edge.from_code] < position[edge.to_code], "依赖边必须从先序指向后序"


def test_cycle_detected() -> None:
    nodes, edges = build_graph()
    first = edges[0]
    broken = [*edges, GraphEdge(first.to_code, first.from_code)]
    try:
        topological_order(nodes, broken)
        raised = False
    except ValueError:
        raised = True
    assert raised is True


def test_unknown_edge_reference_detected() -> None:
    nodes, edges = build_graph()
    broken = [*edges, GraphEdge(nodes[0].code, "not-exists")]
    try:
        topological_order(nodes, broken)
        raised = False
    except ValueError:
        raised = True
    assert raised is True


async def test_seed_idempotent(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    from scripts.seed_knowledge_graph import seed

    first = await seed()
    assert first["nodes_created"] == first["nodes_total"]
    assert first["tags_created"] == 5

    second = await seed()
    assert second["nodes_created"] == 0
    assert second["edges_created"] == 0
    assert second["tags_created"] == 0

    async with sessionmaker() as session:
        node_count = await session.scalar(select(func.count()).select_from(KnowledgePoint))
        edge_count = await session.scalar(select(func.count()).select_from(KnowledgeEdge))
        tag_count = await session.scalar(select(func.count()).select_from(MistakeTag))
    assert node_count == first["nodes_total"]
    assert edge_count == first["edges_total"]
    assert tag_count == 5
