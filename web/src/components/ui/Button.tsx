"use client";

import React, { forwardRef } from "react";
import { cn } from "@/lib/utils";
import { Loader2 } from "lucide-react";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md" | "lg";
  isLoading?: boolean;
  isIconOnly?: boolean;
  "aria-label"?: string;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      children,
      className,
      variant = "primary",
      size = "md",
      isLoading = false,
      isIconOnly = false,
      disabled = false,
      type = "button",
      "aria-label": ariaLabel,
      ...props
    },
    ref
  ) => {
    if (isIconOnly && !ariaLabel && typeof children !== "string") {
      console.warn("Accessible icon-only Button requires an 'aria-label' attribute.");
    }

    const baseStyles =
      "inline-flex items-center justify-center font-medium rounded-lg transition-colors min-h-[44px] min-w-[44px] select-none " +
      "focus:outline-none focus-visible:outline-2 focus-visible:outline-sky-400 focus-visible:outline-offset-2 " +
      "disabled:opacity-50 disabled:cursor-not-allowed disabled:pointer-events-none";

    const variantStyles = {
      primary:
        "bg-cyan-500/20 text-cyan-200 border border-cyan-400/50 hover:bg-cyan-500/30 active:bg-cyan-500/40 shadow-glowCyan",
      secondary:
        "bg-space-navy/70 text-apptext-primary border border-white/10 hover:bg-space-surfaceHover hover:border-white/20 active:bg-space-surface",
      ghost:
        "bg-transparent text-apptext-secondary hover:text-apptext-primary hover:bg-white/5 active:bg-white/10",
      danger:
        "bg-rose-500/20 text-rose-200 border border-rose-500/50 hover:bg-rose-500/30 active:bg-rose-500/40 shadow-glowRose",
    };

    const sizeStyles = {
      sm: isIconOnly ? "p-2 text-sm" : "px-3 py-1.5 text-sm gap-1.5",
      md: isIconOnly ? "p-2.5 text-base" : "px-4 py-2 text-base gap-2",
      lg: isIconOnly ? "p-3 text-lg" : "px-6 py-3 text-lg gap-2.5",
    };

    return (
      <button
        ref={ref}
        type={type}
        disabled={disabled || isLoading}
        aria-label={ariaLabel}
        className={cn(baseStyles, variantStyles[variant], sizeStyles[size], className)}
        {...props}
      >
        {isLoading && <Loader2 className="w-4 h-4 animate-spin shrink-0" aria-hidden="true" />}
        {children}
      </button>
    );
  }
);

Button.displayName = "Button";
