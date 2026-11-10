"use client";

import React, { useState } from "react";
import { TopBar } from "./TopBar";
import { Panel } from "@/components/ui/Panel";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { useData } from "@/lib/DataProvider";
import { Layers, ChevronUp, ChevronDown, Compass, Clock, ListFilter } from "lucide-react";

export interface AppShellProps {
  children?: React.ReactNode;
}

export const AppShell: React.FC<AppShellProps> = ({ children }) => {
  const { data, status, error, reload } = useData();
  const [mobileSheetState, setMobileSheetState] = useState<"collapsed" | "half" | "full">("half");

  const movers = data?.movers || [];
  const knownCount = movers.filter((m) => m.type === "known").length;
  const unknownCount = movers.filter((m) => m.type === "unknown").length;

  return (
    <div className="min-h-screen bg-space-deep text-apptext-primary flex flex-col antialiased selection:bg-cyan-500/30 selection:text-cyan-200">
      {/* Accessible Skip Link */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-tooltip focus:px-4 focus:py-2 focus:bg-cyan-500 focus:text-space-deep focus:font-bold focus:rounded-lg focus:shadow-xl"
      >
        Skip to main content
      </a>

      {/* Top Header */}
      <TopBar />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col lg:flex-row overflow-hidden relative">
        {/* Primary Viewport (Sky Viewer & Time-bar) */}
        <main
          id="main-content"
          role="main"
          className="flex-1 flex flex-col p-3 lg:p-4 gap-3 lg:gap-4 overflow-y-auto lg:overflow-hidden relative"
        >
          {/* Sky Viewer Slot (Module 7 Placeholder) */}
          <div
            id="sky-viewer-slot"
            className="flex-1 min-h-[380px] lg:min-h-0 rounded-2xl bg-space-navy/50 border border-white/10 backdrop-blur-md flex flex-col items-center justify-center relative p-6 text-center shadow-glass group"
          >
            <div className="w-16 h-16 rounded-full bg-cyan-500/10 border border-cyan-400/30 flex items-center justify-center mb-3 group-hover:scale-105 transition-transform">
              <Compass className="w-8 h-8 text-cyan-300" aria-hidden="true" />
            </div>
            <h2 className="text-lg font-bold text-apptext-primary">
              Aladin Lite Sky Viewer
            </h2>
            <p className="text-xs text-apptext-muted max-w-sm mt-1">
              Interactive multi-epoch SPHEREx sky map tiles and candidate overlays will render here in Module 7.
            </p>
            <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
              <span className="text-xs font-mono px-3 py-1 rounded-full bg-white/5 border border-white/10 text-apptext-secondary">
                RA: {data?.region?.ra_center ?? 60.0}° | Dec: {data?.region?.dec_center ?? 20.0}°
              </span>
              <span className="text-xs font-mono px-3 py-1 rounded-full bg-white/5 border border-white/10 text-apptext-secondary">
                FOV: {data?.fov_deg ?? 0.2}°
              </span>
            </div>
          </div>

          {/* Time-lapse Epoch Controls Slot (Module 7 Placeholder) */}
          <div
            id="time-controls-slot"
            className="h-24 shrink-0 rounded-xl bg-space-navy/70 border border-white/10 backdrop-blur-md p-4 flex items-center justify-between shadow-glass"
          >
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-white/5 text-cyan-300">
                <Clock className="w-5 h-5" aria-hidden="true" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-apptext-primary">
                  Time-lapse Blink & Epoch Slider
                </h3>
                <p className="text-xs text-apptext-muted">
                  Multi-epoch animation and playback controls load here in Module 7.
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Badge variant="neutral" label={`${data?.epochs?.length ?? 0} Epochs Loaded`} />
            </div>
          </div>
        </main>

        {/* Desktop Side Panel (>= 1024px) (Module 8 Placeholder) */}
        <aside
          role="complementary"
          aria-label="Moving Object Candidates and Spectra Details"
          className="hidden lg:flex w-96 shrink-0 border-l border-white/10 bg-space-deep/80 backdrop-blur-md flex-col p-4 gap-4 overflow-y-auto"
        >
          {/* Overview Card */}
          <Panel title="Candidate Summary">
            <div className="grid grid-cols-2 gap-2 text-center">
              <div className="p-3 rounded-xl bg-cyan-950/30 border border-cyan-800/40">
                <p className="text-xs text-cyan-300 font-medium">Known Asteroids</p>
                <p className="text-2xl font-bold font-mono text-cyan-200 mt-1">{knownCount}</p>
              </div>
              <div className="p-3 rounded-xl bg-amber-950/30 border border-amber-800/40">
                <p className="text-xs text-amber-300 font-medium">Unknown Movers</p>
                <p className="text-2xl font-bold font-mono text-amber-200 mt-1">{unknownCount}</p>
              </div>
            </div>
          </Panel>

          {/* Movers List Slot (Module 8 Placeholder) */}
          <div
            id="movers-list-slot"
            className="flex-1 rounded-xl bg-space-navy/40 border border-white/10 p-4 flex flex-col items-center justify-center text-center"
          >
            <ListFilter className="w-8 h-8 text-apptext-muted mb-2" aria-hidden="true" />
            <h3 className="text-sm font-semibold text-apptext-primary">
              Candidate Movers List
            </h3>
            <p className="text-xs text-apptext-muted mt-1 max-w-xs">
              Filtering, sorting, and trajectory detail cards will render here in Module 8.
            </p>
          </div>

          {/* Spectrum Detail Slot (Module 8 Placeholder) */}
          <div
            id="spectra-detail-slot"
            className="h-44 rounded-xl bg-space-navy/40 border border-white/10 p-4 flex flex-col items-center justify-center text-center"
          >
            <Layers className="w-8 h-8 text-cyan-400 mb-2" aria-hidden="true" />
            <h3 className="text-sm font-semibold text-apptext-primary">
              102-Channel Spectra Viewer
            </h3>
            <p className="text-xs text-apptext-muted mt-1 max-w-xs">
              Interactive reflectance curves and absorption band diagnostic indices load in Module 8.
            </p>
          </div>
        </aside>

        {/* Mobile Bottom Sheet (< 1024px) */}
        <aside
          role="complementary"
          aria-label="Mobile Candidates Sheet"
          className={`lg:hidden fixed bottom-0 left-0 right-0 z-sticky bg-space-navy/95 border-t border-white/20 backdrop-blur-xl rounded-t-2xl shadow-2xl transition-all duration-300 flex flex-col ${
            mobileSheetState === "collapsed"
              ? "h-14"
              : mobileSheetState === "half"
              ? "h-1/2"
              : "h-[85vh]"
          }`}
        >
          {/* Drag Handle & Toggle Header */}
          <div
            className="h-14 px-4 flex items-center justify-between cursor-pointer border-b border-white/10"
            onClick={() => {
              if (mobileSheetState === "collapsed") setMobileSheetState("half");
              else if (mobileSheetState === "half") setMobileSheetState("full");
              else setMobileSheetState("collapsed");
            }}
          >
            <div className="flex items-center gap-2">
              <span className="w-8 h-1 rounded-full bg-white/20 inline-block mr-2" aria-hidden="true" />
              <span className="text-xs font-bold text-apptext-primary uppercase tracking-wider">
                Movers ({movers.length})
              </span>
              <Badge variant="known" label={`${knownCount}`} />
              <Badge variant="unknown" label={`${unknownCount}`} />
            </div>

            <Button
              variant="ghost"
              size="sm"
              isIconOnly
              aria-label={
                mobileSheetState === "collapsed"
                  ? "Expand candidates bottom sheet"
                  : "Toggle candidates bottom sheet"
              }
              onClick={(e) => {
                e.stopPropagation();
                setMobileSheetState(mobileSheetState === "collapsed" ? "half" : "collapsed");
              }}
            >
              {mobileSheetState === "collapsed" ? (
                <ChevronUp className="w-4 h-4 text-apptext-muted" aria-hidden="true" />
              ) : (
                <ChevronDown className="w-4 h-4 text-apptext-muted" aria-hidden="true" />
              )}
            </Button>
          </div>

          {/* Sheet Body */}
          {mobileSheetState !== "collapsed" && (
            <div className="p-4 flex-1 overflow-y-auto space-y-3">
              <div className="p-3 rounded-xl bg-space-surface border border-white/10 text-center">
                <p className="text-xs text-apptext-muted">
                  Mobile candidates table and spectra viewer load in Module 8.
                </p>
              </div>
            </div>
          )}
        </aside>
      </div>

      {children}
    </div>
  );
};
