"use client";

/** 儿童模式的作答控件（REBUILD §4.1 / §6.1）：
 *  - 连线题：点左再点的配对台（一年级手指精度不够，拖拽不可靠）；
 *  - 答对撒花：纯 CSS 动效，不依赖音频文件。
 * 两者都不引入新依赖，且都不做数据获取。
 */

import { useState, type ReactNode } from "react";

import { cn } from "../cn";

/** 判断题的兜底选项：题库里 judge 题没有 options，前端必须自己补两个大按钮。 */
export const JUDGE_OPTIONS: { key: string; label: ReactNode }[] = [
  { key: "对", label: "√ 对" },
  { key: "错", label: "× 错" },
];

/** 口算/朗读题的兜底提示语（题库里 oral 题没有 options）。 */
export const ORAL_PLACEHOLDER = "先说出来，再把答案写在这里";

export interface LinkMatcherProps {
  /** 左项：题干里列出的实物（按展示顺序） */
  left: string[];
  /** 右项候选池 */
  right: string[];
  /** 已配对结果（左 → 右），受控 */
  value?: Record<string, string>;
  disabled?: boolean;
  /** 配对变化时回调；父组件负责序列化成答案提交 */
  /** 配对变化时回调，第二个参数表示是否已全部配好 */
  onChange?: (pairs: Record<string, string>, complete: boolean) => void;
  /** 刚刚全部配好时再触发一次，供父组件直接提交 */
  onComplete?: (pairs: Record<string, string>) => void;
}

/**
 * 连线题配对台。
 *
 * 交互是「先点左边，再点右边」而不是拖拽：一年级孩子手指精度不够，
 * 拖拽在他们手上极易变成乱拖，点了就配不上，挫败感比做不出题还强。
 * 点同一个右项两次即可解除配对；重新点别的左项直接切换，不会丢已配好的。
 */
export function LinkMatcher({
  left,
  right,
  value = {},
  disabled,
  onChange,
  onComplete,
}: LinkMatcherProps) {
  const [active, setActive] = useState<string | null>(null);

  const pair = (rightKey: string) => {
    if (!active || disabled) return;
    // 再点一次自己已经配上的右项 = 撤销。这一条必须真的生效：孩子配错了
    // 却改不掉，只能从头再来，那挫败感比做不出题还强。
    if (value[active] === rightKey) {
      const undone = { ...value };
      delete undone[active];
      setActive(null);
      onChange?.(undone, false);
      return;
    }
    const next: Record<string, string> = { ...value };
    // 同一右项被别的左项占用时先解掉旧配，保证一右只配一左
    for (const [l, r] of Object.entries(next)) {
      if (r === rightKey) delete next[l];
    }
    next[active] = rightKey;
    setActive(null);
    const complete = Object.keys(next).length === left.length;
    onChange?.(next, complete);
    if (complete) onComplete?.(next);
  };

  const usedRight = new Set(Object.values(value));

  return (
    <div className="mt-sm flex flex-col gap-sm" data-testid="link-matcher">
      <ul className="flex flex-wrap gap-xs" role="list" aria-label="要配对的东西">
        {left.map((item) => {
          const matched = value[item];
          return (
            <li key={item}>
              <button
                type="button"
                disabled={disabled}
                aria-pressed={active === item}
                data-testid={"link-left-" + item}
                onClick={() => setActive(active === item ? null : item)}
                className={cn(
                  "min-h-[var(--tap-min)] rounded-control border px-sm text-app",
                  "transition-colors disabled:cursor-not-allowed disabled:opacity-60",
                  active === item
                    ? "border-primary bg-primary-soft text-accent-foreground"
                    : matched
                      ? "border-success bg-success-soft text-foreground"
                      : "border-border-strong bg-card text-foreground hover:bg-accent",
                )}
              >
                {item}
                {matched ? <span className="ml-xs text-app-xs">→ {matched}</span> : null}
              </button>
            </li>
          );
        })}
      </ul>

      <ul className="flex flex-wrap gap-xs" role="list" aria-label="可以选的答案">
        {right.map((item) => {
          const taken = usedRight.has(item);
          return (
            <li key={item}>
              <button
                type="button"
                disabled={disabled || active === null}
                data-testid={"link-right-" + item}
                onClick={() => pair(item)}
                className={cn(
                  "min-h-[var(--tap-min)] rounded-control border px-sm text-app",
                  "transition-colors disabled:cursor-not-allowed disabled:opacity-60",
                  active === null && "opacity-50",
                  active !== null && !taken && "border-primary hover:bg-accent",
                  taken && "border-success bg-success-soft",
                  "border-border-strong bg-card text-foreground",
                )}
              >
                {item}
              </button>
            </li>
          );
        })}
      </ul>

      <p className="text-app-xs text-muted-foreground" data-testid="link-progress">
        已配对 {Object.keys(value).length} / {left.length}
      </p>
    </div>
  );
}

/** 撒花的颜色：明黄 / 天蓝 / 草绿（§4.1 儿童主题主色）。 */
const CONFETTI_COLORS = ["#F6C445", "#4BA3E3", "#7BC96F", "#F08A5D", "#9B7EDE"] as const;

const KEYFRAMES = `
@keyframes xb-confetti-fall {
  from { transform: translate3d(0, -8%, 0) rotate(0deg); opacity: 1; }
  to { transform: translate3d(var(--xb-drift, 0px), 108%, 0) rotate(540deg); opacity: 0; }
}
@media (prefers-reduced-motion: reduce) {
  .xb-confetti-piece { animation: none !important; display: none; }
}
`;

/**
 * 答对撒花（§4.1 正反馈动效）。
 *
 * 纯 CSS 动画 + 一次性 keyframes，不用音频文件：音效要等资产，
 * 而动效必须立刻有——孩子答对的那一秒就是正反馈窗口。
 * 尊重 prefers-reduced-motion（动效敏感的孩子会直接关掉它）。
 */
export function CorrectBurst({ count = 18 }: { count?: number }) {
  const pieces = Array.from({ length: count }, (_, index) => index);
  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
      <style>{KEYFRAMES}</style>
      {pieces.map((index) => (
        <span
          key={index}
          className="xb-confetti-piece absolute top-0 block h-2 w-1.5 rounded-sm"
          style={{
            left: `${(index * 97) % 100}%`,
            backgroundColor: CONFETTI_COLORS[index % CONFETTI_COLORS.length],
            animation: `xb-confetti-fall ${900 + (index % 5) * 160}ms ease-in ${
              (index % 7) * 60
            }ms forwards`,
            // @ts-expect-error CSS 自定义属性：TS 的 CSSProperties 不认它
            "--xb-drift": `${((index * 37) % 80) - 40}px`,
          }}
        />
      ))}
    </div>
  );
}
