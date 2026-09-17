import type { MetadataRoute } from "next";

import { SITE_URL } from "@/lib/site";

export default function sitemap(): MetadataRoute.Sitemap {
  const lastModified = new Date();
  const routes: { path: string; priority: number; changeFrequency: "weekly" | "monthly" }[] = [
    { path: "/", priority: 1, changeFrequency: "weekly" },
    { path: "/pricing", priority: 0.9, changeFrequency: "monthly" },
    { path: "/download", priority: 0.8, changeFrequency: "monthly" },
    { path: "/register", priority: 0.8, changeFrequency: "monthly" },
    { path: "/help", priority: 0.6, changeFrequency: "monthly" },
    { path: "/privacy", priority: 0.3, changeFrequency: "monthly" },
    { path: "/minor-protection", priority: 0.3, changeFrequency: "monthly" },
  ];
  return routes.map((route) => ({
    url: new URL(route.path, SITE_URL).toString(),
    lastModified,
    changeFrequency: route.changeFrequency,
    priority: route.priority,
  }));
}
