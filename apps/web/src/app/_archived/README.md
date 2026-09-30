# 归档：家长端 / 运营后台 / Web 学习中心（P0 · REBUILD D4）

本目录是**归档区**，不产生任何 Next.js 路由（下划线开头的目录被 App Router 排除）。
归档原因见 `REBUILD.md`：

- **D4**：Web 端收缩为**纯官网 + 下载页**（获客入口），`/parents`、`/admin`、`/app`
  三个路由归档，导航移除，相应 E2E 同步下线。
- **D3**：家长端与运营后台**本次全部后置**，只聚焦学生端；桌面端是唯一主战场（D1）。

## 目录内容

| 归档路径 | 原路由 | 说明 |
| --- | --- | --- |
| `_archived/parents/` | `/parents`、`/parents/view/[token]` | 家长端（绑定孩子、管控设置、安全报告、分享看板） |
| `_archived/admin/` | `/admin` | 运营后台（题库管理、覆盖度、质量巡检、实验、指标） |
| `_archived/app/` | `/app` | Web 学习中心（原已明确写「完整功能在桌面端与移动端提供」） |

## 后端能力未下线

`services/api` 的 `/v1/parents/*`、`/v1/admin/*` 端点与 `apps/web/src/lib/api.ts`
里的对应方法**全部保留**——D3/D4 只后置**前端页面**，后端能力待后续阶段按需重接。
`apps/web/tests/api.test.ts` 仍覆盖这些方法。

## 恢复方式

需要重做家长端或运营后台时，把对应目录 `git mv` 回 `apps/web/src/app/` 即可；
页面与 `lib/api.ts` 的方法签名未做破坏性改动。
