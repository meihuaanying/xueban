# 学伴（XueBan）运维手册（T11.5）

> 配套：`docs/DEPLOY.md`（部署）、`scripts/backup.sh` / `scripts/restore_drill.sh`（备份演练）。
> 本手册中的「实测」均为本机生产编排（`docker-compose.prod.yml`）实跑记录，见 `docs/verification/M11_2026-09-17_T11.1_本地验证.log`。

## 1. 日志

### 1.1 位置与轮转

- 所有容器输出结构化 JSON 到 stdout，由 Docker `json-file` 驱动落盘，**单文件 20MB × 5 份**自动轮转（compose 中 `x-logging`）。
- API 访问日志字段：`ts / level / logger=xueban.access / message / trace_id / method / path / status / elapsed_ms`；每个响应带 `X-Trace-Id` 头，可与前端/网关日志串联。

```bash
COMPOSE="docker compose --env-file .env -f infra/docker/docker-compose.prod.yml"

$COMPOSE logs -f api                    # 实时跟踪 API（2 副本合并）
$COMPOSE logs --since 1h caddy          # 网关（ERROR 级）
$COMPOSE logs api | grep '"status": 5'  # 5xx 排查
$COMPOSE logs api | grep <trace_id>     # 按 trace 串联单次请求
```

### 1.2 应用内定时任务（arq worker）

| 时间 | 任务 | 说明 |
| --- | --- | --- |
| 每日 03:00 | 学习路径重排 | `planner_service` |
| 每周日 22:00 | 学习周报生成 | `report_service` |
| 每日 03:30 | 题库/解析质量巡检 | 超阈值（默认 3%）触发 `ALERT_WEBHOOK_URL` 告警 |

查看：`$COMPOSE logs -f worker`。

## 2. 备份与恢复

```bash
bash scripts/backup.sh                 # pg_dump 自定义格式 → backups/xueban_<时间戳>.dump
bash scripts/restore_drill.sh          # 演练：备份 → 临时库 → pg_restore → 一致性校验 → 清理（DRILL_OK）
```

**生产恢复步骤**（会覆盖当前数据，先停写）：

```bash
$COMPOSE stop api worker
docker exec -i <postgres容器> pg_restore -U xueban -d xueban --clean --if-exists < backups/xueban_xxx.dump
$COMPOSE start api worker
```

建议：每日 02:30 由 crontab 执行 `backup.sh`，保留 14 天；备份文件异地（对象存储）同步。MinIO 附件数据卷（minio-data）随主机快照备份。

### 数据保留与注销清理（规格书 §10）

- 用户注销：客户端/接口 `POST /v1/auth/account/delete`（校验密码 → 匿名化手机号/nickname/密码 + 停用 + 吊销全部刷新令牌）。
- 物理删除：`docker compose exec api python -m scripts.purge_deleted_accounts --dry-run`（演练）→ 去掉 `--dry-run` 执行；默认删除注销满 30 天的账号，子表按外键级联清理。
- 建议 crontab 每日 04:00 执行（先 `--dry-run` 留档日志，再执行清理）。

## 3. 模型切换（实测：仅改环境变量）

`LLM_PROVIDER` 切换实测（同一 API 镜像，改 `.env` 后 `docker compose up -d api`，无需改代码/重建镜像）：

| 操作 | 实测结果 | 记录 |
| --- | --- | --- |
| `LLM_PROVIDER=mock` | 讲解第 1 层返回确定性文本「思路提示：先看题目的已知条件与所求量…」（2 副本均一致） | 本地验证日志 §3 |
| `LLM_PROVIDER=litellm`（无有效 Key） | 返回明确错误码与提示：`{"code":"LLM_AUTH_FAILED","message":"模型网关鉴权失败：请检查 LITELLM_MASTER_KEY 或供应商 API Key…"}`（HTTP 503，服务不崩） | 本节实测 |
| LiteLLM 降级链（无 Key 时直连验证） | `deepseek-chat` 401 → 自动 fallback `qwen-plus` → `glm-4`，错误信息含 `Available Model Group Fallbacks` | 本节实测 |

切换 **主模型**（同一网关内）：

```bash
# 方式一：改 API 默认模型（仅影响新请求）
LLM_DEFAULT_MODEL=qwen-plus  # .env → docker compose up -d api
# 方式二：调 LiteLLM 配置（模型组/降级链）
vi infra/docker/litellm/config.yaml   # 修改 model_list
docker compose --env-file .env -f infra/docker/docker-compose.prod.yml up -d litellm
```

切换 **Embedding/检索**：`EMBEDDING_PROVIDER=mock|siliconflow`、`RERANK_PROVIDER`（填 `SILICONFLOW_API_KEY` 后生效，见 B-004）。

## 4. 成本控制（LiteLLM 预算与告警）

1. **预算告警**（LiteLLM 支持 `budget_duration`/`max_budget`）：在 `infra/docker/litellm/config.yaml` 为模型组加预算，或接入 LiteLLM 的 `/spend/*` 报表接口；运营侧接 `ALERT_WEBHOOK_URL`。
2. **峰谷调度**：批量任务（周报、巡检、微课生成）已排至凌晨；如成本超预算 80%，将 `llm_default_model` 降级为 `qwen-plus`（峰谷计价）。
3. **缓存**：LiteLLM 支持响应缓存（Redis）；启用后相同提示词命中缓存不重复计费。
4. **用量观测**：Langfuse（可选，`LANGFUSE_*`）按用户/trace 统计 token 与费用；未接入时以 LiteLLM 日志为准。
5. **降级顺序**（规格书风险预案）：陪练 → 工具 → V3 批改；核心闭环（F-01~F-31）不降级。

## 5. 扩容与性能

- **API 扩容**：`docker compose ... up -d --scale api=4`（本机验证建议先调 `LB` 与 `DB_MAX_CONNECTIONS`；总连接 = 副本数 × (DB_POOL_SIZE+DB_MAX_OVERFLOW)）。
- **压测复测**（交付必做，B-017）：
  ```bash
  k6 run infra/k6/core_api.js -e K6_BASE_URL=https://learn.example.com -e K6_VUS=200 -e K6_DURATION=5m
  ```
  目标：p95 ≤300ms、错误率 ≤0.1%；LLM 流式首 token：`infra/k6/llm_stream.js`（p95 ≤3s）。
- **慢查询**：`docker exec <postgres> psql -U xueban -d xueban -c "SELECT pid, now()-query_start AS dur, query FROM pg_stat_activity WHERE state='active' AND now()-query_start > interval '1s'"`。

## 6. 安全维护（每月）

```bash
services/api/.venv/Scripts/python -m pip_audit          # Python 依赖（Windows 开发机）
pnpm audit --prod --registry=https://registry.npmjs.org/ # 前端依赖（image-size 2 high 为已知 B-015）
docker exec <api> pip list --outdated                    # 容器内版本巡检
docker run --rm -v "$PWD:/repo:ro" ghcr.io/trufflesecurity/trufflehog:latest filesystem /repo --no-update
```

ZAP baseline 复扫（官网）：见 `docs/verification/M10_2026-09-16_zap-baseline.md` 的命令（docker 镜像 + 生产站点地址）。

## 7. 故障处置速查

| 症状 | 首要动作 | 备注 |
| --- | --- | --- |
| 全站 502/503 | `$COMPOSE ps` → 上游是否 healthy | Caddy 冷启动 15s 内 503 属正常 |
| API 报 500 增多 | `$COMPOSE logs api | grep 500`；看 DB 连接与 trace_id | 连接池耗尽时调 `DB_POOL_SIZE`/`DB_MAX_CONNECTIONS` |
| 模型全挂 | `$COMPOSE logs litellm`；临时 `LLM_PROVIDER=mock` 保底 | Key 恢复后切回 |
| Redis 队列积压 | `docker exec <redis> redis-cli LLEN arq:queue` | 重启 worker；检查定时任务耗时 |
| 磁盘告急 | `docker system df`；清理旧镜像与备份 | 日志已轮转；备份保留策略见 §2 |
| 证书过期 | `$COMPOSE logs caddy | grep -i acme` | Caddy 自动续期；确认 80 端口可达 |
| 迁移中断 | `$COMPOSE exec api alembic current` / `alembic history` | 不要手动改表；按迁移脚本回滚或前滚 |

## 8. 值班交接清单

- [ ] `$COMPOSE ps` 全绿、`/healthz` 200
- [ ] 近 24h 5xx 比例 <0.1%（日志采样）
- [ ] backup.sh 当日产物存在且 >1MB；每周跑一次 restore_drill.sh
- [ ] LiteLLM/Langfuse 成本在预算内；巡检告警无未处理项
- [ ] 待发布项已走 `docs/DEPLOY.md` §5 更新流程并留存迁移记录
