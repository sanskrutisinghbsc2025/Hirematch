import React from "react";
import { cn } from "@/lib/utils";
import { Loader2 } from "lucide-react";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "outline" | "ghost" | "danger";
  size?: "sm" | "md" | "lg" | "icon";
  isLoading?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className,
      variant = "primary",
      size = "md",
      isLoading = false,
      leftIcon,
      rightIcon,
      children,
      disabled,
      ...props
    },
    ref
  ) => {
    const baseStyles =
      "inline-flex items-center justify-center font-medium rounded-lg transition-all duration-150 focus:outline-none focus:ring-2 focus:ring-olive-500/30 focus:ring-offset-2 focus:ring-offset-[#F7F5F0] disabled:opacity-50 disabled:cursor-not-allowed select-none active:scale-[0.98]";

    let variantStyles = "";
    switch (variant) {
      case "primary":
        variantStyles =
          "bg-olive-500 hover:bg-olive-600 text-white border border-olive-600/40 shadow-subtle";
        break;
      case "secondary":
        variantStyles =
          "bg-white hover:bg-stone-50 text-stone-900 border border-stone-300 shadow-subtle hover:border-stone-400";
        break;
      case "outline":
        variantStyles =
          "bg-transparent hover:bg-stone-100 text-stone-900 border border-stone-300 hover:border-stone-400";
        break;
      case "ghost":
        variantStyles =
          "bg-transparent hover:bg-stone-100 text-stone-600 hover:text-stone-900 border border-transparent";
        break;
      case "danger":
        variantStyles =
          "bg-terracotta-50 hover:bg-terracotta-100 text-terracotta-700 border border-terracotta-200";
        break;
    }

    let sizeStyles = "";
    switch (size) {
      case "sm":
        sizeStyles = "h-8 px-3 text-xs gap-1.5";
        break;
      case "md":
        sizeStyles = "h-9 px-4 text-sm gap-2";
        break;
      case "lg":
        sizeStyles = "h-10 px-5 text-sm gap-2";
        break;
      case "icon":
        sizeStyles = "h-9 w-9 p-0 justify-center";
        break;
    }

    return (
      <button
        ref={ref}
        className={cn(baseStyles, variantStyles, sizeStyles, className)}
        disabled={disabled || isLoading}
        {...props}
      >
        {isLoading ? (
          <Loader2 className="h-4 w-4 animate-spin text-current" />
        ) : (
          leftIcon
        )}
        {children}
        {!isLoading && rightIcon}
      </button>
    );
  }
);

Button.displayName = "Button";
