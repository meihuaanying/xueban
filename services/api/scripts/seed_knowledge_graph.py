"""种子脚本：知识点图谱 + 前置依赖边 + 错因标签（幂等）。

用法（services/api 目录）：
    .venv/Scripts/python scripts/seed_knowledge_graph.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import database_session
from sqlalchemy import select

from app.data.knowledge_graph import build_graph, topological_order
from app.models import KnowledgeEdge, KnowledgePoint, MistakeTag

MISTAKE_TAG_SEED: list[tuple[str, str, str]] = [
    ("concept", "概念不清", "cognition"),
    ("reading", "审题偏差", "process"),
    ("computation", "计算失误", "skill"),
    ("method", "方法缺失", "method"),
    ("transfer", "迁移薄弱", "application"),
]


async def seed() -> dict[str, int]:
    """写入知识点/边/错因标签，返回统计。"""
    nodes, edges = build_graph()
    order = topological_order(nodes, edges)  # 无环校验（有环将抛错）
    node_map = {node.code: node for node in nodes}
    order_index = {code: index for index, code in enumerate(order)}

    async with database_session() as session:
        existing_rows = (
            await session.execute(select(KnowledgePoint.code, KnowledgePoint.id))
        ).all()
        code_to_id = {code: identifier for code, identifier in existing_rows}
        created_nodes = 0
        for code in order:
            if code in code_to_id:
                continue
            node = node_map[code]
            parent_id = code_to_id.get(node.parent_code) if node.parent_code else None
            record = KnowledgePoint(
                code=node.code,
                name=node.name,
                subject=node.subject,
                stage=node.stage,
                parent_id=parent_id,
                sort_order=order_index[code],
            )
            session.add(record)
            await session.flush()
            code_to_id[code] = record.id
            created_nodes += 1

        existing_edges = {
            (str(left), str(right))
            for left, right in (
                await session.execute(select(KnowledgeEdge.from_id, KnowledgeEdge.to_id))
            ).all()
        }
        created_edges = 0
        for edge in edges:
            from_id = code_to_id.get(edge.from_code)
            to_id = code_to_id.get(edge.to_code)
            if from_id is None or to_id is None:
                continue
            if (str(from_id), str(to_id)) in existing_edges:
                continue
            session.add(KnowledgeEdge(from_id=from_id, to_id=to_id))
            created_edges += 1

        tag_codes = {code for code, _, _ in MISTAKE_TAG_SEED}
        existing_tags = set((await session.execute(select(MistakeTag.code))).scalars())
        created_tags = 0
        for code, name, category in MISTAKE_TAG_SEED:
            if code in existing_tags or code not in tag_codes:
                continue
            session.add(MistakeTag(code=code, name=name, category=category))
            created_tags += 1

        await session.commit()
    return {
        "nodes_total": len(nodes),
        "nodes_created": created_nodes,
        "edges_total": len(edges),
        "edges_created": created_edges,
        "tags_created": created_tags,
    }


def main() -> int:
    """入口。"""
    stats = asyncio.run(seed())
    print(
        "知识点图谱种子完成："
        f"节点 {stats['nodes_total']}（新增 {stats['nodes_created']}），"
        f"依赖边 {stats['edges_total']}（新增 {stats['edges_created']}），"
        f"错因标签新增 {stats['tags_created']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
