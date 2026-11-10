"use client";

import React from "react";
import { cn } from "@/lib/utils";

export interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {}

export const Skeleton: React.FC<SkeletonProps> = ({ className, ...props }) => {
  return (
    <div
      role="status"
      aria-label="Loading content"
      className={cn(
        "animate-pulse rounded-lg bg-white/10 select-none",
        className
      )}
      {...props}
    />
  );
};
