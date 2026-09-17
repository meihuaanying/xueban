# 学伴（XueBan）发布手册（T11.4）

> 覆盖：版本号规范、桌面三平台发布（CI + GitHub Release + 官网下载页联动）、安卓上架（EAS 与国内商店）、回滚策略。
> 上架材料目录：`release-assets/`（README 有逐店对照表）。

## 1. 版本号规范

- 采用 SemVer：`MAJOR.MINOR.PATCH`（当前 `0.1.0`）。
- 发版需同步以下位置（一次提交内完成）：

| 位置 | 字段 |
| --- | --- |
| `package.json` / `apps/*/package.json` | `version` |
| `apps/desktop/src-tauri/tauri.conf.json` | `version`（安装包名/升级判定） |
| `apps/mobile/app.json` | `expo.version` 与 `android.versionCode`（递增整数） |
| Git | 标签 `v0.1.0`（桌面 Release 触发条件） |

## 2. 桌面端发布（自动化）

`.github/workflows/release.yml`：推送 `v*` 标签 → 三平台矩阵构建 → 稳定文件名归档 → 创建 GitHub Release。

```bash
git tag v0.1.0 && git push origin v0.1.0
```

| 平台 | Runner | 产物（Release 资产名） |
| --- | --- | --- |
| Windows | windows-latest | `XueBan-Setup-x64.exe`（NSIS） |
| macOS | macos-14 | `XueBan-universal.dmg`（Intel + Apple Silicon 通用包） |
| Linux | ubuntu-22.04 | `XueBan-x86_64.AppImage`、`XueBan-amd64.deb` |

同时生成 `SHA256SUMS.txt`。**B-001 未闭环前**（无 GitHub 远端），本矩阵只能在本地验证配置：

```bash
# 本地可产 Windows NSIS（需本机 WiX/NSIS；mac/linux 不能交叉编译，交 CI）
VITE_API_BASE_URL=https://<SITE> pnpm --filter @xueban/desktop build
pnpm --filter @xueban/desktop exec tauri build --bundles nsis
```

### 2.1 官网下载页联动

下载页（`/download`）以 `NEXT_PUBLIC_RELEASE_BASE_URL` 为基地址拼接稳定文件名。使用 GitHub Release 时：

```dotenv
NEXT_PUBLIC_RELEASE_BASE_URL=https://github.com/<OWNER>/<REPO>/releases/latest/download
```

`latest/download` 永远指向最新 Release，因此**发版后无需改动前端**，页面即指向最新安装包（验收：浏览器打开 `/download`，链接为 `.../releases/latest/download/XueBan-Setup-x64.exe` 等）。

### 2.2 安装冒烟（每版本）

| 项 | Windows | macOS | Linux |
| --- | --- | --- | --- |
| 安装 | 双击 NSIS 静默/常规安装 | 拖拽到 Applications | AppImage 直接运行 / deb 安装 |
| 启动 | 记录冷启动 ≤3s（当前 1.1s，见 M5 证据） | CI 冒烟 | CI 冒烟 |
| 核心动作 | 登录 → 诊断 → 讲解流式输出（LaTeX 正常） | 同左 | 同左 |
| 卸载 | 控制面板卸载后无残留进程 | 删除应用 | 卸载 deb |

## 3. 安卓发布（EAS + 国内商店）

### 3.1 前置

```bash
npm i -g eas-cli        # 或 npx eas-cli@latest
cd apps/mobile
eas login               # 使用团队 Expo 账号
eas init                # 首次：创建/关联 EAS 项目（会写回 app.json 的 extra.eas.projectId）
```

`apps/mobile/eas.json` 已配置 development / preview（APK）/ production（AAB，autoIncrement）。

### 3.2 构建

```bash
# 预览 APK（内部验收/商店提审素材可用）
eas build --platform android --profile preview

# 生产 AAB（Google Play）/ APK（国内商店可再用 preview 产物）
eas build --platform android --profile production
```

产物在 EAS 控制台下载；同时可配置 CI 直传（见 `.github/workflows/ci.yml` 的 `mobile-apk` 作业，输出 APK ≤80MB 门禁）。

### 3.3 签名

- 首次 `eas build` 时选择 **Generate a new Android Keystore**（EAS 托管，支持导出）。
- 导出（备份，勿入库）：`eas credentials --platform android` → Download keystore；登记 SHA-256 指纹。
- 国内商店若要求自有签名：用同一 keystore 重签（`apksigner`），并保证后续版本一致。

### 3.4 EAS Submit（Google Play，如需出海）

```bash
eas submit --platform android --profile production
```

国内商店（应用宝/华为/小米/OPPO/vivo）不支持 EAS 自动提交，需在各自开放平台**手动上传 APK/AAB 并填写材料**：

1. 材料取用：`release-assets/README.md`（对照表）→ `store-listing.md`（文案/权限）→ `icons/`（图标）→ `privacy-policy.md`（隐私政策文本与 URL）。
2. 截图：`release-assets/screenshots/README.md`（B-009 闭环后补；商店要求 3~8 张真机截图）。
3. 资质：`release-assets/compliance-checklist.md`（软著、ICP 备案、主体资质）。
4. 审核注意：学习类应用需能打开隐私政策链接；未成年人相关声明随包/随商店后台提交；权限说明必须与 `store-listing.md` §5 一致。

## 4. 发布检查单（发版前逐项勾选）

- [ ] 全部门禁绿：`pnpm lint && pnpm typecheck && pnpm test`；后端 `pytest --cov-fail-under=85`、ruff、mypy
- [ ] 版本号已同步（§1）；CHANGELOG/Release Notes 草稿准备好
- [ ] `v*` 标签已推送，Release 产物齐全（三平台 + SHA256SUMS.txt）
- [ ] 官网 `/download` 链接指向新 Release（latest/download 自动生效）
- [ ] Android：EAS 产物版本号递增、签名一致、隐私政策 URL 可访问
- [ ] 后端镜像 tag `XUEBAN_VERSION=<版本>`，按 `docs/DEPLOY.md` §5 更新生产
- [ ] 冒烟：官网 Lighthouse 四项、桌面安装启动、Android 核心旅程（Maestro）

## 5. 回滚策略

| 场景 | 动作 |
| --- | --- |
| 桌面端问题 | 在 GitHub Release 上标记该版本为 pre-release 并补发修复版本；官网 latest 自动指回上一稳定版（若删除 latest 资产，需重建 release 或改用版本化 URL） |
| 服务端问题 | 回退镜像 tag：`XUEBAN_VERSION=<上一版本> docker compose ... up -d api worker`；数据库迁移按 `alembic downgrade -1`（先备份） |
| 移动端问题 | 商店后台下架问题版本/提交热修版本（Expo OTA 未启用：本期走应用商店更新） |
| 数据问题 | 按 `docs/OPS.md` §2 恢复备份（先停 api/worker） |

## 6. 已知阻塞（发版前必须闭环）

| 编号 | 事项 | 闭环动作 |
| --- | --- | --- |
| B-001 | GitHub 无远端，CI/Release 未实跑 | 配置远端并推送，`v*` 标签触发 Release 全绿 |
| B-008 | mac/Linux 包本机不可产 | 交 CI 矩阵（与 B-001 同批） |
| B-009 | 本机无 Android SDK/模拟器/Maestro | CI `mobile-apk` 作业 + 设备/模拟器复跑 Maestro |
| B-005/B-003 | 真实模型 Key | 生产 `.env` 填 Key 后切 `LLM_PROVIDER=litellm` 并跑 promptfoo 全量 |
