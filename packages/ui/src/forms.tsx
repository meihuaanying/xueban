"use client";

import type { InputHTMLAttributes, LabelHTMLAttributes, SelectHTMLAttributes, TextareaHTMLAttributes } from "react";
import { forwardRef } from "react";

import { cn } from "./cn";

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  invalid?: boolean;
}

/** 文本输入框 */
export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { className, invalid, ...props },
  ref,
) {
  return (
    <input
      ref={ref}
      aria-invalid={invalid || undefined}
      className={cn(
        "flex h-10 w-full rounded-lg border border-input bg-card px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50",
        invalid && "border-destructive focus-visible:ring-destructive",
        className,
      )}
      {...props}
    />
  );
});

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  invalid?: boolean;
}

/** 多行文本输入 */
export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea(
  { className, invalid, ...props },
  ref,
) {
  return (
    <textarea
      ref={ref}
      aria-invalid={invalid || undefined}
      className={cn(
        "flex min-h-24 w-full rounded-lg border border-input bg-card px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50",
        invalid && "border-destructive",
        className,
      )}
      {...props}
    />
  );
});

/** 表单标签 */
export function Label({ className, ...props }: LabelHTMLAttributes<HTMLLabelElement>) {
  return (
    <label className={cn("text-sm font-medium text-foreground", className)} {...props} />
  );
}

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  options: { value: string; label: string }[];
  placeholder?: string;
}

/** 下拉选择（原生控件，保证可访问性） */
export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { className, options, placeholder, ...props },
  ref,
) {
  return (
    <select
      ref={ref}
      className={cn(
        "flex h-10 w-full rounded-lg border border-input bg-card px-3 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      {...props}
    >
      {placeholder ? <option value="">{placeholder}</option> : null}
      {options.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  );
});

export interface CheckboxProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
}

/** 复选框 */
export const Checkbox = forwardRef<HTMLInputElement, CheckboxProps>(function Checkbox(
  { className, label, id, ...props },
  ref,
) {
  const inputId = id ?? (label ? `checkbox-${label}` : undefined);
  return (
    <span className="inline-flex items-center gap-2">
      <input
        ref={ref}
        id={inputId}
        type="checkbox"
        className={cn(
          "h-4 w-4 rounded border-input text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
          className,
        )}
        {...props}
      />
      {label ? (
        <label htmlFor={inputId} className="text-sm text-foreground">
          {label}
        </label>
      ) : null}
    </span>
  );
});

export interface SwitchProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "type"> {
  label?: string;
}

/** 开关 */
export const Switch = forwardRef<HTMLInputElement, SwitchProps>(function Switch(
  { className, label, id, ...props },
  ref,
) {
  const inputId = id ?? (label ? `switch-${label}` : undefined);
  return (
    <span className="inline-flex items-center gap-2">
      <input
        ref={ref}
        id={inputId}
        type="checkbox"
        role="switch"
        className={cn("h-5 w-9 appearance-none rounded-full bg-muted transition-colors checked:bg-primary", className)}
        {...props}
      />
      {label ? (
        <label htmlFor={inputId} className="text-sm text-foreground">
          {label}
        </label>
      ) : null}
    </span>
  );
});
