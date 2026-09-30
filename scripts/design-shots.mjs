/* P0 设计稿走查截图：Ladle 并排双主题 → PNG（仅 Edge，本机无 Chrome）
 * 每个 story 内部已并排渲染 focus / kids，故每个 story 只需一张截图即可对比。
 * 另加一张 focus 深色皮肤。
 * 用法：node scripts/design-shots.mjs [输出目录]
 */
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { chromium } from "playwright";

const OUT = process.argv[2] ?? path.resolve("docs/verification/design-review");
const BASE = "http://localhost:61000";

const SHOTS = [
  { file: "01-palette", story: "design-tokens--palette" },
  { file: "02-typography", story: "design-tokens--typography" },
  { file: "03-spacing-radius", story: "design-tokens--spacing-and-radius" },
  { file: "04-learning-bits", story: "design-tokens--learning-bits" },
  { file: "05-today-task-page", story: "design-tokens--today-task-page" },
  { file: "06-palette-focus-dark", story: "design-tokens--palette", query: "theme=focus&mode=dark" },
];

await mkdir(OUT, { recursive: true });

const browser = await chromium.launch({ channel: "msedge" });
const page = await browser.newPage({ viewport: { width: 1400, height: 1100 }, deviceScaleFactor: 2 });

for (const shot of SHOTS) {
  const query = shot.query ?? "theme=focus&mode=light";
  await page.goto(`${BASE}/?story=${shot.story}&${query}`, { waitUntil: "networkidle" });
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
