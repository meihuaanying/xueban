# AUDIT_INDEX

> intent_auto_generated: false（意图来源为仓库内 README.md 与 docs/，非自动推断；所有 E-编号为确定置信度）

## 1. 元信息

- 审查时间：2026-10-24
- PROJECT_ROOT: C:\Users\Lenovo\Documents\Default Project\xueban
- DISCOVERY.md: C:\Users\Lenovo\Documents\Default Project\xueban\.audit\DISCOVERY.md
- detected_stack: pnpm 9 + turbo monorepo（Tauri 2/React 19 桌面端、Next.js 15 官网、Expo 移动端、packages/core|ui|config）+ Python 3.12 FastAPI + SQLAlchemy 2(async)/Alembic + PostgreSQL/pgvector + MinIO + ARQ
- baseline_commands:
  - test: `pnpm --filter @xueban/<pkg> test`（desktop/web=vitest, mobile=jest, core/ui=vitest）；根脚本 `pnpm test:e2e:web`、`pnpm test:e2e:desktop`；services/api 下 `pytest`
  - lint: `pnpm --filter @xueban/<pkg> lint`；services/api 下 `ruff check .`
  - typecheck: `pnpm --filter @xueban/<pkg> typecheck`；services/api 下 `mypy --strict app`
  - build: `pnpm build`（turbo run build）；原子：`pnpm --filter @xueban/<pkg> build`
  - （无 UNKNOWN 项）

## 2. 预期行为清单摘要

| 编号 | 一句话 | 来源 |
| --- | --- | --- |
| E-001 | 守护型讲解：给答案类功能不直接给完整答案，走三层提示（思路→关键步骤→全解） | README.md §工程纪律红线 1 |
| E-002 | 防拐杖：无辅助测评期间服务端拒绝提示类接口（solo_locked） | README.md 红线 2；docs/adr/001-schema.md §关键字段约定 |
| E-003 | 未成年人保护：K12 强制时长管控、内容过滤、家长可见留痕 | README.md 红线 3 |
| E-004 | 密钥只进 .env，仓库内仅保留 .env.example | README.md 红线 4 |
| E-005 | JWT access 15min / refresh 30d 轮换、角色 RBAC、家长不可看他人孩子数据 | docs/COMPLIANCE.md §5 |
| E-006 | 监护人同意：注册/订阅/敏感功能需监护人同意 | docs/COMPLIANCE.md §2 |
| E-007 | 数据删除权：注销=匿名化+停用+吊销令牌，30 天物理删除 | docs/COMPLIANCE.md §2 |
| E-008 | 内容安全：SAFETY_PROVIDER=mock\|yidun 可切换，失败降级本地词表不阻塞主流程 | docs/COMPLIANCE.md §1.2 |
| E-009 | 对话留痕：chat_messages 全量落库，家长端可查（F-44） | docs/COMPLIANCE.md §1.2 |
| E-010 | 管理员操作审计：audit_logs 表关键操作留痕 | docs/COMPLIANCE.md §5 |
| E-011 | 日志脱敏：access 日志不含手机号/正文等敏感信息 | docs/COMPLIANCE.md §2 |
| E-012 | 数据库约定：UUID 主键、TIMESTAMPTZ、枚举 VARCHAR+CHECK、约束命名、Alembic autogenerate 稳定、禁改历史迁移 | docs/adr/001-schema.md §决策 |
| E-013 | 心理安全红线：危机识别为规则层+固定求助话术，不扮演心理咨询师 | docs/COMPLIANCE.md §1.3 |
| E-014 | 未成年人默认关闭自动续费入口 | docs/COMPLIANCE.md §4 |
| E-015 | 统一错误契约 {code, message, trace_id}，trace_id 可为 null | services/api/app/main.py `_error_payload`（代码显式契约） |
| E-016 | 判题沙箱「隔离执行 + 资源/超时限制」（F-26） | services/api/app/services/judge_service.py 模块 docstring（代码显式契约） |

## 3. 任务摘要表（depends_on 唯一真相源）

| ID | 严重性 | depends_on |
| --- | --- | --- |
| T-001 | P0 | none |
| T-002 | P1 | none |
| T-003 | P1 | none |
| T-004 | P1 | [T-003] |
| T-005 | P1 | none |
| T-006 | P1 | none |
| T-007 | P1 | none |
| T-008 | P2 | none |
| T-009 | P2 | none |
| T-010 | P2 | none |
| T-011 | P2 | none |
| T-012 | P2 | none |
| T-013 | P2 | none |
| T-014 | P2 | none |
| T-015 | P2 | none |
| T-016 | P2 | none |

## 4. 执行顺序（层内拓扑排序）

### P0 层
1. T-001

### P1 层
1. T-002
2. T-003
3. T-004 (depends_on: T-003)
4. T-005
5. T-006
6. T-007

### P2 层
1. T-008
2. T-009
3. T-010
4. T-011
5. T-012
6. T-013
7. T-014
8. T-015
9. T-016

## 5. 统计

- P0：1 个任务
- P1：6 个任务
- P2：9 个任务

## 6. 备注（不构成任务的观察，无对应基线验证命令或未复现）

- `docs/api/openapi.json` 为自动生成快照（`services/api/scripts/export_openapi.py` 导出），滞后实际路由 46 个路径（admin/coach/parents/explainer/library/cards/tools/sync 等未收录）。属生成物陈旧，重新导出无基线验证命令，不立任务；建议随 M 里程碑重新导出。
- `app/services/math_verify.py:52` 对用户可控文本调用 sympy `parse_expr(evaluate=True)`，仅靠字符白名单 `_MATH_CHARS` 防护；经分析 auto_symbol 变换会未知名称转 Symbol、字符白名单禁引号/方括号，未构造出可用载荷，未复现，不立任务。
- 家长看板分享 token（`parent_service.py` ReportShare.token）明文入库、明文比对，有 30 天有效期与吊销机制；列为观察。
- Explainer 降级路径在消毒失败时存服务端模板原文（`explainer_service.py:513`），模板内 LLM 文本经 `html_lib.escape`，风险可控；列为观察。
