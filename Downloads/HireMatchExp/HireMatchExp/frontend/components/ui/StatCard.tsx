"use client";

import React, { useState } from "react";
import { cn } from "@/lib/utils";

export interface StatCardProps {
  title: string;
  value: string | number;
  description?: string;
  icon?: React.ReactNode;
  trend?: {
    value: string;
    isPositive?: boolean;
  };
  accentColor?: "blue" | "emerald" | "amber" | "violet" | "rose";
  className?: string;
}

export function StatCard({
  title,
  value,
  description,
  icon,
  trend,
  accentColor = "blue",
  className,
}: StatCardProps) {
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const [isHovered, setIsHovered] = useState(false);

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    setMousePos({ x: e.clientX - rect.left, y: e.clientY - rect.top });
  };

  return (
    <div
      onMouseMove={handleMouseMove}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      className={cn(
        "relative overflow-hidden rounded-xl border border-stone-300 bg-white p-5 shadow-subtle transition-all duration-200 hover:border-stone-400 hover:shadow-card group",
        className
      )}
    >
      {/* Interactive Cursor Spotlight Glow */}
      <div
        className="pointer-events-none absolute inset-0 opacity-0 transition-opacity duration-300 group-hover:opacity-100"
        style={{
          background: isHovered
            ? `radial-gradient(200px circle at ${mousePos.x}px ${mousePos.y}px, rgba(41, 43, 39, 0.04), transparent 70%)`
            : undefined,
        }}
        aria-hidden="true"
      />

      <div className="relative z-10 flex items-center justify-between">
        <span className="text-xs font-medium text-stone-500 uppercase tracking-wider">{title}</span>
        {icon && (
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-olive-50/80 border border-olive-200/80 text-olive-800 group-hover:bg-olive-100/80 transition-colors">
            {icon}
          </div>
        )}
      </div>

      <div className="relative z-10 mt-3 flex items-baseline gap-2">
        <div className="text-2xl font-semibold tracking-tight text-stone-900 tabular-nums">
          {value}
        </div>
        {trend && (
          <span
            className={cn(
              "text-xs font-medium",
              trend.isPositive ? "text-olive-700" : "text-terracotta-600"
            )}
          >
            {trend.value}
          </span>
        )}
      </div>

      {description && (
        <p className="relative z-10 mt-1.5 text-xs text-stone-500 line-clamp-1">{description}</p>
      )}
    </div>
  );
}
