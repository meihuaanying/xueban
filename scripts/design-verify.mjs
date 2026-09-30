/* P0 设计稿走查：像素级核验（Playwright + Edge）
 * 直接量 Ladle 示例页里两套主题的**计算值**，避免「截图看起来一样」的争议。
 * 注意：自定义属性的 getPropertyValue 返回的是「在声明处已解析的记号」，
 * 因此字号/圆角/热区必须在主题容器内插入探针元素，量 getComputedStyle 的结果。
 * 用法：node scripts/design-verify.mjs
 */
import { chromium } from "playwright";

const BASE = "http://localhost:61000";

/** 在指定容器内插探针，量 var() 落到真实属性上的结果 */
const MEASURE = `(sel, pairs) => {
  const box = document.querySelector(sel);
  if (!box) return null;
  const out = { theme: box.getAttribute("data-theme"), mode: box.getAttribute("data-mode"), dark: box.classList.contains("dark") };
  for (const [key, prop, value] of pairs) {
    const probe = document.createElement("span");
    probe.style.position = "absolute";
    probe.style.visibility = "hidden";
    probe.style.setProperty(prop, value);
    box.appendChild(probe);
    out[key] = getComputedStyle(probe).getPropertyValue(prop).trim();
    probe.remove();
  }
  for (const [key, name] of [["bg", "--background"], ["primary", "--primary"], ["fg", "--foreground"], ["sunken", "--surface-sunken"], ["borderStrong", "--border-strong"], ["fontScale", "--font-scale"], ["tapMin", "--tap-min"], ["kmapNode", "--kmap-node"], ["barHeight", "--mastery-bar-height"]]) {
    out[key] = getComputedStyle(box).getPropertyValue(name).trim();
  }
  return out;
}`;

const PAIRS = [
  ["fontApp", "font-size", "var(--text-app)"],
  ["fontLg", "font-size", "var(--text-app-lg)"],
  ["font2xl", "font-size", "var(--text-app-2xl)"],
  ["radiusControl", "border-radius", "var(--radius-control)"],
  ["radiusCard", "border-radius", "var(--radius-card)"],
  ["minHeight", "min-height", "var(--tap-min)"],
];

const browser = await chromium.launch({ channel: "msedge" });
const page = await browser.newPage({ viewport: { width: 1500, height: 1200 } });

async function probe(story, query) {
  await page.goto(`${BASE}/?story=${story}&${query}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(500);
  await page.keyboard.press("f");
  await page.waitForTimeout(300);
  return page.evaluate(
    ([measure, pairs]) => {
      const fn = eval(measure);
      return {
        focus: fn('[data-theme="focus"]', pairs),
        kids: fn('[data-theme="kids"]', pairs),
      };
    },
    [MEASURE, PAIRS],
  );
}

const results = {};
results.dual = await probe("design-tokens--learning-bits", "theme=focus&mode=light");
results.dark = await probe("design-tokens--palette", "theme=focus&mode=dark");
results.shellKids = await probe("design-shell--desktop-shell", "theme=kids&mode=light");

const checks = [];
const push = (name, pass, detail) => {
  checks.push({ name, pass, detail });
  console.log(`${pass ? "PASS" : "FAIL"}  ${name}\n        ${detail}`);
};
const px = (v) => Math.round(Number.parseFloat(v) * 100) / 100;

const f = results.dual.focus;
const k = results.dual.kids;
const d = results.dark.focus;
const dk = results.dark.kids;
const sk = results.shellKids.kids;

console.log("== A 亮色并排（story: learning-bits）==");
console.log("focus:", JSON.stringify(f));
console.log("kids :", JSON.stringify(k));
console.log("== B ?mode=dark ==");
console.log("focus:", JSON.stringify(d));
console.log("kids :", JSON.stringify(dk));
console.log("== C 桌面骨架 ?theme=kids ==");
console.log("kids :", JSON.stringify(sk));
console.log("== 判定 ==");

push("1 dark 皮肤底色生效", d.dark === true && d.bg === "#0b1220", `--background=${d.bg}（亮色为 ${f.bg}）class.dark=${d.dark}`);
push("2 dark 与亮色确实不同", d.bg !== f.bg, `dark=${d.bg} vs light=${f.bg}`);
push("3 kids 在 mode=dark 下仍亮色", dk.dark === false && dk.bg === k.bg, `kids.dark=${dk.dark} bg=${dk.bg}`);
push("4 focus 正文 14px", px(f.fontApp) === 14, `text-app=${f.fontApp}`);
push("5 kids 正文 18px", px(k.fontApp) === 18, `text-app=${k.fontApp}`);
push("6 两主题字阶肉眼可辨（≥4px）", px(k.fontApp) - px(f.fontApp) >= 4, `focus=${f.fontApp} kids=${k.fontApp} 差 ${px(k.fontApp) - px(f.fontApp)}px`);
push("7 标题字阶也有别（app-2xl）", px(k.font2xl) !== px(f.font2xl), `focus=${f.font2xl} kids=${k.font2xl}`);
push("8 focus 选项热区 32px", px(f.minHeight) === 32, `--tap-min 量得 ${f.minHeight}`);
push("9 kids 选项热区 48px", px(k.minHeight) === 48, `--tap-min 量得 ${k.minHeight}`);
push("10 圆角随主题换肤（radius-control）", px(f.radiusControl) !== px(k.radiusControl), `focus=${f.radiusControl} kids=${k.radiusControl}`);
push("11 kids 圆角 ≥12px（§4）", px(k.radiusControl) >= 12, `kids radius-control=${k.radiusControl}`);
push("12 知识地图节点尺寸有别", f.kmapNode !== k.kmapNode, `focus=${f.kmapNode} kids=${k.kmapNode}`);
push("13 掌握度条高度有别", f.barHeight !== k.barHeight, `focus=${f.barHeight} kids=${k.barHeight}`);
push("14 卡片描边令牌存在", Boolean(f.borderStrong && k.borderStrong), `focus=${f.borderStrong} kids=${k.borderStrong}`);
push("15 表面三层可区分", f.sunken !== f.bg && k.sunken !== k.bg, `focus bg=${f.bg}/sunken=${f.sunken}；kids bg=${k.bg}/sunken=${k.sunken}`);
push("16 桌面骨架 kids 字阶生效", px(sk.fontApp) === 18, `shell(kids) text-app=${sk.fontApp}`);

const failed = checks.filter((c) => !c.pass);
console.log(`\n合计 ${checks.length} 项，通过 ${checks.length - failed.length}，失败 ${failed.length}`);
await browser.close();
if (failed.length > 0) {
  console.log("失败项：", failed.map((c) => c.name).join(" | "));
  process.exitCode = 1;
}
