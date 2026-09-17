# 学伴（XueBan）部署手册（T11.2）

> 目标：在**干净服务器**上按本文档即可完成部署，无需口头补充。
> 本地验证记录：`docs/verification/M11_2026-09-17_T11.1_本地验证.log`（全新数据库 8 条迁移 + 种子 + 全链路冒烟通过）。

## 1. 服务器要求

| 项 | 最低 | 推荐 | 说明 |
| --- | --- | --- | --- |
| CPU | 4 vCPU | **16 vCPU 专用核** | API 为 CPU 密集（详见 §8 性能）；压测目标 p95≤300ms@200 并发需 ≥16 核（B-017） |
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

## 6. 架构速览

```
Internet ──▶ Caddy :80/:443 ──┬── /v1/* /healthz /docs  ──▶ api:8000（2 副本 × API_WORKERS，轮询）
                              └── 其余                    ──▶ web:3000（Next.js standalone）
api ──▶ postgres（pgvector） / redis（arq 队列） / minio（附件） / litellm:4000（模型网关） / ocr:8100
worker ──▶ arq app.worker.WorkerSettings（03:00 规划重排 / 周日 22:00 周报 / 03:30 巡检）
数据卷：postgres-data / redis-data / minio-data / caddy-data / caddy-config
```

## 7. 常见故障排查

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

## 8. 性能与容量（实测基线）

- 单进程 uvicorn（Linux 容器）约 250 rps；8~16 进程约 620~905 rps（本机 16 逻辑核共享环境实测，错误率 0.00%）。
- 生产建议：≥16 专用 vCPU 时按 `API_WORKERS=4`、`DB_MAX_CONNECTIONS=200` 起步，用 k6 复测后再调。
- 完整压测方法：`infra/k6/core_api.js`（200 VU × 5 分钟）；LLM 流式首 token：`infra/k6/llm_stream.js`。

## 9. 安全基线

- 仅 80/443 暴露；数据库/Redis/MinIO API 不映射宿主端口。
- Caddy 统一注入安全头；ZAP baseline 0 High（见 `docs/verification/M10_2026-09-16_zap-baseline.md`）。
- 密钥全部经 `.env` 注入，仓库不含真实密钥（detect-secrets/trufflehog 0 发现）。
- 建议：启用云防火墙仅放行 80/443/SSH；SSH 用密钥登录；定期 `pip-audit`/`pnpm audit`（见 OPS.md）。
