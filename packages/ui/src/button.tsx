import { cva, type VariantProps } from "class-variance-authority";
import type { ButtonHTMLAttributes } from "react";

import { cn } from "./cn";

/**
 * 全端统一按钮。
 * 尺寸与圆角全部走令牌：--button-height / --r-control / --text-app-*，
 * 因此 kids 主题下自动变大变圆（无需为儿童单独写一套组件）。
 * 最小热区由 --tap-min 兜底：即使 sm 尺寸也不会低于 32px（focus）/ 48px（kids）。
 */
export const buttonVariants = cva(
  [
    "inline-flex items-center justify-center gap-x-hair",
    "rounded-control font-medium transition-colors",
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
    "disabled:pointer-events-none disabled:opacity-50",
  ],
  {
    variants: {
      variant: {
        primary: "bg-primary text-primary-foreground hover:bg-primary-hover",
        secondary: "bg-secondary text-secondary-foreground hover:bg-accent",
        outline: "border border-border-strong bg-transparent text-foreground hover:bg-muted",
        ghost: "bg-transparent text-foreground hover:bg-muted",
        destructive: "bg-destructive text-white hover:opacity-90",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        sm: "min-h-[var(--tap-min)] px-3 text-app-sm",
        md: "min-h-[var(--button-height)] px-4 text-app",
        lg: "min-h-[calc(var(--button-height)*1.25)] px-6 text-app-md",
        icon: "min-h-[var(--tap-min)] w-[var(--tap-min)] p-0",
      },
    },
    defaultVariants: {
      variant: "primary",
      size: "md",
    },
  },
);

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

export function Button({ className, variant, size, type = "button", ...props }: ButtonProps) {
  return (
    <button type={type} className={cn(buttonVariants({ variant, size }), className)} {...props} />
  );
}
