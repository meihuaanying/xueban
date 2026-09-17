import type { NextConfig } from "next";

const isDev = process.env.NODE_ENV !== "production";

const rawApiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const apiOrigins = new Set<string>([rawApiBase.replace(/\/+$/, "")]);
try {
  const parsed = new URL(rawApiBase);
  const mirror = new URL(rawApiBase);
  if (parsed.hostname === "localhost") {
    mirror.hostname = "127.0.0.1";
  } else if (parsed.hostname === "127.0.0.1") {
    mirror.hostname = "localhost";
  }
  if (mirror.origin !== parsed.origin) {
    apiOrigins.add(mirror.origin);
  }
} catch {
  // 非法 URL 时仅保留原字符串，交由运行时请求报错暴露
}
const apiOriginList = [...apiOrigins].join(" ");

// 生产 CSP：Next.js 静态注入的内联脚本需要 script-src 'unsafe-inline'（无 nonce 方案），
// 其余指令最小化：不引入通配符（避免 ZAP 10055），仅允许同源 + 显式 API 源。
const csp = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${isDev ? " 'unsafe-eval'" : ""}`,
  "style-src 'self' 'unsafe-inline'",
  `img-src 'self' data: blob: ${apiOriginList}`,
  `media-src 'self' blob: ${apiOriginList}`,
  "font-src 'self' data:",
  `connect-src 'self' ${apiOriginList}`,
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
].join("; ");

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  output: "standalone",
  transpilePackages: ["@xueban/ui", "@xueban/core"],
  experimental: {
    // 组件库为 barrel 导出（含 recharts / katex 等重依赖），按需转译避免首屏体积膨胀。
    optimizePackageImports: ["@xueban/ui"],
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "Content-Security-Policy", value: csp },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
          { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
          { key: "Cross-Origin-Embedder-Policy", value: "require-corp" },
          { key: "Cross-Origin-Resource-Policy", value: "same-origin" },
        ],
      },
    ];
  },
};

export default nextConfig;
