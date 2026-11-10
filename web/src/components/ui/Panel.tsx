"use client";

import React, { useState } from "react";
import { cn } from "@/lib/utils";
import { ChevronDown, ChevronUp } from "lucide-react";

export interface PanelProps extends React.HTMLAttributes<HTMLDivElement> {
  title: string;
  collapsible?: boolean;
  defaultExpanded?: boolean;
  headerAction?: React.ReactNode;
}

export const Panel: React.FC<PanelProps> = ({
  title,
  collapsible = false,
  defaultExpanded = true,
  headerAction,
  children,
  className,
  id,
  ...props
}) => {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);
  const panelId = id || `panel-${title.toLowerCase().replace(/\s+/g, "-")}`;
  const contentId = `${panelId}-content`;

  return (
    <div
      id={panelId}
      className={cn(
        "rounded-xl backdrop-blur-md bg-space-navy/70 border border-white/10 overflow-hidden shadow-glass",
        className
      )}
      {...props}
    >
      <div className="flex items-center justify-between px-4 py-3 bg-white/[0.03] border-b border-white/10 min-h-[44px]">
        <h2 className="text-sm font-semibold tracking-wide text-apptext-primary uppercase flex items-center gap-2">
          {title}
        </h2>
        <div className="flex items-center gap-2">
          {headerAction}
          {collapsible && (
            <button
              type="button"
              onClick={() => setIsExpanded(!isExpanded)}
              aria-expanded={isExpanded}
              aria-controls={contentId}
              aria-label={isExpanded ? `Collapse ${title}` : `Expand ${title}`}
              className="p-2 text-apptext-muted hover:text-apptext-primary rounded-lg min-h-[44px] min-w-[44px] inline-flex items-center justify-center focus:outline-none focus-visible:outline-2 focus-visible:outline-sky-400"
            >
              {isExpanded ? (
                <ChevronUp className="w-4 h-4" aria-hidden="true" />
              ) : (
                <ChevronDown className="w-4 h-4" aria-hidden="true" />
              )}
            </button>
          )}
        </div>
      </div>
      <div
        id={contentId}
        hidden={collapsible && !isExpanded}
        className={cn("p-4", collapsible && !isExpanded && "hidden")}
      >
        {children}
      </div>
    </div>
  );
};
