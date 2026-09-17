# 开发环境搭建（SETUP）

> 本文档随里程碑推进持续完善；外部账号（DeepSeek Key、短信、支付、应用商店）开通步骤在 M1 起逐项补齐。

## 1. 工具链

| 工具             | 版本要求                | 说明                               |
| ---------------- | ----------------------- | ---------------------------------- |
| Node.js          | ≥ 20.11（建议 22 LTS+） | 前端与客户端                       |
| pnpm             | 9.x                     | 通过 `corepack enable pnpm` 启用   |
| Python           | 3.12                    | 后端                               |
| Docker + Compose | 最新稳定版              | 基础设施编排                       |
| Rust             | 1.75+（stable）         | Tauri 2 桌面端编译（仅桌面端需要） |

## 2. 首次初始化

```bash
corepack enable pnpm
pnpm install
cp .env.example .env        # 填入密钥；.env 不入库
```

## 3. 后端

```bash
cd services/api
python -m venv .venv
source .venv/Scripts/activate        # Windows Git Bash；Linux/macOS 用 .venv/bin/activate
pip install -e ".[dev]"
pytest                                # 单元/集成测试（自动创建 xueban_test 测试库）
uvicorn app.main:app --reload --port 8000
curl http://localhost:8000/healthz    # {"status":"ok",...}
```

数据库迁移（需要先启动 PostgreSQL）：

```bash
cd services/api
alembic upgrade head                  # 建表/升级
alembic downgrade base                # 回滚
alembic revision --autogenerate -m "描述"   # 生成增量迁移
```

### 3.1 测试环境变量

| 变量                | 默认值                                                             | 说明                             |
| ------------------- | ------------------------------------------------------------------ | -------------------------------- |
| `TEST_DATABASE_URL` | `postgresql+asyncpg://xueban:change-me@localhost:5432/xueban_test` | 测试库（用例自动创建/迁移/清空） |

覆盖率门禁：`pytest --cov=app --cov-fail-under=80`（当前实测 97%）。

### 3.2 认证与订阅（M1 已交付）

- `POST /v1/auth/register|login|sms/send|sms/login|refresh|logout`、`GET /v1/auth/me`
- 家长绑定：`POST/GET/DELETE /v1/auth/parents/children`
- 订阅：`GET /v1/billing/plans|subscription`、`POST /v1/billing/trial|checkout|checkout/{id}/mock-pay|cancel`
- 对象存储：`POST /v1/storage/presign-upload`、`GET /v1/storage/presign-download`、`DELETE /v1/storage/objects`
- 内容安全：`POST /v1/safety/check`（对话入口统一过检，M3 起被讲解/陪练复用）
- 开发环境短信验证码在接口响应 `debug_code` 返回（仅 `ENVIRONMENT=development|testing`）

### 3.3 LLM 网关与观测

- LiteLLM：`http://localhost:4000`，主模型 `deepseek-chat`，fallback 链 `qwen-plus → glm-4`（配置见 `infra/docker/litellm/config.yaml`）
- 无供应商 Key 时：请求返回明确错误码（`LLM_AUTH_FAILED` 等），服务不崩溃
- Langfuse：开发环境由 compose 自动初始化项目密钥（`pk-lf-xueban-dev` / `sk-lf-xueban-dev`），
  验证脚本：`LANGFUSE_PUBLIC_KEY=... LANGFUSE_SECRET_KEY=... python scripts/verify_langfuse_trace.py`

### 3.4 题库与 RAG（M2）

按顺序执行（幂等，可重复运行）：

```bash
cd services/api
python scripts/seed_knowledge_graph.py    # 知识点图谱 641 节点 + 前置依赖边 + 错因标签
python scripts/seed_demo_questions.py     # 生成/导出/导入演示题库（1114 条）+ 向量化
python scripts/import_questions.py --validate   # 题库校验（门禁命令）
python scripts/eval_retrieval.py          # 检索评测：30 问 recall@5
```

RAG 供应商切换（仅改环境变量）：

| 变量                  | 取值                          | 说明                                                   |
| --------------------- | ----------------------------- | ------------------------------------------------------ |
| `EMBEDDING_PROVIDER`  | `mock`（默认）/ `siliconflow` | mock 为本地词面哈希向量（离线）；siliconflow 为 bge-m3 |
| `RERANK_PROVIDER`     | `mock`（默认）/ `siliconflow` | mock 为词面重排；siliconflow 为 bge-reranker-v2-m3     |
| `SILICONFLOW_API_KEY` | —                             | 开通后填入即可启用真实语义检索                         |

### 3.5 官网 E2E 与 Lighthouse（M4）

前置：PostgreSQL 已启动且 `alembic upgrade head` 已执行（注册/试用链路需要 `users`、`billing` 表）。

```bash
# 1) 构建产物（E2E 与 Lighthouse 均基于 next start 的生产构建）
pnpm --filter @xueban/web build

# 2) 官网 E2E（自动拉起 Next 生产服务器与 uvicorn；含 axe 无障碍与 SEO 断言）
pnpm test:e2e:web

# 3) Lighthouse CI（默认移动端仿真；Perf≥90 / A11y≥95 / BP≥95 / SEO≥95）
pnpm exec lhci autorun
```

本机（Windows）注意事项：

| 事项                | 说明                                                                                                                                                                                                                                                                                                                  |
| ------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 浏览器              | 无 Chrome 时 Playwright 走 Edge 通道（`channel: "msedge"`，配置内置）；Lighthouse 通过 `CHROME_PATH` 指向 Edge：`CHROME_PATH="C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" pnpm exec lhci autorun`                                                                                                   |
| Lighthouse 清理竞态 | Windows 下 chrome-launcher 删临时 profile 偶发 `EPERM`（仅退出码，审计/断言不受影响）。确定性做法：先启动 Edge 再让 Lighthouse 接入调试端口——`msedge --headless=new --remote-debugging-port=9222 --user-data-dir=<临时目录> about:blank &`，然后 `pnpm exec lhci autorun --collect.settings.port=9222`。CI 无需此步骤 |
| API 端口            | 若 8000 落在 Hyper-V 保留端口段（`netsh interface ipv4 show excludedportrange protocol=tcp` 可查），Playwright 用 `PLAYWRIGHT_API_PORT=8090` 启动 API；此时构建需带 `NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8090`（`NEXT_PUBLIC_*` 在构建期内联）                                                                  |
| 解释器              | CI 无 `.venv` 时用 `PLAYWRIGHT_PYTHON=python` 指定后端解释器                                                                                                                                                                                                                                                          |
| 截图证据            | E2E 自动写入 `docs/verification/assets/`（首页、主色按钮、注册页、试用状态）                                                                                                                                                                                                                                          |

## 4. 基础设施（Docker）

```bash
# 在仓库根目录执行（--env-file 让 compose 读取根目录 .env）
docker compose --env-file .env -f infra/docker/docker-compose.yml up -d
docker compose -f infra/docker/docker-compose.yml ps
```

> `.env` 未创建时也可启动（compose 内置开发默认值），但建议创建后启动。

| 服务                  | 端口        | 说明                                |
| --------------------- | ----------- | ----------------------------------- |
| PostgreSQL (pgvector) | 5432        | 业务库 `xueban` + 观测库 `langfuse` |
| Redis                 | 6379        | 缓存与 arq 队列                     |
| MinIO                 | 9000 / 9001 | 对象存储（控制台 9001）             |
| LiteLLM               | 4000        | 模型网关（OpenAI 兼容）             |
| Langfuse              | 3100        | LLM 观测台                          |
| OCR（占位）           | 8100        | M8 替换为 PaddleOCR 实现            |

## 5. 外部账号开通清单（需人工办理）

| 项目             | 用途                      | 开通入口                   | 状态                |
| ---------------- | ------------------------- | -------------------------- | ------------------- |
| DeepSeek API Key | 主推理模型 deepseek-chat  | platform.deepseek.com      | 待开通（mock 先行） |
| 阿里云百炼 Key   | 备用模型 qwen-plus        | bailian.console.aliyun.com | 待开通              |
| 智谱开放平台 Key | 备用模型 glm-4            | open.bigmodel.cn           | 待开通              |
| 硅基流动 Key     | bge-m3 embedding / rerank | siliconflow.cn             | 待开通              |
| 网易易盾/数美    | 内容安全（M1 起）         | 各官网                     | 待开通（mock 先行） |
| 短信服务         | 验证码（M1 起）           | 阿里云短信等               | 待开通（mock 先行） |
| 微信支付/支付宝  | 订阅支付（M11 前）        | 各商户平台                 | 待开通（mock 先行） |
| 应用商店账号     | 安卓上架（M11）           | 应用宝/华为/小米/OPPO/vivo | 待开通              |

> 原则：mock 与真实实现以接口隔离，切换只改环境变量（见 `.env.example`）。

## 6. 常见问题

- **pnpm 未启用**：`corepack enable pnpm && corepack prepare pnpm@9 --activate`。
- **Expo 依赖告警**：在 `apps/mobile` 下执行 `npx expo install --check` 对齐 SDK 版本。
- **Docker 拉取慢**：配置镜像加速；或先只起 `postgres redis minio` 三个基础服务。
