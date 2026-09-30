import type { MetadataRoute } from "next";

import { SITE_URL } from "@/lib/site";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        // P0 / D4：/parents、/admin、/app 已归档至 src/app/_archived，
        // 保留 disallow 既防止旧链接被抓取，也避免归档内容重新进入索引。
        disallow: ["/app", "/parents", "/admin"],
      },
    ],
    sitemap: new URL("/sitemap.xml", SITE_URL).toString(),
  };
}
