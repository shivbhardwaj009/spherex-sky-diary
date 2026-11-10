"use client";

import React from "react";
import { cn } from "@/lib/utils";
import { AlertCircle, RotateCcw } from "lucide-react";
import { Button } from "./Button";

export interface ErrorMessageProps extends React.HTMLAttributes<HTMLDivElement> {
  title?: string;
  message: string;
  onRetry?: () => void;
}

export const ErrorMessage: React.FC<ErrorMessageProps> = ({
  title = "An Error Occurred",
  message,
  onRetry,
  className,
  ...props
}) => {
  return (
    <div
      role="alert"
      className={cn(
        "rounded-xl border border-rose-500/40 bg-rose-950/30 p-4 text-rose-200 flex flex-col gap-3 backdrop-blur-md shadow-glowRose",
        className
      )}
      {...props}
    >
      <div className="flex items-start gap-3">
        <AlertCircle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" aria-hidden="true" />
        <div className="flex-1">
          <h3 className="font-semibold text-rose-100 text-sm">{title}</h3>
          <p className="text-xs text-rose-200/80 mt-1">{message}</p>
        </div>
      </div>
      {onRetry && (
        <div className="self-end">
          <Button
            variant="secondary"
            size="sm"
            onClick={onRetry}
            className="border-rose-500/40 text-rose-200 hover:bg-rose-500/20"
          >
            <RotateCcw className="w-3.5 h-3.5" aria-hidden="true" />
            <span>Try Again</span>
          </Button>
        </div>
      )}
    </div>
  );
};
