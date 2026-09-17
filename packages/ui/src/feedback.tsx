"use client";

import type { HTMLAttributes, ReactNode } from "react";

import { cn } from "./cn";

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: "default" | "success" | "warning" | "danger" | "outline";
}

/** 徽标 */
export function Badge({ className, variant = "default", ...props }: BadgeProps) {
  const variantClass = {
    default: "bg-secondary text-secondary-foreground",
    success: "bg-green-100 text-green-800",
    warning: "bg-amber-100 text-amber-800",
    danger: "bg-red-100 text-red-800",
    outline: "border border-border text-foreground",
  }[variant];
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
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

/** 提示条 */
export function Alert({ className, variant = "info", title, children, ...props }: AlertProps) {
  const variantClass = {
    info: "border-blue-200 bg-blue-50 text-blue-900",
    success: "border-green-200 bg-green-50 text-green-900",
    warning: "border-amber-200 bg-amber-50 text-amber-900",
    danger: "border-red-200 bg-red-50 text-red-900",
  }[variant];
  return (
    <div role="alert" className={cn("rounded-lg border p-4 text-sm", variantClass, className)} {...props}>
      {title ? <p className="mb-1 font-semibold">{title}</p> : null}
      {children}
    </div>
  );
}

export interface ProgressProps extends HTMLAttributes<HTMLDivElement> {
  value: number;
  max?: number;
}

/** 进度条 */
export function Progress({ className, value, max = 100, ...props }: ProgressProps) {
  const ratio = max > 0 ? Math.min(Math.max(value / max, 0), 1) : 0;
  return (
    <div
      role="progressbar"
      aria-label="进度"
      aria-valuenow={value}
      aria-valuemin={0}
      aria-valuemax={max}
      className={cn("h-2 w-full overflow-hidden rounded-full bg-muted", className)}
      {...props}
    >
      <div
        className="h-full rounded-full bg-primary transition-all"
        style={{ width: `${ratio * 100}%` }}
      />
    </div>
  );
}

/** 加载骨架屏 */
export function Skeleton({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("animate-pulse rounded-md bg-muted", className)} {...props} />;
}

export interface SpinnerProps extends HTMLAttributes<HTMLSpanElement> {
  size?: "sm" | "md" | "lg";
}

/** 加载指示器 */
export function Spinner({ className, size = "md", ...props }: SpinnerProps) {
  const sizeClass = { sm: "h-4 w-4", md: "h-6 w-6", lg: "h-8 w-8" }[size];
  return (
    <span
      role="status"
      aria-label="加载中"
      className={cn(
        "inline-block animate-spin rounded-full border-2 border-muted border-t-primary",
        sizeClass,
        className,
      )}
      {...props}
    />
  );
}

/** 分隔线 */
export function Separator({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div role="separator" className={cn("h-px w-full bg-border", className)} {...props} />;
}

export interface AvatarProps extends HTMLAttributes<HTMLSpanElement> {
  name: string;
  src?: string;
  size?: "sm" | "md" | "lg";
}

/** 头像（无图时显示首字） */
export function Avatar({ className, name, src, size = "md", ...props }: AvatarProps) {
  const sizeClass = { sm: "h-8 w-8 text-xs", md: "h-10 w-10 text-sm", lg: "h-14 w-14 text-lg" }[size];
  return (
    <span
      className={cn(
        "inline-flex items-center justify-center overflow-hidden rounded-full bg-primary text-primary-foreground",
        sizeClass,
        className,
      )}
      {...props}
    >
      {src ? (
        <img src={src} alt={name} className="h-full w-full object-cover" />
      ) : (
        name.trim().charAt(0) || "学"
      )}
    </span>
  );
}

export interface ToastProps extends HTMLAttributes<HTMLDivElement> {
  title: string;
  description?: string;
  variant?: "default" | "success" | "danger";
  onClose?: () => void;
}

/** 轻提示（受控展示） */
export function Toast({ className, title, description, variant = "default", onClose, ...props }: ToastProps) {
  const variantClass = {
    default: "bg-card text-card-foreground",
    success: "bg-green-600 text-white",
    danger: "bg-destructive text-white",
  }[variant];
  return (
    <div
      role="status"
      className={cn("flex items-start gap-3 rounded-lg px-4 py-3 shadow-lg", variantClass, className)}
      {...props}
    >
      <div className="flex-1">
        <p className="text-sm font-semibold">{title}</p>
        {description ? <p className="mt-0.5 text-xs opacity-90">{description}</p> : null}
      </div>
      {onClose ? (
        <button type="button" onClick={onClose} aria-label="关闭提示" className="text-xs opacity-80 hover:opacity-100">
          ✕
        </button>
      ) : null}
    </div>
  );
}
