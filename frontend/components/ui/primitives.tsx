"use client";

/**
 * Shared UI primitives, owned in-repo (shadcn/ui idiom: copy-in components you
 * control, not a black-box dependency). Tailwind-based, themed via the design
 * tokens in globals.css. Kept in one file at this scale; split later if it grows.
 */
import * as React from "react";

export function cn(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

// ── Button ──────────────────────────────────────────────────────────────────
type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "ghost" | "outline" | "danger";
  size?: "sm" | "md";
};

export function Button({
  variant = "primary",
  size = "md",
  className,
  ...props
}: ButtonProps) {
  const base =
    "inline-flex items-center justify-center gap-2 rounded font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand/40 disabled:opacity-50 disabled:cursor-not-allowed";
  const sizes = { sm: "px-3 py-1.5 text-sm", md: "px-4 py-2 text-sm" };
  const variants = {
    primary: "bg-brand text-white hover:bg-brand-ink",
    ghost: "text-ink-soft hover:bg-surface-2 hover:text-ink",
    outline: "border border-border-strong text-ink hover:bg-surface-2",
    danger: "text-danger hover:bg-[var(--warn-soft)]",
  };
  return (
    <button className={cn(base, sizes[size], variants[variant], className)} {...props} />
  );
}

// ── Card ────────────────────────────────────────────────────────────────────
export function Card({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "rounded border border-border bg-surface shadow-sm",
        className
      )}
      {...props}
    />
  );
}

// ── Badge ───────────────────────────────────────────────────────────────────
export function Badge({
  className,
  ...props
}: React.HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-sm px-2 py-0.5 text-xs font-medium",
        className
      )}
      {...props}
    />
  );
}

// ── Input ───────────────────────────────────────────────────────────────────
export const Input = React.forwardRef<
  HTMLInputElement,
  React.InputHTMLAttributes<HTMLInputElement>
>(function Input({ className, ...props }, ref) {
  return (
    <input
      ref={ref}
      className={cn(
        "w-full rounded-sm border border-border bg-surface px-3 py-2 text-sm text-ink placeholder:text-ink-mute focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/20",
        className
      )}
      {...props}
    />
  );
});

// ── Spinner ─────────────────────────────────────────────────────────────────
export function Spinner({ className }: { className?: string }) {
  return (
    <svg
      className={cn("animate-spin", className)}
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
    >
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeOpacity="0.25" strokeWidth="3" />
      <path d="M22 12a10 10 0 0 0-10-10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}
