# 学伴 · 安卓上架材料包（T11.4）

> 目标商店：应用宝 / 华为应用市场 / 小米应用商店 / OPPO 软件商店 / vivo 应用商店。
> 状态图例：✅ 已备（本目录）｜⬜ 待补（需设备/资质，见备注）｜🔁 自动（CI/EAS 产出）。

## 1. 材料总览

| 材料 | 文件/位置 | 应用宝 | 华为 | 小米 | OPPO | vivo |
| --- | --- | --- | --- | --- | --- | --- |
| 应用图标 512×512 | `icons/icon-512.png` ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 应用图标 216×216/192×192 | `icons/icon-192.png` ✅ | — | — | ✅ | — | — |
| 应用名称与简介/详述 | `store-listing.md` ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 隐私政策 URL/文本 | `privacy-policy.md` ✅（线上：`https://<SITE>/privacy`） | ✅ | ✅ | ✅ | ✅ | ✅ |
| 未成年人保护声明 | `minor-protection.md` ✅（线上：`https://<SITE>/minor-protection`） | ✅ | ✅ | ✅ | ✅ | ✅ |
| 权限使用说明 | `store-listing.md` §5 ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 应用截图（手机） | `screenshots/` ⬜ 待补（B-009：需模拟器/真机；获取指引见 `screenshots/README.md`） | 3~8 张 | 3~8 张 | 3~8 张 | 3~8 张 | 3~8 张 |
| 特性图/宣传图 | 由设计按 `store-listing.md` §7 生成 ⬜ | — | ✅ | — | — | — |
| APK/AAB 安装包 | EAS/CI 产出 🔁（`docs/RELEASE.md` §4） | APK | APK | APK | APK | APK |
| 软件著作权证书 | `compliance-checklist.md` §1 指引 ⬜ 人工办理 | ✅（推荐） | ✅ | ✅ | ✅ | ✅ |
| ICP 备案/主体资质 | `compliance-checklist.md` §2 ⬜ 人工办理 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 应用签名（keystore） | EAS 托管 🔁（`docs/RELEASE.md` §4.3） | ✅ | ✅ | ✅ | ✅ | ✅ |

> 截图、软著、备案为**人工/设备依赖项**，逐项状态与闭环动作记录在 `compliance-checklist.md`；其余材料已随本目录备齐。

## 2. 包信息（多商店一致）

| 项 | 值 |
| --- | --- |
| 应用名称 | 学伴 |
| 包名 | `com.xueban.mobile` |
| 版本 | 0.1.0（versionCode 1，见 `apps/mobile/app.json`） |
| 支持系统 | Android 9.0（API 28）及以上 |
| 安装包形态 | 首版 APK 直传（评审用）；正式分发切换 AAB（Google Play）/ APK（国内商店） |
| 签名 | EAS 托管密钥（详见 `docs/RELEASE.md` §4.3） |
| 隐私政策 | `https://<SITE>/privacy` |
| 用户协议 | 同隐私政策页脚（如需独立协议页，按商店模板补充） |
| 客服邮箱 | `support@xueban.example.com`（上线前替换为真实邮箱） |

## 3. 目录说明

```
release-assets/
├── README.md                 # 本文件（总览与状态）
├── store-listing.md          # 商店文案 + 权限说明 + 截图要求
├── privacy-policy.md         # 隐私政策（与官网 /privacy 同源）
├── minor-protection.md       # 未成年人保护声明（与官网 /minor-protection 同源）
├── compliance-checklist.md   # 软著/备案/权限/内容安全办理清单与闭环动作
├── icons/                    # 商店图标（192/512）
└── screenshots/README.md     # 截图清单与获取方式（待设备补齐）
```
