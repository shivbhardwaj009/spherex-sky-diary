"use client";

import React, { useState, useRef } from "react";
import { cn } from "@/lib/utils";

export interface TabItem {
  id: string;
  label: string;
  content: React.ReactNode;
}

export interface TabsProps {
  items: TabItem[];
  defaultTabId?: string;
  onChange?: (id: string) => void;
  className?: string;
}

export const Tabs: React.FC<TabsProps> = ({
  items,
  defaultTabId,
  onChange,
  className,
}) => {
  const [activeTab, setActiveTab] = useState(defaultTabId || items[0]?.id);
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);

  const handleSelect = (id: string) => {
    setActiveTab(id);
    onChange?.(id);
  };

  const handleKeyDown = (e: React.KeyboardEvent, index: number) => {
    let nextIndex = index;
    if (e.key === "ArrowRight") {
      nextIndex = (index + 1) % items.length;
    } else if (e.key === "ArrowLeft") {
      nextIndex = (index - 1 + items.length) % items.length;
    } else if (e.key === "Home") {
      nextIndex = 0;
    } else if (e.key === "End") {
      nextIndex = items.length - 1;
    } else {
      return;
    }

    e.preventDefault();
    tabRefs.current[nextIndex]?.focus();
    handleSelect(items[nextIndex].id);
  };

  return (
    <div className={cn("w-full flex flex-col", className)}>
      <div
        role="tablist"
        aria-orientation="horizontal"
        className="flex items-center gap-1 border-b border-white/10 pb-1"
      >
        {items.map((tab, idx) => {
          const isActive = tab.id === activeTab;
          return (
            <button
              key={tab.id}
              ref={(el) => { tabRefs.current[idx] = el; }}
              role="tab"
              id={`tab-${tab.id}`}
              aria-selected={isActive}
              aria-controls={`panel-${tab.id}`}
              tabIndex={isActive ? 0 : -1}
              onClick={() => handleSelect(tab.id)}
              onKeyDown={(e) => handleKeyDown(e, idx)}
              className={cn(
                "px-4 py-2 text-sm font-medium rounded-lg transition-all min-h-[44px] inline-flex items-center justify-center",
                "focus:outline-none focus-visible:outline-2 focus-visible:outline-sky-400 focus-visible:outline-offset-2",
                isActive
                  ? "bg-cyan-500/15 text-cyan-300 border-b-2 border-cyan-400 font-semibold"
                  : "text-apptext-muted hover:text-apptext-primary hover:bg-white/5"
              )}
            >
              {tab.label}
            </button>
          );
        })}
      </div>
      <div className="pt-4">
        {items.map((tab) => {
          const isActive = tab.id === activeTab;
          return (
            <div
              key={tab.id}
              role="tabpanel"
              id={`panel-${tab.id}`}
              aria-labelledby={`tab-${tab.id}`}
              hidden={!isActive}
              tabIndex={0}
              className={cn(
                "focus:outline-none focus-visible:outline-2 focus-visible:outline-sky-400",
                !isActive && "hidden"
              )}
            >
              {tab.content}
            </div>
          );
        })}
      </div>
    </div>
  );
};
