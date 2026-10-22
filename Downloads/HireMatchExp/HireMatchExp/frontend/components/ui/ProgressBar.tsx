import React from "react";
import { cn, getScoreBadgeColor } from "@/lib/utils";

export interface ProgressBarProps {
  value: number; // 0 to 100
  max?: number;
  className?: string;
  barClassName?: string;
  trackClassName?: string;
  showValue?: boolean;
  colorScheme?: "score" | "blue" | "emerald" | "amber" | "violet" | "terra";
  size?: "sm" | "md" | "lg";
}

export function ProgressBar({
  value,
  max = 100,
  className,
  barClassName,
  trackClassName,
  showValue = false,
  colorScheme = "score",
  size = "md",
}: ProgressBarProps) {
  const percentage = Math.min(Math.max(0, (value / max) * 100), 100);

  let barColor = "bg-olive-500";
  if (colorScheme === "score") {
    if (percentage >= 80) barColor = "bg-olive-500";
    else if (percentage >= 60) barColor = "bg-olive-400";
    else if (percentage >= 40) barColor = "bg-stone-400";
    else barColor = "bg-terracotta-500";
  } else if (colorScheme === "blue" || colorScheme === "terra") {
    barColor = "bg-olive-500";
  } else if (colorScheme === "emerald") {
    barColor = "bg-olive-600";
  } else if (colorScheme === "amber") {
    barColor = "bg-stone-500";
  } else if (colorScheme === "violet") {
    barColor = "bg-stone-500";
  }

  const heightClass = {
    sm: "h-1.5",
    md: "h-2.5",
    lg: "h-4",
  }[size];

  return (
    <div className={cn("w-full", className)}>
      {showValue && (
        <div className="mb-1 flex justify-between text-xs text-stone-500">
          <span>Score</span>
          <span className="font-semibold text-charcoal-900">{Math.round(percentage)}%</span>
        </div>
      )}
      <div className={cn("w-full overflow-hidden rounded-full bg-stone-200", heightClass, trackClassName)}>
        <div
          className={cn("h-full rounded-full transition-all duration-500", barClassName || barColor)}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}
