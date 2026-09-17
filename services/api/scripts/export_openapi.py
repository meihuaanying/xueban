"""导出 OpenAPI 文档到仓库 docs/api/openapi.json。

用法（services/api 目录下）：
    .venv/Scripts/python scripts/export_openapi.py
"""

from __future__ import annotations

import json
from pathlib import Path

from app.main import create_app


def main() -> None:
    """生成并写出 OpenAPI 文档。"""
    app = create_app()
    schema = app.openapi()
    output = Path(__file__).resolve().parents[3] / "docs" / "api" / "openapi.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OpenAPI 已写出：{output}")
    print(f"标题：{schema['info']['title']} 版本：{schema['info']['version']}")
    print(f"路径数量：{len(schema['paths'])}")


if __name__ == "__main__":
    main()
