"use client";

import React, { useId } from "react";
import { cn } from "@/lib/utils";
import { Minus, Plus } from "lucide-react";

export interface SliderProps {
  label: string;
  min: number;
  max: number;
  step?: number;
  value: number;
  onChange: (value: number) => void;
  valueDisplay?: string | number;
  className?: string;
}

export const Slider: React.FC<SliderProps> = ({
  label,
  min,
  max,
  step = 1,
  value,
  onChange,
  valueDisplay,
  className,
}) => {
  const sliderId = useId();

  const handleStepDown = () => {
    const nextVal = Math.max(min, value - step);
    onChange(nextVal);
  };

  const handleStepUp = () => {
    const nextVal = Math.min(max, value + step);
    onChange(nextVal);
  };

  return (
    <div className={cn("flex flex-col gap-2 w-full", className)}>
      <div className="flex items-center justify-between text-sm">
        <label htmlFor={sliderId} className="font-medium text-apptext-secondary">
          {label}
        </label>
        <span className="font-mono text-cyan-300 font-semibold bg-cyan-950/60 px-2 py-0.5 rounded border border-cyan-800/60">
          {valueDisplay ?? value}
        </span>
      </div>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={handleStepDown}
          disabled={value <= min}
          aria-label={`Decrease ${label}`}
          className="p-2.5 rounded-lg bg-space-surface border border-white/10 text-apptext-muted hover:text-apptext-primary hover:bg-space-surfaceHover disabled:opacity-30 disabled:pointer-events-none min-h-[44px] min-w-[44px] inline-flex items-center justify-center focus:outline-none focus-visible:outline-2 focus-visible:outline-sky-400"
        >
          <Minus className="w-4 h-4" aria-hidden="true" />
        </button>

        <input
          id={sliderId}
          type="range"
          min={min}
          max={max}
          step={step}
          value={value}
          aria-label={label}
          aria-valuemin={min}
          aria-valuemax={max}
          aria-valuenow={value}
          aria-valuetext={String(valueDisplay ?? value)}
          onChange={(e) => onChange(Number(e.target.value))}
          className="w-full h-2 bg-space-surface rounded-lg appearance-none cursor-pointer accent-cyan-400 focus:outline-none focus-visible:outline-2 focus-visible:outline-sky-400 focus-visible:outline-offset-4"
        />

        <button
          type="button"
          onClick={handleStepUp}
          disabled={value >= max}
          aria-label={`Increase ${label}`}
          className="p-2.5 rounded-lg bg-space-surface border border-white/10 text-apptext-muted hover:text-apptext-primary hover:bg-space-surfaceHover disabled:opacity-30 disabled:pointer-events-none min-h-[44px] min-w-[44px] inline-flex items-center justify-center focus:outline-none focus-visible:outline-2 focus-visible:outline-sky-400"
        >
          <Plus className="w-4 h-4" aria-hidden="true" />
        </button>
      </div>
    </div>
  );
};
