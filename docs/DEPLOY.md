# 学伴（XueBan）部署手册（T11.2）

> 目标：在**干净服务器**上按本文档即可完成部署，无需口头补充。
> 本地验证记录：`docs/verification/M11_2026-09-17_T11.1_本地验证.log`（全新数据库 8 条迁移 + 种子 + 全链路冒烟通过）。

## 1. 服务器要求

| 项 | 最低 | 推荐 | 说明 |
| --- | --- | --- | --- |
| CPU | 4 vCPU | **16 vCPU 专用核** | API 为 CPU 密集（详见 §9 性能）；压测目标 p95≤300ms@200 并发需 ≥16 核（B-017） |
| 内存 | 8 GB | 16 GB | postgres/litellm/clickhouse（若自建 Langfuse）合计 |
| 磁盘 | 40 GB SSD | 100 GB SSD | 数据库 + MinIO 附件 + 日志轮转 |
| 系统 | Ubuntu 22.04+/Debian 12+ | Ubuntu 24.04 LTS | 任何支持 Docker 的 Linux |
| 软件 | Docker 24+ 与 compose v2（`docker compose version`） | 同左 | `curl -fsSL https://get.docker.com | sh` |
| 网络 | 80/443 入站开放；出站可访问 LLM 供应商 | 同左 | 证书签发需 80 端口可达（HTTP-01） |

> 国内服务器如拉取 Docker Hub 受限，可为 Docker 配置镜像加速（`/etc/docker/daemon.json` 的 `registry-mirrors`），或对 `pgvector/pgvector:pg16`、`redis:7-alpine`、`node:20-alpine`、`caddy:2-alpine`、`python:3.12-slim` 预拉取。

## 2. 域名与 DNS

| 记录 | 示例 | 用途 |
| --- | --- | --- |
| A | `learn.example.com → <服务器 IP>` | 官网 / 家长端 / 后台 / API 同域 |
| A | `minio.example.com → <服务器 IP>`（可选） | 对象存储预签名直传（无此域则官网附件上传不可用） |

备案：中国大陆服务器需完成 ICP 备案（见 `docs/COMPLIANCE.md`）。

## 3. 获取代码与配置

```bash
git clone <你的仓库地址> xueban && cd xueban
cp .env.example .env
vi .env
```

### 3.1 必填项（缺失会阻止启动）

| 变量 | 示例 | 说明 |
| --- | --- | --- |
| `SITE_ADDRESS` | `learn.example.com` | 站点域名；Caddy 自动申请/续期 HTTPS 证书。本地验证可填 `http://localhost` 并设置 `CADDY_HTTP_PORT=8088` |
| `ACME_EMAIL` | `ops@example.com` | Let's Encrypt 账号邮箱（证书到期提醒） |
| `POSTGRES_PASSWORD` | 随机 32 位 | 数据库密码 |
| `MINIO_ROOT_PASSWORD` | 随机 32 位 | 对象存储管理密码 |
| `LITELLM_MASTER_KEY` | `sk-` 开头随机串 | LLM 网关密钥（API 与 LiteLLM 共享） |
| `JWT_SECRET` | `openssl rand -hex 32` | 访问令牌签名密钥 |
| `DEEPSEEK_API_KEY` | `sk-...` | 主模型（未填则 `LLM_PROVIDER=litellm` 下讲解功能不可用；可先用 `LLM_PROVIDER=mock` 离线验收） |

### 3.2 常用可选项

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `LLM_PROVIDER` | `litellm` | `mock` 用于离线演示（讲解为确定性文本） |
| `DASHSCOPE_API_KEY` / `ZHIPU_API_KEY` | 空 | LiteLLM fallback 链（qwen-plus → glm-4） |
| `SILICONFLOW_API_KEY` | 空 | 需要真实语义检索时设置 `EMBEDDING_PROVIDER=siliconflow`、`RERANK_PROVIDER=siliconflow` |
| `API_WORKERS` | `2` | 每副本 uvicorn 进程数；总进程 = 2 副本 × 该值；须满足 `2×API_WORKERS×(DB_POOL_SIZE+DB_MAX_OVERFLOW) < DB_MAX_CONNECTIONS` |
| `DB_MAX_CONNECTIONS` | `200` | PostgreSQL 最大连接数 |
| `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` | `10` / `20` | 每副本连接池 |
| `MINIO_HOST` | `minio.localhost` | MinIO 公网子域（预签名直传）；无则保持默认 |
| `CORS_ALLOW_ORIGINS` | 含 localhost | 生产同域反代时可留空或仅保留站点域名 |
| `LANGFUSE_*` | 空 | 观测服务；未配置时自动降级不影响主流程 |
| `ALERT_WEBHOOK_URL` | 空 | 运营告警（企业微信/钉钉机器人） |
| `NEXT_PUBLIC_RELEASE_BASE_URL` | 占位 | 桌面端安装包下载地址（见 `docs/RELEASE.md`） |
| `XUEBAN_VERSION` | `latest` | 镜像 tag，发布时建议改为版本号 |

## 4. 部署

```bash
./deploy.sh                       # 构建 → 启动 → 等 PG → 迁移 → 状态
SEED_DEMO_DATA=true ./deploy.sh   # 首次部署并播种知识图谱与演示题库（幂等）
```

`deploy.sh` 依次执行：`docker compose up -d --build` → 等待 postgres 健康 → `alembic upgrade head` → （可选）种子 → `docker compose ps`。
首次构建约 5~15 分钟（取决于网络与机器性能），满足「30 分钟内服务全通」的前提是镜像拉取顺畅。

验证：

```bash
curl -fsS https://$SITE_ADDRESS/healthz        # {"status":"ok",...}
curl -fsS -o /dev/null -w '%{http_code}\n' https://$SITE_ADDRESS/   # 200（官网首页）
```

浏览器打开 `https://<域名>/`（官网首页）、`/app`（学习端）、`/parents`（家长端）、`/admin`（运营后台，需管理员账号）。

## 5. 日常运维

```bash
# 查看服务
docker compose --env-file .env -f infra/docker/docker-compose.prod.yml ps
docker compose --env-file .env -f infra/docker/docker-compose.prod.yml logs -f api
docker compose --env-file .env -f infra/docker/docker-compose.prod.yml logs --since 1h caddy

# 更新发布
git pull
docker compose --env-file .env -f infra/docker/docker-compose.prod.yml up -d --build
docker compose --env-file .env -f infra/docker/docker-compose.prod.yml exec api alembic upgrade head

# 备份 / 恢复
bash scripts/backup.sh                 # 产出 backups/xueban_<时间戳>.dump
bash scripts/restore_drill.sh          # 演练：备份→临时库→一致性校验
# 实际恢复：pg_restore -d xueban --clean --if-exists backups/<file>.dump（先停 api/worker）
```

更多运维主题（日志、模型切换、成本控制、扩缩容）见 `docs/OPS.md`。

## 6. 全学段内容扩展（2026-10）运行手册

> 范围：小学/初中/高中三科（语文、数学、英语）课程树与题库。课程树已覆盖
> `grade1`~`grade12`（三科每个年级均有点位，合计 488 个知识点）；题库按知识点
> 逐个补齐，受网关用量窗口约束，可反复断点续跑。

### 6.1 数据库迁移

```bash
cd services/api
alembic upgrade head
```

当前 `head` 即 `e8a3c5f2b7d1`（可用 `alembic heads` 复核），迁移内容：

- `knowledge_points` 新增 `grade` 列（`varchar(8)`，可空）与
  `ix_knowledge_points_grade` 索引；旧自动展开图谱的知识点没有年级，保持 `NULL`。
- 按课程 JSON 的 `code` 回填课程树知识点的 `grade` 与 `stage`（小学 `primary`、
  初中 `junior`、高中 `senior`）。
- 历史 `stage='grade1_2'` 统一改写为 `primary`，`knowledge_points` 与 `questions`
  两张表都改。只改知识点会让旧小学题按 `Question.stage` 精确过滤时永久查不到，
  且管线会把它们算作「已有题」而跳过补题。
- 迁移末尾自检两张表的 `grade1_2` 残留行数，非 0 直接抛 `RuntimeError` 中止迁移，
  避免「迁移成功但数据不可达」的静默失败。

### 6.2 模型配置

本机开发/验证环境的 `.env` 已统一切到 OpenCode Go 网关（`.env.example` 仍是
本地 LiteLLM 默认值，上线前以实际 `.env` 为准）：

```dotenv
LITELLM_BASE_URL=https://opencode.ai/zen/go/v1
LITELLM_MASTER_KEY=oc_sk_...
LLM_DEFAULT_MODEL=deepseek-v4.1-flash
CONTENT_GENERATION_MODEL=deepseek-v4.1-flash
CONTENT_JUDGE_MODEL=deepseek-v4.1-flash
```

- 网关按 **5 小时用量窗口** 计费；窗口耗尽返回 HTTP 429（网关错误体为
  `GoUsageLimitError`，应用侧统一映射为 `LLM_RATE_LIMITED`）。
- **生产启动校验**：`ENVIRONMENT=production` 时，API 与 worker 启动会拒绝
  LLM/内容安全/embedding/rerank/TTS/口语任一仍为 `mock`，也拒绝默认 JWT 密钥。
  部署前必须把 `.env` 里这些 provider 换成真实供应商，否则容器直接退出。
- 429 先按 `LLM_RATE_LIMIT_RETRIES`（默认 5）与
  `LLM_RATE_LIMIT_BACKOFF_SECONDS`（默认 8.0）退避重试；配置了
  `LLM_FALLBACK_BASE_URL` / `LLM_FALLBACK_MASTER_KEY` / `LLM_FALLBACK_MODEL`
  时，主网关重试预算耗尽后自动切备用网关。
- 注意：生产编排 `infra/docker/docker-compose.prod.yml` 会把 `LITELLM_BASE_URL`
  覆盖为 `http://litellm:4000`。容器内跑管线时模型由 LiteLLM 配置决定；要直连
  OpenCode Go，可在该编排文件里改回，或用
  `docker compose run --rm -e LITELLM_BASE_URL=https://opencode.ai/zen/go/v1 api ...`
  临时覆盖（见 §6.5）。

### 6.3 题库生成

```bash
cd services/api && .venv/Scripts/python scripts/run_content_pipeline.py --subjects math --grades grade10,grade11,grade12 --target 30 --interval 1.0
```

- 按学科/年级换参数：`--subjects` 逗号分隔 `chinese,math,english`；`--grades`
  逗号分隔 `grade1`~`grade12`。默认 `--subjects math,chinese,english`、
  `--grades grade1,grade2`、`--target` 取 `CONTENT_MIN_PER_POINT`（默认 30）、
  `--interval` 默认 1.5 秒。Linux/macOS 把 `.venv/Scripts/python` 换成
  `.venv/bin/python`。
- **全学段队列**（推荐）：`scripts/run_content_queue.py --resume`。按「高中语数英 →
  选考六科 → 初中九科 → 小学」分段，每段完成写断点；配额窗口耗尽退出码 2，
  窗口恢复后同一命令继续。
- **按题型专项补题**（19 题模考必需）：普通队列按知识点总题量推进，
  choice/fill 先达标后整点会被跳过，多选/解答题不会自然补出来。用专项脚本：

  ```bash
  cd services/api
  .venv/Scripts/python scripts/backfill_qtypes.py --qtype multi_choice --target 3
  .venv/Scripts/python scripts/backfill_qtypes.py --qtype short_answer --target 2
  ```

  只按目标题型计数、生成与入库；幂等，重跑自动跳过已达标知识点。
- **断点续跑**：以知识点为粒度。只统计 `PUBLISHED` 且 `stage` 与目标年级一致的题，
  达到 `--target` 即跳过；已有题同时作为判重种子，重跑不会重复生成。
- **限额提前中止**：连续 2 个知识点都因 `LLM_RATE_LIMITED` 失败时立即停止，
  JSON 汇总里的 `aborted_reason` 写明原因（「配额窗口耗尽……」）。窗口重置后
  重跑同一命令即可，已达标知识点自动跳过。
- 入库按 `HUMAN_REVIEW_RATE`（默认 0.05）抽 5% 写成 `REVIEW`，其余 `PUBLISHED`；
  只有 `PUBLISHED` 计入目标题量。

### 6.4 判题批量化

- `CONTENT_JUDGE_BATCH_SIZE`（默认 5）：非数学题先过规则通道，通过后按该批大小
  送 LLM judge；数学**客观题**只走规则 + SymPy，不进 judge。数学多选题（答案为
  `AC`）与解答题（答案为步骤文字）不是数值表达式，规则不做 SymPy 对拍，改走
  judge——否则这两类题会被 100% 误拒。
- 批量返回的题号集合必须严格等于 `{1..N}`。缺项、多余或 0 基错位会**整批作废**，
  该批每道题回退单题 judge，绝不默认放行。解析器容忍 ```json 包裹、前后废话与
  裸数组（`[{...}]`）；仍然失配时日志会带原始输出前 160 字便于定位。调小该值可
  降低整批作废概率，代价是 judge 调用数上升（配额窗口下更费额度）。

### 6.5 部署栈同步（xuebanprod）

新镜像上线后必须先把库迁到 `head`，再按年级重跑题库管线：

```bash
COMPOSE_PROJECT_NAME=xuebanprod docker compose --env-file .env -f infra/docker/docker-compose.prod.yml exec api alembic upgrade head
COMPOSE_PROJECT_NAME=xuebanprod docker compose --env-file .env -f infra/docker/docker-compose.prod.yml exec api python scripts/run_content_pipeline.py --subjects math --grades grade10,grade11,grade12 --target 30 --interval 1.0
```

> 容器内 `LITELLM_BASE_URL` 被编排覆盖为 `http://litellm:4000`（见 §6.2）。
> 若要让管线直接使用 OpenCode Go 的 `deepseek-v4.1-flash`，可临时覆盖该变量
> （`LITELLM_MASTER_KEY` 仍从 `.env` 注入，填 OpenCode Zen 的 `oc_sk_...`）：
>
> ```bash
> COMPOSE_PROJECT_NAME=xuebanprod docker compose --env-file .env -f infra/docker/docker-compose.prod.yml run --rm -e LITELLM_BASE_URL=https://opencode.ai/zen/go/v1 api python scripts/run_content_pipeline.py --subjects math --grades grade10,grade11,grade12 --target 30 --interval 1.0
> ```

## 7. 架构速览

```
Internet ──▶ Caddy :80/:443 ──┬── /v1/* /healthz /docs  ──▶ api:8000（2 副本 × API_WORKERS，轮询）
                              └── 其余                    ──▶ web:3000（Next.js standalone）
api ──▶ postgres（pgvector） / redis（arq 队列） / minio（附件） / litellm:4000（模型网关） / ocr:8100
worker ──▶ arq app.worker.WorkerSettings（03:00 规划重排 / 周日 22:00 周报 / 03:30 巡检）
数据卷：postgres-data / redis-data / minio-data / caddy-data / caddy-config
```

## 8. 常见故障排查

| 现象 | 排查 | 处理 |
| --- | --- | --- |
| `https://域名` 证书报错 | `docker logs <caddy 容器>` 看 ACME 日志；确认 80/443 可达、DNS 已生效 | 修正 DNS/防火墙后 `docker compose restart caddy`；证书状态在 `caddy-data` 卷 |
| 页面 503 `no upstreams available` | `docker compose ps` 看 api 是否 healthy；`logs api` | 冷启动约 15s 内属正常；持续则查 api 日志（多为 DATABASE_URL/JWT_SECRET 缺失） |
| api 反复重启 | `logs api` 中 `pydantic_settings` 报错 | 对照 §3.1 必填项补齐 `.env` |
| 迁移失败 | `logs postgres`；`alembic current` | 检查 `POSTGRES_PASSWORD` 是否与卷中初始化密码一致（改密需重建数据卷或改库内密码） |
| 讲解请求报模型错误 | `logs litellm`；确认 `DEEPSEEK_API_KEY` 与 `LITELLM_MASTER_KEY` | Key 无效时先在 `.env` 设 `LLM_PROVIDER=mock` 维持可用，再更换 Key |
| 附件上传 403/超时 | 确认 `MINIO_HOST` 已备案解析且 Caddy 有对应站点块；MinIO 桶由 `minio-init` 创建 | 修 DNS/证书后重试；桶缺失可重跑 `docker compose up minio-init` |
| 磁盘占用增长 | `docker system df`；日志已按 20MB×5 轮转 | 清理旧镜像 `docker image prune -f`；备份文件保留策略见 OPS.md |
| 压测 p95 不达标 | 对照 B-017；`docker stats` 观察 api CPU | 提升 `API_WORKERS`/服务器规格；用 `infra/k6/core_api.js` 复测 |

## 9. 性能与容量（实测基线）

- 单进程 uvicorn（Linux 容器）约 250 rps；8~16 进程约 620~905 rps（本机 16 逻辑核共享环境实测，错误率 0.00%）。
- 生产建议：≥16 专用 vCPU 时按 `API_WORKERS=4`、`DB_MAX_CONNECTIONS=200` 起步，用 k6 复测后再调。
- 完整压测方法：`infra/k6/core_api.js`（200 VU × 5 分钟）；LLM 流式首 token：`infra/k6/llm_stream.js`。

## 10. 安全基线

- 仅 80/443 暴露；数据库/Redis/MinIO API 不映射宿主端口。
- Caddy 统一注入安全头；ZAP baseline 0 High（见 `docs/verification/M10_2026-09-16_zap-baseline.md`）。
- 密钥全部经 `.env` 注入，仓库不含真实密钥（detect-secrets/trufflehog 0 发现）。
- 建议：启用云防火墙仅放行 80/443/SSH；SSH 用密钥登录；定期 `pip-audit`/`pnpm audit`（见 OPS.md）。
