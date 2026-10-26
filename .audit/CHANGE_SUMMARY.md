# CHANGE SUMMARY

执行完成时间: 2026-10-24T12:20:30+08:00

## 统计
- 总任务数: 16
- validated: 14
- blocked: 2
- blocked_upstream: 0

## 按任务列出

### T-001 [validated]
- 变更文件: services/api/app/schemas/auth.py; services/api/app/services/auth_service.py; services/api/app/api/routes/auth.py; services/api/tests/test_parents.py; services/api/tests/test_auth.py
- 验证: `cd services/api && pytest tests/test_parents.py tests/test_auth.py tests/test_auth_extra.py` → pass（59 passed）
- 阻塞原因: -

### T-002 [blocked]
- 变更文件: none
- 验证: `cd services/api && pytest tests/test_judge.py tests/test_grading.py` → 未执行（STOP 于修改前）
- 阻塞原因: 修复指令与当前代码结构语义冲突——指令要求在导入守卫生效后 `import runpy`，而 runpy 顶层 `import importlib.machinery` 会被 BLOCKED_MODULES（含 importlib）拦截；Python 3.12.10 实证 `python -I -S` 下抛 ImportError，accepted 路径用例必然失败。规避手段（预导入 runpy / 放行 importlib / 改黑名单）均无规格授权，未修改任何代码。详见 OBSERVATIONS.md 建议的规格重写方案。

### T-003 [validated]
- 变更文件: services/api/app/api/deps.py; services/api/tests/test_guardian.py（新建）
- 验证: `cd services/api && pytest tests/test_guardian.py tests/test_parents.py` → pass（15 passed）
- 阻塞原因: -

### T-004 [validated]
- 变更文件: services/api/app/api/routes/practice.py; tutor.py; exam.py; diagnosis.py; explainer.py; review.py; mistakes.py; coach.py（均 app/api/routes/ 下）
- 验证: `cd services/api && pytest` → pass（652 passed，全量）
- 阻塞原因: -

### T-005 [validated]
- 变更文件: services/api/app/services/admin_service.py; services/api/tests/test_admin_governance.py
- 验证: `cd services/api && pytest tests/test_admin_governance.py` → pass（12 passed）
- 阻塞原因: -

### T-006 [validated]
- 变更文件: apps/desktop/src/lib/api.ts; apps/desktop/src/lib/token-store.ts; apps/desktop/src/lib/endpoints.test.ts; apps/mobile/src/lib/api.ts; apps/mobile/src/__tests__/api.test.ts
- 验证: `pnpm --filter @xueban/desktop test && pnpm --filter @xueban/desktop typecheck` → pass；`pnpm --filter @xueban/mobile test && pnpm --filter @xueban/mobile typecheck` → pass
- 阻塞原因: -

### T-007 [validated]
- 变更文件: services/api/app/services/safety_service.py; services/api/tests/test_safety.py
- 验证: `cd services/api && pytest tests/test_safety.py` → pass（14 passed）
- 阻塞原因: -

### T-008 [validated]
- 变更文件: services/api/app/api/routes/coach.py; services/api/tests/test_coach.py
- 验证: `cd services/api && pytest tests/test_coach.py` → pass（9 passed）
- 阻塞原因: -

### T-009 [validated]
- 变更文件: services/api/app/api/routes/sync.py; services/api/tests/test_sync.py
- 验证: `cd services/api && pytest tests/test_sync.py` → pass（7 passed）
- 阻塞原因: -

### T-010 [validated]
- 变更文件: services/api/app/config.py; services/api/app/services/auth_service.py; services/api/tests/test_auth.py
- 验证: `cd services/api && pytest tests/test_auth.py tests/test_auth_extra.py` → pass（46 passed）
- 阻塞原因: -

### T-011 [validated]
- 变更文件: services/api/app/config.py; services/api/app/api/routes/tools.py; services/api/tests/test_library_cards.py
- 验证: `cd services/api && pytest tests/test_library_cards.py` → pass（6 passed）
- 阻塞原因: -

### T-012 [validated]
- 变更文件: services/api/app/services/auth_service.py；另清理本会话此前任务引入的 7 处 lint 问题（均在该来源任务 allowed_files 内）：app/api/routes/auth.py、app/schemas/auth.py、app/services/admin_service.py、tests/test_library_cards.py、tests/test_safety.py、tests/test_sync.py
- 验证: `cd services/api && ruff check . && pytest tests/test_auth.py` → pass（ruff 全绿，32 passed）
- 阻塞原因: -

### T-013 [validated]
- 变更文件: services/api/app/models/learning.py
- 验证: `cd services/api && mypy --strict app && pytest` → pass（mypy 无错误，660 passed）
- 阻塞原因: -

### T-014 [validated]
- 变更文件: packages/core/src/schemas.ts
- 验证: `pnpm --filter @xueban/core test` → pass（23 passed）
- 阻塞原因: -

### T-015 [validated]
- 变更文件: apps/desktop/src/lib/token-store.ts; apps/desktop/src/lib/token-store.test.ts
- 验证: `pnpm --filter @xueban/desktop test && pnpm --filter @xueban/desktop typecheck` → pass（202 passed）
- 阻塞原因: -

### T-016 [blocked]
- 变更文件: apps/desktop/src-tauri/tauri.conf.json（CSP 已按指令设置，指令明确不得回退为 null）
- 验证: `pnpm --filter @xueban/desktop build && pnpm test:e2e:desktop` → fail（build 通过；E2E 28 passed / 1 flaky / 2 failed，exit 1）
- 阻塞原因: 两条失败（guardian.spec.ts:89、:119）与 CSP 无关：用例经 API 绑定孩子时沿用 T-001 改造前的请求体（缺 `sms_code` → 422）。该 E2E 文件不在任何任务的 allowed_files/allowed_extra_paths 内，按硬约束不得修改，须由审计方补任务授权（修复方式已写入 OBSERVATIONS.md：两处 bind 请求体按 pytest 侧 _bind 模式补验证码）。E2E 环境准备（题库种子、数据库迁移）已在本轮完成，补任务后可直接复跑。

## 附注
- 执行环境：PostgreSQL 不可用 5432（Windows 端口排除段 5427-5526），全程使用 docker 容器 xueban-audit-pg（pgvector/pgvector:pg16，127.0.0.1:55432）；桌面 E2E 额外完成 alembic 迁移与题库种子（详见 OBSERVATIONS.md）。
- T-005/T-006/T-008/T-011 存在"首次验证因新增测试自身笔误失败 → 修正测试代码（断言语义不变）→ 重跑通过"的过程披露，见 OBSERVATIONS.md。
