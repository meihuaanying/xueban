/* P0 设计稿走查截图：Ladle 示例页 → PNG（仅 Edge，本机无 Chrome）
 * 依赖：先 `pnpm --filter @xueban/ui stories`（Ladle dev server，端口 61000）
 * 每个 story 默认已并排渲染 focus / kids；桌面骨架稿为单主题，由 ?theme= 决定。
 * 用法：node scripts/design-shots.mjs [输出目录]
 */
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { chromium } from "playwright";

const OUT = process.argv[2] ?? path.resolve("docs/verification/design-review");
const BASE = "http://localhost:61000";

const SHOTS = [
  { file: "01-palette", story: "design-tokens--palette", query: "theme=focus&mode=light" },
  { file: "02-typography", story: "design-tokens--typography", query: "theme=focus&mode=light" },
  { file: "03-spacing-radius", story: "design-tokens--spacing-and-radius", query: "theme=focus&mode=light" },
  { file: "04-learning-bits", story: "design-tokens--learning-bits", query: "theme=focus&mode=light" },
  { file: "06-palette-focus-dark", story: "design-tokens--palette", query: "theme=focus&mode=dark" },
  // 单主题宽幅：桌面完整骨架（两套皮肤各一张）
  { file: "05-shell-focus", story: "design-shell--desktop-shell", query: "theme=focus&mode=light" },
  { file: "05-shell-kids", story: "design-shell--desktop-shell", query: "theme=kids&mode=light" },
];

await mkdir(OUT, { recursive: true });

const browser = await chromium.launch({ channel: "msedge" });
const page = await browser.newPage({ viewport: { width: 1500, height: 1200 }, deviceScaleFactor: 2 });

for (const shot of SHOTS) {
  await page.goto(`${BASE}/?story=${shot.story}&${shot.query}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(600);
  // Ladle 自带全屏（快捷键 f）：隐藏侧栏与工具条，只留走查画布
  await page.keyboard.press("f");
  await page.waitForTimeout(400);
  const target = path.join(OUT, `${shot.file}.png`);
  await page.screenshot({ path: target, fullPage: true });
  console.log("saved", target);
}

await browser.close();
console.log("done ->", OUT);
