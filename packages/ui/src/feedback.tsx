"use client";

import type { HTMLAttributes, ReactNode } from "react";

import { cn } from "./cn";

/**
 * 反馈类基础组件。
 * 全部配色改用语义令牌（--success-soft/--warning-soft/--destructive-soft/--info-soft 等），
 * 去掉 green-100/amber-100/blue-200 等硬编码色 ⇒ 跟随双主题换肤。
 * 进度条高度走 --mastery-bar-height（focus 8px / kids 14px）。
 */

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: "default" | "success" | "warning" | "danger" | "info" | "outline";
}

export function Badge({ className, variant = "default", ...props }: BadgeProps) {
  const variantClass = {
    default: "bg-secondary text-secondary-foreground",
    success: "bg-success-soft text-success-foreground",
    warning: "bg-warning-soft text-warning-foreground",
    danger: "bg-destructive-soft text-destructive-foreground",
    info: "bg-info-soft text-info-foreground",
    outline: "border border-border-strong text-foreground",
  }[variant];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-hair rounded-pill px-xs py-hair text-app-xs font-medium",
        variantClass,
        className,
      )}
      {...props}
    />
  );
}

export interface AlertProps extends HTMLAttributes<HTMLDivElement> {
  variant?: "info" | "success" | "warning" | "danger";
  title?: string;
  children?: ReactNode;
}

export function Alert({ className, variant = "info", title, children, ...props }: AlertProps) {
  const variantClass = {
    info: "border-info/40 bg-info-soft text-info-foreground",
    success: "border-success/40 bg-success-soft text-success-foreground",
    warning: "border-warning/40 bg-warning-soft text-warning-foreground",
    danger: "border-destructive/40 bg-destructive-soft text-destructive-foreground",
  }[variant];
  return (
    <div
      role="alert"
      className={cn("rounded-card border p-sm text-app", variantClass, className)}
      {...props}
    >
      {title ? <p className="mb-hair font-semibold">{title}</p> : null}
      {children}
    </div>
  );
}

export interface ProgressProps extends HTMLAttributes<HTMLDivElement> {
  value: number;
  max?: number;
  /** 填充色令牌（默认主色），例如 `var(--mastery-3)` */
  tone?: string;
  label?: string;
}

export function Progress({ className, value, max = 100, tone, label = "进度", ...props }: ProgressProps) {
  const ratio = max > 0 ? Math.min(Math.max(value / max, 0), 1) : 0;
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuenow={value}
      aria-valuemin={0}
      aria-valuemax={max}
      className={cn(
        "w-full overflow-hidden rounded-pill bg-muted",
        "h-[var(--mastery-bar-height)]",
        className,
      )}
      {...props}
    >
      <div
        className="h-full rounded-pill transition-all duration-base ease-soft"
        style={{ width: `${ratio * 100}%`, background: tone ?? "var(--primary)" }}
      />
    </div>
  );
}

export function Skeleton({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("animate-pulse rounded-control bg-muted", "h-[var(--mastery-bar-height)]", className)}
      {...props}
    />
  );
}

export interface SpinnerProps extends HTMLAttributes<HTMLSpanElement> {
  size?: "sm" | "md" | "lg";
}

export function Spinner({ className, size = "md", ...props }: SpinnerProps) {
  const sizeClass = { sm: "size-hair", md: "size-md", lg: "size-lg" }[size];
  return (
    <span
      role="status"
      aria-label="加载中"
      className={cn(
        "inline-block animate-spin rounded-pill border-2 border-muted border-t-primary",
        sizeClass,
        className,
      )}
      {...props}
    />
  );
}

export function Separator({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div role="separator" className={cn("h-px w-full bg-border", className)} {...props} />;
}

export interface AvatarProps extends HTMLAttributes<HTMLSpanElement> {
  name: string;
  src?: string;
  size?: "sm" | "md" | "lg";
}

export function Avatar({ className, name, src, size = "md", ...props }: AvatarProps) {
  const sizeClass = {
    sm: "size-sm text-app-xs",
    md: "size-md text-app-sm",
    lg: "size-lg text-app-lg",
  }[size];
  return (
    <span
      className={cn(
        "inline-flex items-center justify-center overflow-hidden rounded-pill bg-primary font-medium text-primary-foreground",
        sizeClass,
        className,
      )}
      {...props}
    >
      {src ? <img src={src} alt={name} className="size-full object-cover" /> : name.trim().charAt(0) || "学"}
    </span>
  );
}

export interface ToastProps extends HTMLAttributes<HTMLDivElement> {
  title: string;
  description?: string;
  variant?: "default" | "success" | "danger" | "warning";
  onClose?: () => void;
}

export function Toast({ className, title, description, variant = "default", onClose, ...props }: ToastProps) {
  const variantClass = {
    default: "bg-card text-card-foreground border-border",
    success: "bg-success text-success-foreground",
    danger: "bg-destructive text-destructive-foreground",
    warning: "bg-warning text-warning-foreground",
  }[variant];
  return (
    <div
      role="status"
      className={cn(
        "flex items-start gap-sm rounded-card border p-sm shadow-pop",
        variantClass,
        className,
      )}
      {...props}
    >
      <div className="flex-1">
        <p className="text-app font-semibold">{title}</p>
        {description ? <p className="mt-hair text-app-xs opacity-90">{description}</p> : null}
      </div>
      {onClose ? (
        <button
          type="button"
          onClick={onClose}
          aria-label="关闭提示"
          className="text-app-xs opacity-80 hover:opacity-100"
        >
          ✕
        </button>
      ) : null}
    </div>
  );
}
