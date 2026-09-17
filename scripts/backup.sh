#!/usr/bin/env bash
# 学伴数据库备份（T10.5）：pg_dump 自定义格式，产物可被 pg_restore 还原。
#
# 用法：
#   scripts/backup.sh [备份目录]        # 默认 ./backups
# 环境变量：
#   XUEBAN_PG_CONTAINER  默认 xueban-postgres-1
#   XUEBAN_PG_USER       默认 xueban
#   XUEBAN_PG_DB         默认 xueban
set -euo pipefail

CONTAINER="${XUEBAN_PG_CONTAINER:-xueban-postgres-1}"
DB_USER="${XUEBAN_PG_USER:-xueban}"
DB_NAME="${XUEBAN_PG_DB:-xueban}"
BACKUP_DIR="${1:-backups}"

mkdir -p "$BACKUP_DIR"
STAMP="$(date +%Y%m%d_%H%M%S)"
FILE="$BACKUP_DIR/${DB_NAME}_${STAMP}.dump"

if ! docker inspect "$CONTAINER" >/dev/null 2>&1; then
  echo "错误：容器 $CONTAINER 不存在（请先启动 compose）" >&2
  exit 1
fi

docker exec "$CONTAINER" pg_dump -U "$DB_USER" -d "$DB_NAME" --format=custom --no-owner > "$FILE"

SIZE="$(wc -c < "$FILE" | tr -d ' ')"
if [ "$SIZE" -le 0 ]; then
  echo "错误：备份文件为空" >&2
  exit 1
fi

echo "BACKUP_OK $FILE ($SIZE bytes)"
echo "$FILE"
