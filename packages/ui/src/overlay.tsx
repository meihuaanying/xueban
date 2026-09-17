"use client";

import type { HTMLAttributes, ReactNode } from "react";

import { cn } from "./cn";

export interface DialogProps extends HTMLAttributes<HTMLDivElement> {
  open: boolean;
  title: string;
  onClose?: () => void;
  children?: ReactNode;
  footer?: ReactNode;
}

/** 对话框（受控；Esc 与遮罩关闭） */
export function Dialog({ className, open, title, onClose, children, footer, ...props }: DialogProps) {
  if (!open) {
    return null;
  }
  return (
    <div className={cn("fixed inset-0 z-50 flex items-center justify-center", className)} {...props}>
      <button
        type="button"
        aria-label="关闭对话框"
        className="absolute inset-0 bg-black/40"
        onClick={onClose}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onKeyDown={(event) => {
          if (event.key === "Escape") {
            onClose?.();
          }
        }}
        className="relative z-10 w-full max-w-md rounded-xl border border-border bg-card p-6 shadow-xl"
      >
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-card-foreground">{title}</h2>
          {onClose ? (
            <button type="button" onClick={onClose} aria-label="关闭" className="text-muted-foreground hover:text-foreground">
              ✕
            </button>
          ) : null}
        </div>
        <div className="text-sm text-muted-foreground">{children}</div>
        {footer ? <div className="mt-6 flex justify-end gap-3">{footer}</div> : null}
      </div>
    </div>
  );
}

export interface TooltipProps extends HTMLAttributes<HTMLSpanElement> {
  content: string;
  children: ReactNode;
}

/** 悬浮提示（title 兜底 + 自定义样式） */
export function Tooltip({ className, content, children, ...props }: TooltipProps) {
  return (
    <span className={cn("group relative inline-flex", className)} {...props}>
      <span title={content} className="border-b border-dashed border-border">
        {children}
      </span>
      <span
        role="tooltip"
        className="pointer-events-none absolute -top-2 left-1/2 hidden -translate-x-1/2 -translate-y-full whitespace-nowrap rounded-md bg-foreground px-2 py-1 text-xs text-background group-hover:block"
      >
        {content}
      </span>
    </span>
  );
}
