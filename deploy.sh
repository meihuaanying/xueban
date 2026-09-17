#!/usr/bin/env bash
# 学伴一键部署（T11.1）
# 用法：cp .env.example .env && vi .env && ./deploy.sh
# 可选：SEED_DEMO_DATA=true ./deploy.sh（首次部署播种知识图谱与演示题库）
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

COMPOSE_FILE="infra/docker/docker-compose.prod.yml"
COMPOSE=(docker compose --env-file .env -f "$COMPOSE_FILE")

if [[ ! -f .env ]]; then
  echo "✗ 缺少 .env —— 请先执行：cp .env.example .env 并填写关键项（见 docs/DEPLOY.md）" >&2
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "✗ 未安装 Docker（需 Docker 24+ 与 compose v2）" >&2
  exit 1
fi

# 载入 .env（供 web 构建变量与域名推导使用）
set -a
# shellcheck disable=SC1091
source ./.env
set +a

if [[ -z "${SITE_ADDRESS:-}" ]]; then
  echo "✗ .env 未设置 SITE_ADDRESS（站点域名，如 learn.example.com）" >&2
  exit 1
fi

if [[ "$SITE_ADDRESS" == http* ]]; then
  SITE_URL="${SITE_ADDRESS%/}"
else
  SITE_URL="https://${SITE_ADDRESS}"
fi
# 官网与 API 同域（Caddy 反代）：构建期公开变量默认指向站点域名
if [[ -z "${NEXT_PUBLIC_SITE_URL:-}" || "$NEXT_PUBLIC_SITE_URL" == *localhost* ]]; then
  export NEXT_PUBLIC_SITE_URL="$SITE_URL"
fi
if [[ -z "${NEXT_PUBLIC_API_BASE_URL:-}" || "$NEXT_PUBLIC_API_BASE_URL" == *localhost* ]]; then
  export NEXT_PUBLIC_API_BASE_URL="$SITE_URL"
fi
export NEXT_PUBLIC_RELEASE_BASE_URL="${NEXT_PUBLIC_RELEASE_BASE_URL:-https://dl.xueban.example.com/releases/latest}"

echo "==> [1/5] 构建并启动容器（api×2 + web + worker + caddy + postgres/redis/minio/litellm/ocr）"
"${COMPOSE[@]}" up -d --build

echo "==> [2/5] 等待 PostgreSQL 健康"
for _ in $(seq 1 60); do
  state="$("${COMPOSE[@]}" ps postgres --format '{{.Health}}' 2>/dev/null | head -1 || true)"
  if [[ "$state" == "healthy" ]]; then
    break
  fi
  sleep 2
done
if [[ "$state" != "healthy" ]]; then
  echo "✗ PostgreSQL 未在预期时间内健康，请查看：${COMPOSE[*]} logs postgres" >&2
  exit 1
fi

echo "==> [3/5] 执行数据库迁移（alembic upgrade head）"
"${COMPOSE[@]}" exec -T api alembic upgrade head

if [[ "${SEED_DEMO_DATA:-false}" == "true" ]]; then
  echo "==> [4/5] 播种知识图谱与演示题库（幂等）"
  "${COMPOSE[@]}" exec -T api python -m scripts.seed_knowledge_graph
  "${COMPOSE[@]}" exec -T api python -m scripts.seed_demo_questions
else
  echo "==> [4/5] 跳过数据播种（如需：SEED_DEMO_DATA=true ./deploy.sh）"
fi

echo "==> [5/5] 服务状态"
"${COMPOSE[@]}" ps

cat <<EOF

✓ 部署完成
  站点（官网/家长端/后台）：${SITE_URL}
  API 健康检查：           ${SITE_URL}/healthz
  MinIO 控制台：           ssh 隧道到 9001 端口后访问（生产不直接暴露）

常用命令：
  ${COMPOSE[*]} ps
  ${COMPOSE[*]} logs -f api
  ${COMPOSE[*]} exec api alembic upgrade head
EOF
