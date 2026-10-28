# 学伴（XueBan）· AI 学习软件

<!-- audit-note 2026-11-06 -->
本仓库采用 MIT 许可，见 [LICENSE](LICENSE)。依赖锁定在 `pnpm-lock.yaml`，验证记录集中在 `docs/verification/`。

最后推送：2026-10-04。

以「学情闭环」（诊断 → 规划 → 讲解 → 练习 → 复盘）为核心、以守护型 AI 讲解为差异化的全端学习软件：**不直接给答案，而是把学生教到「独立做得对」**。

## 当前状态（2026-10-28）

- **高中阶段可交付自学闭环**：语数英物四科题库均达到「每知识点 ≥30 题 PUBLISHED」；新高考数学 19 题模考支持组卷、限时作答、客观题判分与解答题逐题批改。
- **题库持续生成中**：全库 PUBLISHED 9453（2026-10-28 22:40）；高中化学进行中（1052 题，27/30 已入库点达标），之后为其余选考科目 → 初中九科 → 小学；`run_content_queue.py --resume` 断点续跑。
- **Manim 渲染环境已就绪**（`scripts/check_manim.py` 自检通过），六阶段视频生成管线待实现。
- 完整进度快照见 [`docs/verification/PROGRESS_2026-10-28.md`](docs/verification/PROGRESS_2026-10-28.md)；广东 2026 对齐见 [`docs/verification/GD_2026_ALIGNMENT.md`](docs/verification/GD_2026_ALIGNMENT.md)；剩余阻塞见 [`docs/BLOCKERS.md`](docs/BLOCKERS.md)。

## 仓库结构

```
xueban/
├── apps/
│   ├── web/          # Next.js 15：官网(/) + 家长端(/parents) + 运营后台(/admin)
│   ├── desktop/      # Tauri 2 + React 19 + Vite：Windows/macOS/Linux
│   └── mobile/       # Expo (React Native)：安卓
├── packages/
│   ├── core/         # 共享 TS：API client、zod schema、类型、常量
│   ├── ui/           # 共享 React 组件库（web/desktop）
│   └── config/       # 共享 tsconfig / ESLint / 设计 tokens
├── services/
│   ├── api/          # FastAPI 主服务
│   └── ocr/          # PaddleOCR 独立容器（M8 接入）
├── infra/
│   ├── docker/       # docker-compose、LiteLLM 配置、初始化 SQL
│   └── ci/           # CI 说明（实际工作流在 .github/workflows/）
├── docs/             # SETUP / DEPLOY / RELEASE / OPS / ADR / verification
├── evals/            # promptfoo 评测集（M3 起）
├── scripts/          # 题库导入、seed、压测等脚本
└── package.json      # pnpm workspace 根
```

## 开发环境

要求：Node ≥ 20.11（本仓库用 pnpm 9）、Python 3.12、Docker（含 compose）。

```bash
corepack enable pnpm          # 启用 pnpm 9
pnpm install                  # 安装全部前端依赖
pnpm lint && pnpm typecheck   # 静态检查
pnpm test                     # 单元测试
pnpm dev                      # 并行启动 web / desktop / mobile

# 官网质量门（M4）：先构建，再 E2E，最后 Lighthouse
pnpm --filter @xueban/web build
pnpm test:e2e:web             # Playwright（转化链路 + axe + SEO），需 PostgreSQL 已迁移
pnpm exec lhci autorun        # Perf≥90 / A11y≥95 / BP≥95 / SEO≥95
```

后端：

```bash
cd services/api
python -m venv .venv && .venv/Scripts/activate   # Windows
pip install -e ".[dev]"
pytest
uvicorn app.main:app --reload --port 8000
```

基础设施（PostgreSQL/pgvector、Redis、MinIO、LiteLLM、Langfuse、OCR）：

```bash
cp .env.example .env
docker compose --env-file .env -f infra/docker/docker-compose.yml up -d
```

更多说明见 `docs/SETUP.md`。

## 工程纪律（红线）

1. 守护型讲解：任何「给答案类」功能默认不直接给完整答案，走三层提示（思路 → 关键步骤 → 全解）。
2. 防拐杖：周期性无辅助限时测评，独立能力单独建模。
3. 未成年人保护：K12 强制时长管控、内容过滤、家长可见留痕。
4. 密钥只进 `.env`，仓库内仅保留 `.env.example`。
