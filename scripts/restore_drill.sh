#!/usr/bin/env bash
# 备份恢复演练（T10.5）：备份 → 建临时库 → 还原 → 数据一致性校验 → 清理。
#
# 用法：scripts/restore_drill.sh [备份文件]
#   未提供备份文件时先调用 scripts/backup.sh 生成。
set -euo pipefail

CONTAINER="${XUEBAN_PG_CONTAINER:-xueban-postgres-1}"
DB_USER="${XUEBAN_PG_USER:-xueban}"
DB_NAME="${XUEBAN_PG_DB:-xueban}"
SCRATCH="${XUEBAN_PG_SCRATCH:-xueban_restore_drill}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_FILE="${1:-}"

if [ -z "$BACKUP_FILE" ]; then
  BACKUP_FILE="$(bash "$SCRIPT_DIR/backup.sh" backups | tail -n 1)"
  echo "已生成备份：$BACKUP_FILE"
fi

if [ ! -s "$BACKUP_FILE" ]; then
  echo "错误：备份文件不存在或为空：$BACKUP_FILE" >&2
  exit 1
fi

psql_admin() {
  docker exec "$CONTAINER" psql -U "$DB_USER" -d postgres -v ON_ERROR_STOP=1 -tAc "$1"
}

echo "== 1) 重建演练库 $SCRATCH"
psql_admin "DROP DATABASE IF EXISTS $SCRATCH" >/dev/null
psql_admin "CREATE DATABASE $SCRATCH" >/dev/null

echo "== 2) 还原备份"
docker exec -i "$CONTAINER" pg_restore -U "$DB_USER" -d "$SCRATCH" --no-owner --exit-on-error < "$BACKUP_FILE"

count_of() {
  local database="$1" table="$2"
  docker exec "$CONTAINER" psql -U "$DB_USER" -d "$database" -tAc \
    "SELECT count(*) FROM $table" 2>/dev/null || echo "n/a"
}

echo "== 3) 一致性校验（表数量 + 关键表行数）"
count_tables() {
  local database="$1"
  docker exec "$CONTAINER" psql -U "$DB_USER" -d "$database" -tAc     "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'"
}
TABLES_SRC="$(count_tables "$DB_NAME")"
TABLES_DST="$(count_tables "$SCRATCH")"
echo "表数量：源=$TABLES_SRC 还原=$TABLES_DST"
if [ "$TABLES_SRC" != "$TABLES_DST" ]; then
  echo "错误：表数量不一致" >&2
  exit 1
fi

MISMATCH=0
for TABLE in users questions knowledge_points plan_tasks practice_records mastery_records exam_answers knowledge_cards; do
  SRC="$(count_of "$DB_NAME" "$TABLE")"
  DST="$(count_of "$SCRATCH" "$TABLE")"
  STATUS="OK"
  if [ "$SRC" != "$DST" ]; then
    STATUS="MISMATCH"
    MISMATCH=1
  fi
  printf '  %-20s 源=%-8s 还原=%-8s %s\n' "$TABLE" "$SRC" "$DST" "$STATUS"
done

# 抽样校验：最新一条题目的题干应一致
SAMPLE_SRC="$(docker exec "$CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -tAc "SELECT md5(string_agg(stem, '|' ORDER BY stem)) FROM (SELECT stem FROM questions ORDER BY created_at DESC LIMIT 20) t")"
SAMPLE_DST="$(docker exec "$CONTAINER" psql -U "$DB_USER" -d "$SCRATCH" -tAc "SELECT md5(string_agg(stem, '|' ORDER BY stem)) FROM (SELECT stem FROM questions ORDER BY created_at DESC LIMIT 20) t")"
echo "题目抽样 md5：源=$SAMPLE_SRC 还原=$SAMPLE_DST"
if [ "$SAMPLE_SRC" != "$SAMPLE_DST" ]; then
  MISMATCH=1
fi

echo "== 4) 清理演练库"
psql_admin "DROP DATABASE IF EXISTS $SCRATCH" >/dev/null

if [ "$MISMATCH" -ne 0 ]; then
  echo "DRILL_FAILED 数据一致性校验未通过" >&2
  exit 1
fi
echo "DRILL_OK 备份恢复演练通过（备份文件：$BACKUP_FILE）"
