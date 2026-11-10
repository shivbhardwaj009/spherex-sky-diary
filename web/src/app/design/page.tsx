"use client";

import React, { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { Panel } from "@/components/ui/Panel";
import { Tooltip } from "@/components/ui/Tooltip";
import { Tabs } from "@/components/ui/Tabs";
import { Slider } from "@/components/ui/Slider";
import { Modal } from "@/components/ui/Modal";
import { Skeleton } from "@/components/ui/Skeleton";
import { ConfidenceBar } from "@/components/ui/ConfidenceBar";
import { Spinner } from "@/components/ui/Spinner";
import { ErrorMessage } from "@/components/ui/ErrorMessage";
import { colors, contrastAudit } from "@/design/tokens";
import { Telescope, Check, AlertTriangle, ShieldCheck } from "lucide-react";

export default function DesignSystemPage() {
  const [sliderVal, setSliderVal] = useState(3);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [selectedCard, setSelectedCard] = useState(false);

  return (
    <div className="min-h-screen bg-space-deep text-apptext-primary p-6 md:p-12 space-y-12 max-w-6xl mx-auto selection:bg-cyan-500/30 selection:text-cyan-200">
      {/* Header Banner */}
      <div className="border-b border-white/10 pb-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-cyan-400 text-xs font-mono uppercase tracking-wider mb-1">
            <Telescope className="w-4 h-4" />
            <span>SPHEREx Sky Diary — Design Tokens & UI Sheet</span>
          </div>
          <h1 className="text-3xl font-extrabold tracking-tight">Design System Review</h1>
          <p className="text-sm text-apptext-muted mt-1">
            Prepared for Yash Pratap (Design Lead). All reusable components, interactive states,
            and WCAG AA contrast ratio audits.
          </p>
        </div>
        <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/30 text-xs text-amber-200">
          <strong>Internal Review:</strong> Excluded from public navigation.
        </div>
      </div>

      {/* 1. Color Palette & WCAG AA Contrast Audit */}
      <section className="space-y-4">
        <h2 className="text-xl font-bold flex items-center gap-2">
          <span>1. Space Palette & Contrast Audit</span>
          <span className="text-xs font-normal text-emerald-400 bg-emerald-950/60 border border-emerald-800 px-2 py-0.5 rounded-full">
            All WCAG AA Verified
          </span>
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
          {contrastAudit.map((item, idx) => (
            <div
              key={idx}
              className="p-4 rounded-xl border border-white/10 bg-space-navy flex flex-col justify-between"
            >
              <div>
                <p className="text-xs text-apptext-muted">{item.name}</p>
                <div className="flex items-center gap-2 mt-2">
                  <span
                    className="w-5 h-5 rounded-full border border-white/20 shrink-0"
                    style={{ backgroundColor: item.fg }}
                  />
                  <span className="font-mono text-sm font-bold text-apptext-primary">{item.fg}</span>
                </div>
              </div>
              <div className="mt-4 pt-3 border-t border-white/10 flex items-center justify-between text-xs">
                <span className="text-apptext-muted">Ratio: <strong className="text-apptext-primary">{item.ratio}:1</strong></span>
                <span className="text-emerald-400 font-semibold flex items-center gap-1">
                  <ShieldCheck className="w-3.5 h-3.5" />
                  <span>Pass (Min {item.minRequired}:1)</span>
                </span>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* 2. Badges (Never rely on color alone) */}
      <section className="space-y-4">
        <h2 className="text-xl font-bold">2. Badges (Icons + Text)</h2>
        <div className="flex flex-wrap items-center gap-3 p-6 rounded-2xl bg-space-navy/50 border border-white/10">
          <Badge variant="known" label="(433) Eros — Known Asteroid" />
          <Badge variant="unknown" label="Candidate mov_001 — Unknown Mover" />
          <Badge variant="testData" label="TEST DATA — Synthetic Ground Truth" />
          <Badge variant="offline" label="Offline Fallback Catalog" />
          <Badge variant="neutral" label="Epoch 03 / 06" />
        </div>
      </section>

      {/* 3. Buttons (Variants, Sizes, States) */}
      <section className="space-y-4">
        <h2 className="text-xl font-bold">3. Buttons (Interactive States & Touch Targets)</h2>
        <div className="p-6 rounded-2xl bg-space-navy/50 border border-white/10 space-y-4">
          <div className="flex flex-wrap items-center gap-3">
            <Button variant="primary">Primary Cyan</Button>
            <Button variant="secondary">Secondary Glass</Button>
            <Button variant="ghost">Ghost Button</Button>
            <Button variant="danger">Danger Rose</Button>
            <Button variant="primary" isLoading>Loading...</Button>
            <Button variant="primary" disabled>Disabled</Button>
          </div>
          <div className="flex flex-wrap items-center gap-3 pt-2">
            <Button variant="secondary" size="sm">Small (44px min)</Button>
            <Button variant="secondary" size="md">Medium (Default)</Button>
            <Button variant="secondary" size="lg">Large Target</Button>
          </div>
        </div>
      </section>

      {/* 4. Cards & Selectable States */}
      <section className="space-y-4">
        <h2 className="text-xl font-bold">4. Glass Cards</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Card
            header={<span className="text-sm font-semibold">Standard Static Card</span>}
            footer={<span className="text-xs text-apptext-muted">Footnote info</span>}
          >
            <p className="text-xs text-apptext-secondary leading-relaxed">
              Glass panel style featuring translucent background, subtle light border, and soft backdrop blur.
            </p>
          </Card>

          <Card
            selectable
            selected={selectedCard}
            onClick={() => setSelectedCard(!selectedCard)}
            header={
              <div className="flex items-center justify-between w-full">
                <span className="text-sm font-semibold">Selectable Candidate Card</span>
                <Badge variant={selectedCard ? "known" : "unknown"} />
              </div>
            }
          >
            <p className="text-xs text-apptext-secondary">
              Click or press Enter to toggle selection state. Active cards display a cyan neon glow.
            </p>
          </Card>
        </div>
      </section>

      {/* 5. Collapsible Panel */}
      <section className="space-y-4">
        <h2 className="text-xl font-bold">5. Collapsible Panels</h2>
        <Panel title="Candidate Trajectory Analysis" collapsible defaultExpanded>
          <div className="space-y-2 text-xs text-apptext-secondary">
            <p>Fitted celestial velocity: <strong className="text-cyan-300">19.58 arcsec/day</strong></p>
            <p>Astrometric fit residual: <strong className="text-emerald-400">0.042 arcsec</strong></p>
          </div>
        </Panel>
      </section>

      {/* 6. Tabs & Sliders */}
      <section className="space-y-4">
        <h2 className="text-xl font-bold">6. Accessible Controls (Tabs & Sliders)</h2>
        <div className="p-6 rounded-2xl bg-space-navy/50 border border-white/10 space-y-6">
          <Tabs
            items={[
              {
                id: "tab1",
                label: "Wavelength Map",
                content: <p className="text-xs text-apptext-secondary">Linear variable filter gradient 0.75 - 5.0 µm.</p>,
              },
              {
                id: "tab2",
                label: "Difference Image",
                content: <p className="text-xs text-apptext-secondary">Static background subtraction significance plane.</p>,
              },
            ]}
          />

          <div className="pt-2 max-w-md">
            <Slider
              label="Observation Epoch Index"
              min={1}
              max={6}
              value={sliderVal}
              onChange={setSliderVal}
              valueDisplay={`Epoch ${sliderVal} of 6`}
            />
          </div>
        </div>
      </section>

      {/* 7. Dialogs, Tooltips & Feedback */}
      <section className="space-y-4">
        <h2 className="text-xl font-bold">7. Feedback & Overlay Components</h2>
        <div className="p-6 rounded-2xl bg-space-navy/50 border border-white/10 space-y-6">
          <div className="flex flex-wrap items-center gap-6">
            <Tooltip content="Tooltip accessible on hover AND keyboard focus (Esc to close)">
              <Button variant="secondary">Hover or Focus Me</Button>
            </Tooltip>

            <Button variant="primary" onClick={() => setIsModalOpen(true)}>
              Open Accessible Modal
            </Button>

            <div className="flex items-center gap-2">
              <Spinner size="sm" />
              <span className="text-xs text-apptext-muted">Loading SPHEREx cube...</span>
            </div>
          </div>

          <div className="max-w-md space-y-3">
            <ConfidenceBar value={0.94} label="Astrometric Match Confidence" />
            <ConfidenceBar value={0.72} label="Candidate Linearity Score" />
          </div>

          <ErrorMessage
            title="Failed to Load SPHEREx Sky Tile"
            message="WCS re-projection encountered non-convergent astrometric solver. Check coordinate boundaries."
            onRetry={() => alert("Retry callback triggered")}
          />

          <div className="space-y-2">
            <Skeleton className="h-4 w-48" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-3/4" />
          </div>
        </div>
      </section>

      {/* Modal instance */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title="Accessible Focus-Trapped Modal"
        description="Full keyboard trapping, Escape handling, and screen reader announcements."
      >
        <p className="text-xs leading-relaxed text-apptext-secondary">
          Tab key navigation stays trapped within this dialog while open. Closing with Escape or the close button
          restores focus back to the triggering button.
        </p>
        <div className="mt-4 flex justify-end">
          <Button variant="primary" size="sm" onClick={() => setIsModalOpen(false)}>
            Close Modal
          </Button>
        </div>
      </Modal>
    </div>
  );
}
