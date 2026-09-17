/** 站点级常量与导航（官网 SEO 与页眉/页脚共用）。 */

export const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";

/**
 * 安装包下载基地址（稳定文件名，见 .github/workflows/release.yml 与 docs/RELEASE.md）。
 * GitHub Release 场景：https://github.com/<OWNER>/<REPO>/releases/latest/download
 * （latest/download 始终指向最新 Release，发布新版本无需改前端）
 */
export const RELEASE_BASE_URL =
  process.env.NEXT_PUBLIC_RELEASE_BASE_URL ?? "https://dl.xueban.example.com/releases/latest";

export const CONTACT_EMAIL = "support@xueban.example.com";

export interface NavLink {
  href: string;
  label: string;
}

export const NAV_LINKS: NavLink[] = [
  { href: "/#features", label: "产品功能" },
  { href: "/pricing", label: "定价" },
  { href: "/download", label: "下载" },
  { href: "/help", label: "帮助中心" },
];

export const FOOTER_LINKS: { title: string; links: NavLink[] }[] = [
  {
    title: "产品",
    links: [
      { href: "/#features", label: "功能总览" },
      { href: "/pricing", label: "订阅定价" },
      { href: "/download", label: "客户端下载" },
    ],
  },
  {
    title: "资源",
    links: [
      { href: "/help", label: "帮助中心" },
      { href: "/register", label: "免费注册" },
      { href: "/app", label: "我的学习中心" },
    ],
  },
  {
    title: "法律与保护",
    links: [
      { href: "/privacy", label: "隐私政策" },
      { href: "/minor-protection", label: "未成年人保护声明" },
      { href: `mailto:${CONTACT_EMAIL}`, label: "联系我们" },
    ],
  },
];
