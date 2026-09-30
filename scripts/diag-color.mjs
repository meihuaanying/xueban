/* 验证 text-primary-foreground 的 CSS 变量解析链（临时诊断脚本） */
import { chromium } from "playwright";

const BASE = "http://127.0.0.1:4173";
const browser = await chromium.launch({ channel: "msedge" });
const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });

await page.goto(`${BASE}/login`, { waitUntil: "networkidle" });
await page.waitForTimeout(800);

const report = await page.evaluate(() => {
  const root = document.documentElement;
  const cs = getComputedStyle(root);
  const btn = document.querySelector('button[type="submit"]');
  const btnCs = btn ? getComputedStyle(btn) : null;
  return {
    dataTheme: root.getAttribute("data-theme"),
    dataMode: root.getAttribute("data-mode"),
    varPrimaryForeground: cs.getPropertyValue("--primary-foreground").trim(),
    varColorPrimaryForeground: cs.getPropertyValue("--color-primary-foreground").trim(),
    varPrimary: cs.getPropertyValue("--primary").trim(),
    btnColor: btnCs?.color ?? "NO-BUTTON",
    btnBg: btnCs?.backgroundColor ?? "NO-BUTTON",
    btnClass: btn?.className ?? "NO-BUTTON",
    mutedOnBg: (() => {
      const el = document.querySelector(".text-muted-foreground");
      if (!el) return "NO-MUTED-EL";
      const s = getComputedStyle(el);
      return `${s.color} on ${s.backgroundColor}`;
    })(),
  };
});

console.log(JSON.stringify(report, null, 2));
await browser.close();
