import React from "react";
import { cn, getFitTierBadgeClass, getStatusBadgeClass } from "@/lib/utils";

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: "default" | "success" | "warning" | "danger" | "info" | "outline";
  tier?: string;
  status?: string;
  size?: "sm" | "md";
}

export function Badge({
  className,
  variant = "default",
  tier,
  status,
  size = "md",
  children,
  ...props
}: BadgeProps) {
  let computedClass = "";

  if (tier) {
    computedClass = getFitTierBadgeClass(tier);
  } else if (status) {
    computedClass = getStatusBadgeClass(status);
  } else {
    switch (variant) {
      case "success":
        computedClass = "bg-olive-50 text-olive-800 border-olive-200";
        break;
      case "warning":
        computedClass = "bg-stone-100 text-stone-700 border-stone-300";
        break;
      case "danger":
        computedClass = "bg-terracotta-50 text-terracotta-700 border-terracotta-200";
        break;
      case "info":
        computedClass = "bg-sage-50 text-stone-800 border-sage-200";
        break;
      case "outline":
        computedClass = "bg-transparent text-stone-700 border-stone-300";
        break;
      default:
        computedClass = "bg-stone-100 text-stone-700 border-stone-300";
    }
  }

  const sizeClass = size === "sm" ? "px-2 py-0.5 text-xs" : "px-2.5 py-1 text-xs";

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 font-medium rounded-md border transition-colors select-none",
        sizeClass,
        computedClass,
        className
      )}
      {...props}
    >
      {children}
    </span>
  );
}
