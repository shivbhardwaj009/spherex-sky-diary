"use client";

import React from "react";
import { cn } from "@/lib/utils";
import { CheckCircle2, HelpCircle, AlertTriangle, Database } from "lucide-react";

export type BadgeVariant = "known" | "unknown" | "testData" | "offline" | "neutral";

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant: BadgeVariant;
  label?: string;
  showIcon?: boolean;
}

export const Badge: React.FC<BadgeProps> = ({
  variant,
  label,
  showIcon = true,
  className,
  children,
  ...props
}) => {
  const configs = {
    known: {
      defaultLabel: "Known Asteroid",
      icon: CheckCircle2,
      styles:
        "bg-cyan-500/15 text-cyan-200 border border-cyan-400/40 shadow-glowCyan",
      iconClass: "text-cyan-400",
    },
    unknown: {
      defaultLabel: "Unknown Mover",
      icon: HelpCircle,
      styles:
        "bg-amber-500/15 text-amber-200 border border-amber-400/40 shadow-glowAmber",
      iconClass: "text-amber-400",
    },
    testData: {
      defaultLabel: "TEST DATA",
      icon: AlertTriangle,
      styles:
        "bg-rose-500/20 text-rose-100 border border-rose-500 shadow-glowRose font-bold tracking-wide",
      iconClass: "text-rose-400",
    },
    offline: {
      defaultLabel: "Offline Catalog",
      icon: Database,
      styles:
        "bg-slate-500/15 text-slate-200 border border-slate-400/35",
      iconClass: "text-slate-400",
    },
    neutral: {
      defaultLabel: "",
      icon: null,
      styles:
        "bg-white/5 text-apptext-secondary border border-white/10",
      iconClass: "text-apptext-muted",
    },
  };

  const config = configs[variant] || configs.neutral;
  const Icon = config.icon;
  const displayLabel = label || children || config.defaultLabel;

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-semibold rounded-full select-none transition-colors",
        config.styles,
        className
      )}
      {...props}
    >
      {showIcon && Icon && <Icon className={cn("w-3.5 h-3.5 shrink-0", config.iconClass)} aria-hidden="true" />}
      <span>{displayLabel}</span>
    </span>
  );
};
