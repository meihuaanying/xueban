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

/** 对话框（受控；Esc 与遮罩关闭）。遮罩色走 --scrim 令牌，浮层尺寸走字阶/圆角令牌。 */
export function Dialog({ className, open, title, onClose, children, footer, ...props }: DialogProps) {
  if (!open) {
    return null;
  }
  return (
    <div
      className={cn("fixed inset-0 z-50 flex items-center justify-center p-md", className)}
      {...props}
    >
      <button
        type="button"
        aria-label="关闭对话框"
        className="absolute inset-0 bg-scrim"
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
        className="relative z-10 w-full max-w-lg rounded-card border border-border bg-card p-lg text-card-foreground shadow-pop"
      >
        <div className="mb-sm flex items-center justify-between gap-sm">
          <h2 className="text-app-lg font-semibold">{title}</h2>
          {onClose ? (
            <button
              type="button"
              onClick={onClose}
              aria-label="关闭"
              className="text-app-sm text-muted-foreground hover:text-foreground"
            >
              ✕
            </button>
          ) : null}
        </div>
        <div className="text-app text-muted-foreground">{children}</div>
        {footer ? <div className="mt-lg flex justify-end gap-sm">{footer}</div> : null}
      </div>
    </div>
  );
}

export interface TooltipProps extends HTMLAttributes<HTMLSpanElement> {
  content: string;
  children: ReactNode;
}

export function Tooltip({ className, content, children, ...props }: TooltipProps) {
  return (
    <span className={cn("group relative inline-flex", className)} {...props}>
      <span title={content} className="border-b border-dashed border-border-strong">
        {children}
      </span>
      <span
        role="tooltip"
        className="pointer-events-none absolute left-1/2 top-0 hidden -translate-x-1/2 -translate-y-full whitespace-nowrap rounded-control bg-foreground px-xs py-hair text-app-xs text-background group-hover:block"
      >
        {content}
      </span>
    </span>
  );
}
