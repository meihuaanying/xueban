"use client";

import {
  type InputHTMLAttributes,
  type LabelHTMLAttributes,
  type TextareaHTMLAttributes,
  forwardRef,
} from "react";

import { cn } from "./cn";

/**
 * 表单控件：高度走 --input-height，圆角走 --r-control，字号走 --text-app-*，
 * 最小热区 --tap-min 兜底 ⇒ kids 主题下输入框自动变高、字变大、圆角变圆。
 */

const controlClass =
  "w-full rounded-control border bg-card px-sm text-app text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50";

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  invalid?: boolean;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { className, invalid, ...props },
  ref,
) {
  return (
    <input
      ref={ref}
      aria-invalid={invalid || undefined}
      className={cn(
        controlClass,
        "min-h-[var(--input-height)] py-xs",
        invalid ? "border-destructive focus-visible:ring-destructive" : "border-input",
        className,
      )}
      {...props}
    />
  );
});

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(
  function Textarea({ className, ...props }, ref) {
    return (
      <textarea
        ref={ref}
        className={cn(controlClass, "min-h-24 border-input py-xs", className)}
        {...props}
      />
    );
  },
);

export function Label({ className, ...props }: LabelHTMLAttributes<HTMLLabelElement>) {
  return <label className={cn("text-app-sm font-medium text-foreground", className)} {...props} />;
}

export interface SelectOption {
  value: string;
  label: string;
}

export interface SelectProps extends Omit<InputHTMLAttributes<HTMLSelectElement>, "children"> {
  options: SelectOption[];
  placeholder?: string;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { className, options, placeholder, ...props },
  ref,
) {
  return (
    <select
      ref={ref}
      className={cn(
        controlClass,
        "min-h-[var(--input-height)] appearance-none border-input py-xs",
        className,
      )}
      {...props}
    >
      {placeholder ? (
        <option value="" disabled>
          {placeholder}
        </option>
      ) : null}
      {options.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  );
});

export interface CheckboxProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "type"> {
  label?: string;
}

export const Checkbox = forwardRef<HTMLInputElement, CheckboxProps>(function Checkbox(
  { className, label, id, ...props },
  ref,
) {
  const inputId = id ?? (label ? `checkbox-${label}` : undefined);
  return (
    <span className="inline-flex items-center gap-xs">
      <input
        ref={ref}
        id={inputId}
        type="checkbox"
        className={cn(
          "size-4 shrink-0 rounded-xs border-input text-primary",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
          "disabled:cursor-not-allowed disabled:opacity-50",
          className,
        )}
        {...props}
      />
      {label ? (
        <label htmlFor={inputId} className="text-app-sm text-foreground">
          {label}
        </label>
      ) : null}
    </span>
  );
});

export interface SwitchProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "type"> {
  label?: string;
}

export const Switch = forwardRef<HTMLInputElement, SwitchProps>(function Switch(
  { className, label, id, ...props },
  ref,
) {
  const inputId = id ?? (label ? `switch-${label}` : undefined);
  return (
    <span className="inline-flex items-center gap-xs">
      <input
        ref={ref}
        id={inputId}
        type="checkbox"
        role="switch"
        className={cn(
          "h-5 w-9 appearance-none rounded-pill bg-muted transition-colors checked:bg-primary",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
          "disabled:cursor-not-allowed disabled:opacity-50",
          className,
        )}
        {...props}
      />
      {label ? (
        <label htmlFor={inputId} className="text-app-sm text-foreground">
          {label}
        </label>
      ) : null}
    </span>
  );
});
