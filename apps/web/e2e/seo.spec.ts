import { expect, test } from "@playwright/test";

test.describe("SEO 基建（T4.4）", () => {
  test("首页 SSR 返回完整正文（非空壳 JS）", async ({ request }) => {
    const response = await request.get("/");
    expect(response.status()).toBe(200);
    const html = await response.text();
    expect(html).toContain("把每一道题");
    expect(html).toContain("守护型讲解");
    expect(html).toContain("五步学情闭环");
    expect(html).toContain("免费开始学习");
    expect(html).toContain('type="application/ld+json"');
    expect(html).toContain('rel="canonical"');
  });

  test("robots.txt 有效且声明 sitemap", async ({ request }) => {
    const response = await request.get("/robots.txt");
    expect(response.status()).toBe(200);
    const body = await response.text();
    expect(body).toContain("User-Agent: *");
    expect(body).toContain("Disallow: /app");
    expect(body).toContain("Sitemap:");
  });

  test("sitemap.xml 覆盖全部公开页面", async ({ request }) => {
    const response = await request.get("/sitemap.xml");
    expect(response.status()).toBe(200);
    const body = await response.text();
    const locations = [...body.matchAll(/<loc>(.*?)<\/loc>/g)].map((match) =>
      // 统一去掉末尾斜杠，便于路径断言
      (match[1] ?? "").replace(/\/$/, ""),
    );
    for (const url of [
      "http://localhost:3000",
      "http://localhost:3000/pricing",
      "http://localhost:3000/download",
      "http://localhost:3000/register",
      "http://localhost:3000/help",
      "http://localhost:3000/privacy",
      "http://localhost:3000/minor-protection",
    ]) {
      expect(locations).toContain(url);
    }
    // 私有页面（学习中心）不应进入 sitemap
    expect(locations.some((url) => url.endsWith("/app"))).toBe(false);
  });

  test("各页面具备独立标题与描述", async ({ page }) => {
    const expectations: [string, RegExp][] = [
      ["/pricing", /订阅定价/],
      ["/download", /下载客户端/],
      ["/help", /帮助中心/],
      ["/privacy", /隐私政策/],
      ["/minor-protection", /未成年人保护声明/],
      ["/register", /免费注册/],
    ];
    for (const [path, title] of expectations) {
      await page.goto(path);
      await expect(page).toHaveTitle(title);
      await expect(page.locator('meta[name="description"]')).toHaveAttribute("content", /.{20,}/);
    }
  });
});
