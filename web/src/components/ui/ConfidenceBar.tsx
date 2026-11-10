"use client";

import React from "react";
import { cn } from "@/lib/utils";

export interface ConfidenceBarProps extends React.HTMLAttributes<HTMLDivElement> {
  value: number; // 0.0 to 1.0
  label?: string;
  showNumeric?: boolean;
}

export const ConfidenceBar: React.FC<ConfidenceBarProps> = ({
  value,
  label = "Confidence",
  showNumeric = true,
  className,
  ...props
}) => {
  const clamped = Math.max(0.0, Math.min(1.0, value));
  const percentage = Math.round(clamped * 100);

  // High confidence (>85%) cyan, moderate amber, low rose
  const barColor =
    clamped >= 0.85
      ? "bg-cyan-400"
      : clamped >= 0.65
      ? "bg-amber-400"
      : "bg-rose-400";

  return (
    <div className={cn("flex flex-col gap-1 w-full", className)} {...props}>
      <div className="flex items-center justify-between text-xs">
        <span className="text-apptext-muted font-medium">{label}</span>
        {showNumeric && (
          <span className="font-mono text-apptext-primary font-semibold">
            {percentage}%
          </span>
        )}
      </div>
      <div
        role="progressbar"
        aria-label={label}
        aria-valuenow={percentage}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuetext={`${percentage}% confidence`}
        className="w-full h-2 rounded-full bg-white/10 overflow-hidden"
      >
        <div
          className={cn("h-full rounded-full transition-all duration-300", barColor)}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
};
