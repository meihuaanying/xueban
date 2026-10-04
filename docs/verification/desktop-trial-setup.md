# 妹妹试用前置：桌面端启动与打包（2026-10-04）

> 面向第一次在自己电脑上跑「学伴 XueBan」桌面端的人（妈妈 / 爸爸）。
> 目标：**先能启动、先能看见**，再谈安装包。所有命令都在**仓库根目录** `xueban/` 下执行。

---

## 一、先决条件

| 需要什么 | 用来干什么 | 没装会怎样 |
|---|---|---|
| **Node.js ≥ 20 + pnpm** | 构建与运行桌面端 | `pnpm` 不是内部命令 |
| **Rust 工具链**（`rustup`） | 只有 Tauri 窗口需要；纯浏览器试玩不需要 | Tauri 窗口起不来 |
| **WebView2 Runtime**（Windows） | Tauri 窗口的渲染内核；Win10 1803+ 自带 | 窗口白屏 |
| **Docker Desktop** | 后端（Postgres / Redis / MinIO / OCR） | 桌面端登录页能打开，但任何接口都报错 |
| **API 密钥**（`.env`） | 生成讲解内容要调模型 | 讲解生成会失败并降级为图文版；题库与练习不受影响 |

检查命令：

```powershell
node -v          # 期望 v20 以上
pnpm -v
rustc --version  # 只有 Tauri 窗口需要
docker ps        # 期望能看到 xueban-postgres-1 / redis / minio
```

Docker 没起时（Windows 上很常见，服务器或睡眠重启后就会停）：

```powershell
Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe" -WindowStyle Hidden
# 等约 15 秒，再执行 docker ps
```

---

## 二、方式 A：开发模式跑 Tauri 窗口（推荐先走这条）

适合「就想看一眼长什么样」。改动源码后热更新，不用重新编译 Rust。

```powershell
cd C:\Users\Lenovo\Documents\Default Project\xueban

# 1. 起后端（另开一个终端窗口，保持运行）
cd services\api
& ".\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8091

# 2. 起桌面端窗口（回到仓库根）
pnpm --filter @xueban/desktop tauri:dev
```

**Tauri 会自己拉起前端开发服务器**（`vite --port 1420`，见 `tauri.conf.json` 的 `beforeDevCommand`），你不需要手动再开 vite。

### 验证成功的标志

- 弹出标题为 **XueBan** 的窗口
- 窗口里能看到「登录」页（默认停在 `/login`）
- 登录后左侧出现**图标导航 + 熊猫吉祥物**（儿童模式）而不是文字侧边栏

### 常见卡点

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 窗口空白 | 前端 1420 没起来 / 编译报错 | 看终端里 vite 的输出；先单独跑 `pnpm --filter @xueban/desktop dev:vite` 看有没有编译错误 |
| 登录后一直跳回登录页 | 前端打到的后端地址不对 | 前端构建时内联 `VITE_API_BASE_URL`，默认 `http://localhost:8000`。要么让后端也跑 8000，要么构建前设 `$env:VITE_API_BASE_URL="http://127.0.0.1:8091"` |
| 接口报跨域 | `.env` 的 `CORS_ALLOW_ORIGINS` 少了来源 | 见下面「CORS 必读」 |
| Tauri 报缺 `cargo` | 没装 Rust | 装 `rustup` 后重开终端 |

---

## 三、方式 B：浏览器里先看（最省事，不装 Rust）

只验证界面与流程，不装 Tauri：

```powershell
cd C:\Users\Lenovo\Documents\Default Project\xueban
pnpm --filter @xueban/desktop build     # 先构建产物
pnpm --filter @xueban/desktop preview   # 浏览器打开 http://127.0.0.1:4173
```

⚠️ **`vite preview` 的端口是硬编码 4173**（`apps/desktop/vite.config.ts` 里写死的，没有任何环境变量能改）。这是自动化测试也用的端口，别去动它。

---

## 四、方式 C：打包成安装包

适合「装到自己电脑上，像普通软件一样用」。

```powershell
cd C:\Users\Lenovo\Documents\Default Project\xueban
pnpm --filter @xueban/desktop tauri:build
```

**前提**：已装 Rust 工具链 + WebView2。**首次编译很慢**（Tauri 要编自己的壳，数分钟到十几分钟都正常），之后有缓存会快很多。

产物位置：

```
apps/desktop/src-tauri/target/release/bundle/
  ├── nsis/        # Windows 安装包 .exe
  └── msi/         # Windows 安装包 .msi（若配置启用）
```

当前 `tauri.conf.json` 的身份信息：`productName: "XueBan"`、`version: "0.1.0"`、`identifier: "com.xueban.desktop"`。

**打包前必读**：打包出来的是「壳 + 前端产物」。后端（Postgres/Redis/MinIO）和 API 密钥**不在安装包里**——安装到别的电脑时，要么在那边也起一套后端，要么把这套改成指向一台服务器。这个取舍要先想清楚，不要以为装了就能直接用。

---

## 五、CORS 必读（最容易踩、报错最误导）

`.env` 里的 `CORS_ALLOW_ORIGINS` 决定浏览器放不放行前端调用后端。**Tauri 开发模式的来源是 `http://127.0.0.1:1420`，`vite preview` 的来源是 `http://127.0.0.1:4173`**。

漏了这两个 origin 时的症状**不是**「接口报错」，而是：浏览器拦掉 `/v1/auth/me` → 前端判定未登录 → 跳回登录页 → 看起来像「登录功能坏了」。

后端默认值（`services/api/app/config.py` 的 `cors_allow_origins`）**已经包含** 1420 与 4173。只有当 `.env` 显式覆盖了 `CORS_ALLOW_ORIGINS` 时才会漏——所以「什么都不配」反而比「配了但不完整」更安全。

`config.py` 与 `.env.example` 里可复制的完整列表：

```
CORS_ALLOW_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://127.0.0.1:4173,http://localhost:4173,http://127.0.0.1:1420,http://localhost:1420,http://tauri.localhost,tauri://localhost
```

改完 `.env` 要**重启后端**（CORS 是启动时读的）。

---

## 六、登录与数据

- 开发环境的短信验证码接口会在响应里带 `debug_code`，直接填进去即可登录（不需要真手机号）。
- 想直接跳到某个阶段（跳过诊断、复习等前置），浏览器控制台里设置这几个 localStorage 键：

| 键 | 作用 | 值 |
|---|---|---|
| `xueban.journey` | 旅程状态（哪些阶段已完成） | JSON，字段见 `apps/desktop/src/journey/journey-context.tsx` |
| `xueban.gradeBand` | 学段 | `"primary"`（儿童模式）/ `"junior"` / `"senior"` |
| `xueban.theme` | 主题 | `"kids"`（儿童模式）/ `"focus"`（专注模式） |
| `xueban.mode` | 明暗 | `"light"` / `"dark"`（儿童模式下不提供深色） |

- **儿童模式只在 `gradeBand=primary` 时自动启用**。如果妹妹打开的是专注模式界面，先确认 `xueban.gradeBand` 是 `primary`。

---

## 七、试玩前检查清单（30 秒）

- [ ] 后端终端没有报错，`http://127.0.0.1:8091/healthz` 返回 200
- [ ] 桌面端窗口能打开，停在登录页
- [ ] 用 `debug_code` 能登录进去
- [ ] 登录后是**图标导航 + 熊猫**，不是文字侧边栏（说明儿童模式生效）
- [ ] 「今天」页能出题（点「生成练习」）

任一条不通过，先解决再开始试玩——否则试玩时会把环境问题误判成产品问题。

**配套文档**：[`7yo-usability-checklist.md`](./7yo-usability-checklist.md)（13 项逐条取证）、
[`sister-trial-observation-sheet.md`](./sister-trial-observation-sheet.md)（真人试玩观察清单）。
