"use client";

import React from "react";
import { cn } from "@/lib/utils";

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  selectable?: boolean;
  selected?: boolean;
  header?: React.ReactNode;
  footer?: React.ReactNode;
}

export const Card: React.FC<CardProps> = ({
  children,
  header,
  footer,
  selectable = false,
  selected = false,
  className,
  tabIndex,
  ...props
}) => {
  return (
    <div
      tabIndex={selectable ? (tabIndex ?? 0) : tabIndex}
      role={selectable ? "button" : undefined}
      aria-pressed={selectable ? selected : undefined}
      className={cn(
        "rounded-xl backdrop-blur-md bg-space-navy/70 border border-white/10 text-apptext-primary transition-all",
        selectable &&
          "cursor-pointer hover:border-white/20 hover:bg-space-surface focus:outline-none focus-visible:outline-2 focus-visible:outline-sky-400 focus-visible:outline-offset-2",
        selected && "border-cyan-400/80 shadow-glowCyan bg-space-surface",
        className
      )}
      {...props}
    >
      {header && (
        <div className="px-4 py-3 border-b border-white/10 flex items-center justify-between">
          {header}
        </div>
      )}
      <div className="p-4">{children}</div>
      {footer && (
        <div className="px-4 py-3 border-t border-white/10 bg-white/[0.02]">
          {footer}
        </div>
      )}
    </div>
  );
};
