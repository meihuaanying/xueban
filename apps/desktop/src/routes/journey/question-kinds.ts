"use client";

/**
 * 题库题型 → 前端作答形态的映射（REBUILD §6.1）。
 *
 * 题库里六种小学题型的数据形态并不统一（@b4@ 已用 DB 取证确认）：
 *  - choice / pick_hanzi：有 options，answer 是选项 key（pick_hanzi 例外，answer 是汉字内容）
 *  - fill / oral：**没有 options**，answer 直接是答案文本
 *  - judge：没有 options，answer 是「对」/「错」
 *  - match：options 只是右项池（形状），左项列在题干里，answer 是 JSON 映射
 *
 * 所以这里不只是「换个 kind」，还得补默认选项、从题干取连线左项、
 * 并按题型决定提交什么格式——判卷侧（`diagnosis_service.check_answer`）
 * 已经是按题型归一的，两边必须对上。
 */

import type { QuestionKind, QuestionOption } from "@xueban/ui";

/** qtype（小写）→ 题型形态。取不到的一律按 choice 处理，最宽容。 */
const KIND_BY_QTYPE: Record<string, QuestionKind> = {
  choice: "choice",
  fill: "fill",
  judge: "judge",
  match: "link",
  oral: "oral",
  essay: "fill",
  short_answer: "fill",
  pick_hanzi: "pick",
};

/** qtype → 前端 kind。 */
export function resolveKind(qtype: string): QuestionKind {
  return KIND_BY_QTYPE[qtype] ?? "choice";
}

/**
 * 从题干里取连线题的左项。
 *
 * 题库的 match 题把形状池放进 options，左项只能从题干取，形如
 * 「把物品和它的形状连起来：铅笔盒、乒乓球、易拉罐、魔方。」
 * 只按顿号/逗号切，不按「和」「与」切——后者会误伤本身含这些字的词。
 * 取不到就返回空数组，由调用方降级成普通选择题，绝不崩。
 */
export function parseLinkItems(stem: string): string[] {
  const tail = stem.split(/[：:]/).pop() ?? stem;
  return tail
    .split(/[、，,]/)
    .map((part) => part.replace(/[。.!！?？]+$/, "").trim())
    .filter(Boolean);
}

/** 把 `Record<key,label>` 的 options 转成 QuestionCard 需要的数组。 */
export function toOptions(
  options: Record<string, string> | null,
): QuestionOption[] | undefined {
  if (!options) return undefined;
  const list = Object.entries(options).map(([key, label]) => ({ key, label }));
  return list.length ? list : undefined;
}

/**
 * 连线题提交值。
 *
 * 后端 `_matches_link_pairs` 是按 JSON 映射逐键比对的（键序无关），
 * 所以这里 `JSON.stringify` 一个对象即可，不需要自定义序列化格式。
 */
export function toLinkSubmit(pairs: Record<string, string>): string {
  return JSON.stringify(pairs);
}
