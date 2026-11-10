"use client";

import React, { useState } from "react";
import { Telescope, Search, HelpCircle, Info, Sparkles } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Tooltip } from "@/components/ui/Tooltip";
import { Button } from "@/components/ui/Button";
import { useData } from "@/lib/DataProvider";
import { useBeginnerMode } from "@/lib/BeginnerModeContext";
import { AboutModal } from "./AboutModal";

export const TopBar: React.FC = () => {
  const { isSynthetic, data } = useData();
  const { isBeginnerMode, toggleBeginnerMode } = useBeginnerMode();
  const [isAboutOpen, setIsAboutOpen] = useState(false);

  const regionName = data?.region?.name ?? "Loading field...";

  return (
    <>
      <header
        role="banner"
        className="sticky top-0 z-sticky w-full h-16 border-b border-white/10 bg-space-deep/90 backdrop-blur-md px-4 lg:px-6 flex items-center justify-between gap-4 select-none"
      >
        {/* Wordmark and Region */}
        <div className="flex items-center gap-3 shrink-0">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-cyan-500/20 to-blue-600/30 border border-cyan-400/40 flex items-center justify-center shadow-glowCyan">
            <Telescope className="w-5 h-5 text-cyan-300" aria-hidden="true" />
          </div>
          <div>
            <h1 className="text-base font-bold tracking-tight text-apptext-primary flex items-center gap-2">
              <span>SPHEREx Sky Diary</span>
            </h1>
            <p className="text-xs text-apptext-muted hidden sm:block">
              Field: <span className="text-cyan-300 font-mono">{regionName}</span>
            </p>
          </div>
        </div>

        {/* Global Persistent TEST DATA Banner / Badge (Task 7) */}
        {isSynthetic && (
          <div className="flex items-center">
            <Tooltip
              content="Synthetic data for testing. Not a real SPHEREx detection."
              position="bottom"
            >
              <div tabIndex={0} className="focus:outline-none focus-visible:outline-2 focus-visible:outline-rose-400 rounded-full">
                <Badge variant="testData" className="cursor-help py-1 px-3" />
              </div>
            </Tooltip>
          </div>
        )}

        {/* Search placeholder (Non-functional until Module 7) */}
        <div className="hidden md:flex items-center flex-1 max-w-xs mx-2">
          <div className="relative w-full">
            <Search className="w-4 h-4 text-apptext-muted absolute left-3 top-1/2 -translate-y-1/2" aria-hidden="true" />
            <input
              type="text"
              disabled
              placeholder="Search RA/Dec or object... (Module 7)"
              aria-label="Search sky target coordinates"
              className="w-full pl-9 pr-3 py-1.5 text-xs rounded-lg bg-space-surface/80 border border-white/10 text-apptext-muted cursor-not-allowed"
            />
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2">
          {/* Beginner Mode Toggle */}
          <Tooltip
            content={
              isBeginnerMode
                ? "Beginner Mode: Detailed astronomical explanations enabled"
                : "Expert Mode: Compact scientific views"
            }
            position="bottom"
          >
            <Button
              variant="secondary"
              size="sm"
              onClick={toggleBeginnerMode}
              aria-pressed={isBeginnerMode}
              aria-label={`Toggle beginner guidance mode (${isBeginnerMode ? "Enabled" : "Disabled"})`}
              className="text-xs"
            >
              <Sparkles className={isBeginnerMode ? "w-3.5 h-3.5 text-amber-400" : "w-3.5 h-3.5 text-apptext-muted"} aria-hidden="true" />
              <span className="hidden sm:inline">Guide</span>
            </Button>
          </Tooltip>

          {/* About / Attribution Modal Trigger */}
          <Button
            variant="ghost"
            size="sm"
            isIconOnly
            onClick={() => setIsAboutOpen(true)}
            aria-label="Open About and Data Attribution modal"
          >
            <Info className="w-4 h-4" aria-hidden="true" />
          </Button>
        </div>
      </header>

      <AboutModal isOpen={isAboutOpen} onClose={() => setIsAboutOpen(false)} />
    </>
  );
};
