# 学伴（XueBan）项目交接文档 · v4

> **更新时间**：2026-09-18（UTC+8）
> **GitHub 远端**：https://github.com/meihuaanying/xueban （main 已推送；CI 8 作业全绿 run `35287350732`；Release `v0.1.0` 三平台安装包已发布）
> **仓库位置**：`C:\Users\Lenovo\Documents\Default Project\xueban`
> **规格书**：`D:\DATA\Downloads\学伴AI学习软件-项目执行规格书v1.0.md`
> **进度**：**M0–M11 全部完成**；**GitHub CI 全绿并出 v0.1.0 Release**。剩余为外部依赖闭环（模型 Key / VPS p95 复测 / 商店截图）。
> **git 状态**：`git init`（main），**仍无任何 commit**，全部文件未跟踪；commitlint + husky 已配置。
> **M10 证据**：`docs/verification/M10_2026-09-16.md` + `.logs.txt`（+13 份原始报告）
> **M11 证据**：`docs/verification/FINAL.md`（§12 逐项）+ `M11_2026-09-17_T11.1_本地验证.log` + CI 全绿 run `35287350732` + Release `v0.1.0`

---

## 0. 本轮（2026-09-17）新增完成项速览

| 任务 | 结果 | 关键证据 |
| --- | --- | --- |
| T10.2 k6 压测 | 905.6 rps、**错误率 0.00% ✅**、checks 100%；**p95=605ms ❌**（本机共享算力，B-017 待 VPS 复测）；LLM 流式首 token p95=18.16ms（mock） | `M10_2026-09-16_k6-core.{log,summary.json}`、`..._k6-llm-stream.log` |
| T10.3 ZAP baseline | **FAIL(High)=0**；Medium 3（CSP unsafe-inline×2、Anti-CSRF，已评估）| `M10_2026-09-16_zap-baseline.{md,json,html}` |
| T10.3 trufflehog | 经 ghcr.io 拉镜像成功：9713 chunks / 0 发现（**B-016 闭环**） | `..._trufflehog.{jsonl,log}` |
| T10.4 promptfoo（mock provider） | 讲解红线 **50/50**、危机话术 **10/10**（真实模型待 B-005） | `..._promptfoo-{tutor,crisis}-mock.{json,log}` |
| T11.1 生产编排 | `docker-compose.prod.yml` + `deploy.sh` + Caddyfile（api×2、web、worker、litellm、ocr、PG/Redis/MinIO，日志轮转+健康检查）；全新库 8 迁移 + 种子 + 全链路冒烟通过 | `M11_2026-09-17_T11.1_本地验证.log` |
| T11.2 部署手册 | `docs/DEPLOY.md`（服务器/域名/变量/排障/容量） | — |
| T11.3 桌面发布 | `.github/workflows/release.yml`（三平台稳定资产名 + Release）；下载页 `latest/download` 联动 | ✅ v0.1.0 Release |
| T11.4 上架材料 | `docs/RELEASE.md` + `release-assets/`（图标/文案/隐私政策/未成年人声明/办理清单/截图指引）+ `apps/mobile/eas.json` | — |
| T11.5 运维手册 | `docs/OPS.md`（模型切换实测：改 env 即生效；备份/成本/扩容/排障） | OPS §3 实测表 |
| T11.6 最终验收 | `docs/verification/FINAL.md`（§12 清单 7✅ 3🟡 0⬜）+ `docs/COMPLIANCE.md` | — |
| 规格 §10 补口 | 账号注销 `POST /v1/auth/account/delete` + `scripts/purge_deleted_accounts.py`（30 天物理删除，4 用例） | `tests/test_account_deletion.py` |
| 回归 | 后端 **449 用例 / 90.74%**；前端 184；ruff/mypy/ESLint/tsc 全绿；Web E2E 24 绿（含安全头回归） | 本轮日志 |
| **GitHub 上云** | 创建公有仓库并推送 main；**CI 8 作业全绿**（三平台桌面打包、桌面 E2E、release APK + Maestro 两条旅程、Web E2E + Lighthouse、API 449 用例） | run `35287350732` |
| **v0.1.0 Release** | 稳定资产：`XueBan-Setup-x64.exe` / `XueBan-universal.dmg` / `XueBan-x86_64.AppImage` / `XueBan-amd64.deb` + SHA256SUMS | https://github.com/meihuaanying/xueban/releases/tag/v0.1.0 |
| **B-001/B-008/B-009 闭环** | CI 实跑全绿；期间修复 9 类 CI 问题（服务容器平台限制、AppImage 图标、pytest 路径、被忽略的 app/data 源码、Maestro 驱动/ANR/键盘/网络/自清理） | `docs/BLOCKERS.md` |
| **真实缺陷修复** | E2E 暴露「移动端练习填空题无法作答」→ 补 `TextField` 输入支持并由流程覆盖 | `apps/mobile/src/screens/practice.tsx` |

---

## 1. 环境配置（不变项沿用 v2）

### 1.1 工具链

| 工具 | 版本 | 说明 |
| --- | --- | --- |
| Node.js | v24.20.0 | pnpm 9.15.9（corepack） |
| Python | 3.12.10 | 虚拟环境 `services/api/.venv` |
| Docker | 29.7.2 / Compose v5.5.0 | Desktop 已启动 |
| k6 | **2.2.0（本机安装）** | `C:\Program Files\k6\k6.exe`；容器内 `grafana/k6` 镜像已由 daocloud 镜像源拉取 |
| Rust/Java | 1.98.1 / Temurin 17 | 桌面打包 / Gradle |
| 浏览器 | 仅 Edge | Playwright `channel: "msedge"` |

### 1.2 本机网络与端口（新会话必读）

| 限制 | 影响 | 规避 |
| --- | --- | --- |
| 8000 在 Hyper-V 保留段 | API 不能监听 8000 | Web E2E API=8090、桌面 E2E=8091 |
| **Docker Hub 不可达** | 拉镜像失败 | 用 **daocloud/hub.rat.dev 镜像源** > 本地 tag（python/node/caddy/k6）；trufflehog 走 **ghcr.io**（已验证） |
| GitHub 文件下载不稳定 | Tauri MSI/三平台包 | 仅 NSIS 本机；其余交 CI（B-008） |
| 8080 被 DSH 占用 | — | 本地生产栈验证用 **8088/8443**（`CADDY_HTTP_PORT/CADDY_HTTPS_PORT`） |
| npm 镜像无 audit 端点 | pnpm audit | `--registry=https://registry.npmjs.org/` |
| 无 Android SDK/模拟器/Maestro | APK/移动 E2E | CI `mobile-apk`（B-009） |

### 1.3 基础设施

```bash
# 开发栈（8 容器；postgres max_connections=200）
docker compose -f infra/docker/docker-compose.yml up -d

# 生产式压测栈（api×4×4worker + Caddy:8096，直连开发内网）
docker compose -f infra/docker/docker-compose.loadtest.yml up -d --build

# 生产栈本地验证（独立 project，端口 8088/8443）
COMPOSE_PROJECT_NAME=xuebanprod CADDY_HTTP_PORT=8088 CADDY_HTTPS_PORT=8443 SEED_DEMO_DATA=true ./deploy.sh
```

当前运行容器：开发栈 8 个（`xueban-*`，Langfuse/ClickHouse/LiteLLM 本轮曾为压测停机，重启大栈即可恢复）；压测栈 `docker-api-*` / `docker-caddy-1`；生产验证栈 `xuebanprod-*`。**注意：压测/生产验证栈会长期驻留，清理命令见 §6。**

---

## 2. 里程碑完成情况（M0–M11 ✅）

| 里程碑 | 摘要 | 证据 |
| --- | --- | --- |
| M0–M9 | 见 v2 文档（工程基建→同步打磨） | `M0_2026-09-15.md` … `M9_2026-09-16.md` |
| M10 | 覆盖率 90.74%；k6/安全扫描/promptfoo mock/ZAP/备份演练 | `M10_2026-09-16.md` + 13 份原始报告 |
| M11 | 生产 compose+deploy.sh、DEPLOY/RELEASE/OPS/COMPLIANCE、Release 工作流与下载页联动、上架材料、FINAL 验收 | `FINAL.md`、`M11_2026-09-17_T11.1_本地验证.log` |

**当前真实数字**：后端 **449 用例 / 90.74%**（迁移 head **`d88898187de6`**）；前端 **184 用例**；Web E2E 24 / 桌面 E2E 24 / Lighthouse 100·100·96·100；k6 核心 API 905 rps（错误率 0.00%，p95 605ms → B-017）。

---

## 3. M11 交付物地图（新增/修改）

```
infra/docker/docker-compose.prod.yml     生产编排（api×2/worker/web/caddy/litellm/ocr/PG/Redis/MinIO）
infra/docker/Caddyfile                   生产反代（web+api 分流、round_robin、安全头、ACME 邮箱、MinIO 子域）
infra/docker/docker-compose.loadtest.yml 压测编排（api×4×4worker + Caddy）
deploy.sh                                一键部署（构建→健康→迁移→可选种子→状态）
apps/web/Dockerfile                      Next.js standalone 生产镜像（根上下文构建）
apps/web/src/app/download/page.tsx       下载页（稳定资产名 + latest）
apps/web/src/lib/site.ts                 RELEASE_BASE_URL 语义（GitHub latest/download）
.github/workflows/release.yml            三平台 Release（v* 标签触发，稳定资产名 + SHA256SUMS）
apps/mobile/assets/*.png                 品牌图标（脚本生成）
apps/mobile/app.json                     图标/自适应图标/splash/versionCode/权限
apps/mobile/eas.json                     EAS 构建/提交配置
services/api/scripts/make_icons.py       图标生成脚本（Pillow）
services/api/migrations/versions/d88898187de6_user_deleted_at.py   users.deleted_at
services/api/app/api/routes/auth.py      POST /v1/auth/account/delete
services/api/app/services/auth_service.py delete_account / purge_deleted_accounts
services/api/scripts/purge_deleted_accounts.py  30 天物理删除（--dry-run 演练）
services/api/tests/test_account_deletion.py     4 例
release-assets/                          上架材料包（README/store-listing/privacy/minor-protection/compliance/icons/screenshots）
docs/{DEPLOY,RELEASE,OPS,COMPLIANCE}.md  四本 T11 文档
docs/verification/FINAL.md               §12 最终验收
```

---

## 4. 成功管线（命令速查）

```bash
# 前端全仓
pnpm lint && pnpm typecheck && pnpm test && pnpm build

# 官网 E2E（先建：NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8090 pnpm --filter @xueban/web build）
pnpm test:e2e:web
pnpm test:e2e:desktop

# 后端（services/api）
.venv/Scripts/python -m pytest -q --cov=app --cov-fail-under=85
.venv/Scripts/python -m ruff check . && .venv/Scripts/python -m mypy --strict app
.venv/Scripts/python -m alembic upgrade head     # head=d88898187de6

# 压测（生产式栈 + k6；容器内 k6 消除 Windows 代理干扰）
docker compose -f infra/docker/docker-compose.loadtest.yml up -d --build
MSYS_NO_PATHCONV=1 docker run --rm --network docker_default \
  -v "$PWD/infra/k6:/scripts" grafana/k6 run /scripts/core_api.js -e K6_BASE_URL=http://caddy
MSYS_NO_PATHCONV=1 docker run --rm --network docker_default \
  -v "$PWD/infra/k6:/scripts" grafana/k6 run /scripts/llm_stream.js -e K6_BASE_URL=http://caddy -e K6_QUESTION_ID=<uuid>

# promptfoo mock 红线回归
PROMPTFOO_DISABLE_TELEMETRY=1 npx promptfoo@latest eval -c evals/tutor_mock_api.yaml
PROMPTFOO_DISABLE_TELEMETRY=1 npx promptfoo@latest eval -c evals/crisis_mock_api.yaml

# 生产栈本地验证（8088/8443；SEO 冒烟后清理：COMPOSE_PROJECT_NAME=xuebanprod docker compose ... down -v）
COMPOSE_PROJECT_NAME=xuebanprod CADDY_HTTP_PORT=8088 CADDY_HTTPS_PORT=8443 SEED_DEMO_DATA=true ./deploy.sh

# 注销清理演练
docker compose ... exec api python -m scripts.purge_deleted_accounts --dry-run
```

---

## 5. 阻塞清单（`docs/BLOCKERS.md` 全量，只列开放项）

| 编号 | 事项 | 状态/闭环动作 |
| --- | --- | --- |
| B-001 | ✅ 已闭环（CI 全绿 run `35287350732`） | — |
| B-003 | 外部 Key（DeepSeek/硅基流动/短信/支付） | 开通后只改 `.env`（模型切换实测见 OPS §3） |
| B-004 | 真实语义检索评测 | Key 到位后 `EMBEDDING_PROVIDER=siliconflow` 重跑 `eval_retrieval.py` |
| B-005 | promptfoo 真实模型全量 | `npx promptfoo eval -c evals/tutor.yaml`（mock 版已 100% 通过） |
| B-006 | FSRS 与 fsrs4anki 逐值对齐 | 引入参考调度数据集对照（T10 阶段未能收口的遗留项） |
| B-008 | ✅ 已闭环（CI 三平台出包 + v0.1.0 Release） | — |
| B-009 | ✅ 已闭环（CI release APK + Maestro 两条旅程全绿）；B-014 截图待补 | — |
| B-011~B-013 | LLM judge/OCR/口语供应商 | Key/供应商就绪后切 Provider 并回归 |
| B-015 | pnpm audit `image-size` 2 high | 构建期依赖，跟踪上游；禁止 override 到 2.x |
| **B-017** | k6 p95=605ms（本机共享算力） | VPS 部署后原样复跑 `infra/k6/core_api.js` 回填（错误率已达标） |

已闭环：B-002（截图）、B-007（LHCI 竞态）、**B-016（trufflehog，ghcr.io）**。

---

## 6. 清理与注意（新会话必做/勿踩）

```bash
# 清理本轮验证栈（释放资源；数据卷一并删除）
COMPOSE_PROJECT_NAME=xuebanprod docker compose --env-file .env -f infra/docker/docker-compose.prod.yml down -v
docker compose -f infra/docker/docker-compose.loadtest.yml down
rm -f .env   # 本地验证用的临时 .env（生产部署请重新 cp .env.example .env 并填写）
```

1. `alembic.ini` 仅 ASCII；新增模型必须写进 `app/models/__init__.py`；迁移走 upgrade→downgrade→upgrade。
2. pytest-cov 只能 `--cov=app`；测试库 `xueban_test` 由 conftest 自动建/迁移/清空。
3. 门禁顺序：`alembic downgrade base` 后必须先重播种再跑检索评测。
4. React 全仓锁 19.0.0；nativewind 4.1.23；MinIO 必须 quay.io 镜像。
5. Web 测试 JSX：web vitest 已设 `esbuild.jsx="automatic"`；移动端 jest 用 `--runInBand`。
6. pnpm overrides：`glob/postcss/uuid` 已加；**不要覆盖 `image-size`**（expo export 会崩）。
7. E2E 手机号必须随机化；桌面 E2E API=8091；Playwright 走 msedge。
8. 本机 Docker 拉镜像走镜像源再本地 tag（示例：`docker pull docker.m.daocloud.io/library/python:3.12-slim && docker tag ... python:3.12-slim`）。
9. 纯 ASGI 中间件（`app/middleware.py`）勿改回 BaseHTTPMiddleware（压测 CPU 差别明显）。
10. **本地/远端提交哈希差异（2026-09-18）**：推送期间 github.com 间歇不可达，部分提交经 GitHub API（Git Data）推送，远端 tree 与本地一致但 commit 哈希不同。网络恢复后执行 `git fetch origin && git reset --hard origin/main` 对齐；此前不要 `git push --force`。
11. 提交纪律：commitlint 生效（`feat(api): 中文描述`）；首次提交建议 `feat: 完成 M0-M11 里程碑`。

---

_交接文档完。外部阻塞闭环后，仅需按 `docs/verification/FINAL.md` §2 逐项回填证据即可。_
