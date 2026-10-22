"use client";

import React, { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Layers,
  PlusCircle,
  LineChart,
  Settings,
  PanelLeftClose,
  PanelLeftOpen,
  Menu,
  X,
  ChevronLeft,
  ChevronRight,
  Activity,
  CheckCircle2,
  AlertCircle,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { apiClient } from "@/lib/api/client";

interface NavItem {
  name: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  description?: string;
  badge?: string;
}

const navItems: NavItem[] = [
  { name: "Dashboard", href: "/", icon: LayoutDashboard, description: "Overview & key screening metrics" },
  { name: "Screenings", href: "/screenings", icon: Layers, description: "All candidate evaluation batches" },
  { name: "New Screening", href: "/screenings/new", icon: PlusCircle, description: "Upload JD and candidate resumes" },
  { name: "Business Analytics", href: "/business-analytics", icon: LineChart, description: "Pipeline velocity & quality insights" },
  { name: "Settings", href: "/settings", icon: Settings, description: "Scoring weights & model parameters" },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [apiOnline, setApiOnline] = useState<boolean | null>(null);
  const [isCollapsed, setIsCollapsed] = useState<boolean>(false);
  const [mobileOpen, setMobileOpen] = useState<boolean>(false);
  const [mounted, setMounted] = useState<boolean>(false);

  // Restore saved collapse preference on mount (avoid hydration mismatch)
  useEffect(() => {
    setMounted(true);
    try {
      const saved = localStorage.getItem("hirematch_sidebar_collapsed");
      if (saved !== null) {
        setIsCollapsed(saved === "true");
      }
    } catch {}
  }, []);

  const toggleCollapsed = useCallback(() => {
    setIsCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem("hirematch_sidebar_collapsed", String(next));
      } catch {}
      return next;
    });
  }, []);

  // Close mobile drawer on route change
  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  // Global keyboard shortcuts (Ctrl+B / Cmd+B for desktop toggle, Escape for mobile drawer)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "b") {
        e.preventDefault();
        toggleCollapsed();
      } else if (e.key === "Escape" && mobileOpen) {
        setMobileOpen(false);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [toggleCollapsed, mobileOpen]);

  // Health check polling
  useEffect(() => {
    let isSubscribed = true;
    const checkHealth = async () => {
      try {
        const res = await apiClient.getHealth();
        if (isSubscribed) setApiOnline(res.status === "healthy" || res.status === "ok");
      } catch (err) {
        try {
          const direct = await fetch("http://127.0.0.1:8000/api/health", { cache: "no-store" });
          if (direct.ok) {
            const data = await direct.json();
            if (isSubscribed) {
              setApiOnline(data.status === "healthy" || data.status === "ok");
              return;
            }
          }
        } catch {
          // Direct check failed
        }
        if (isSubscribed) setApiOnline(false);
      }
    };

    checkHealth();
    const interval = setInterval(checkHealth, 5000);
    return () => {
      isSubscribed = false;
      clearInterval(interval);
    };
  }, []);

  const triggerHealthRetry = async () => {
    setApiOnline(null);
    try {
      const res = await apiClient.getHealth();
      setApiOnline(res.status === "healthy" || res.status === "ok");
    } catch {
      try {
        const direct = await fetch("http://127.0.0.1:8000/api/health", { cache: "no-store" });
        if (direct.ok) {
          const data = await direct.json();
          setApiOnline(data.status === "healthy" || data.status === "ok");
          return;
        }
      } catch {}
      setApiOnline(false);
    }
  };

  const activePage = navItems.find((item) =>
    item.href === "/"
      ? pathname === "/"
      : pathname === item.href || pathname.startsWith(item.href + "/")
  );

  return (
    <div className="flex min-h-screen bg-slate-50 text-slate-900">
      {/* ─────────────────────────────────────────────────────────────
          1. MOBILE BACKDROP & DRAWER (screens < lg)
         ───────────────────────────────────────────────────────────── */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-slate-900/50 backdrop-blur-xs lg:hidden transition-opacity duration-300"
          onClick={() => setMobileOpen(false)}
          aria-hidden="true"
        />
      )}

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex w-72 flex-col bg-white border-r border-slate-200 shadow-2xl transition-transform duration-300 ease-in-out lg:hidden",
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        )}
        aria-label="Mobile Navigation"
      >
        {/* Mobile Drawer Header */}
        <div className="flex h-14 items-center justify-between border-b border-slate-200 px-5">
          <Link
            href="/"
            onClick={() => setMobileOpen(false)}
            className="flex items-center gap-2.5 group"
          >
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-blue-600 text-white font-bold text-xs shadow-xs">
              H
            </span>
            <span className="font-bold text-slate-900 text-base tracking-tight">
              HireMatch
            </span>
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 border border-slate-200 font-semibold ml-1">
              v1.0
            </span>
          </Link>

          <button
            type="button"
            onClick={() => setMobileOpen(false)}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
            aria-label="Close navigation drawer"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Mobile Navigation Links */}
        <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-1">
          <p className="text-[10px] font-semibold tracking-wider text-slate-400 uppercase px-3 mb-2">
            Workspace
          </p>
          {navItems.map((item) => {
            const isActive =
              item.href === "/"
                ? pathname === "/"
                : pathname === item.href || pathname.startsWith(item.href + "/");
            const Icon = item.icon;

            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setMobileOpen(false)}
                className={cn(
                  "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all duration-200 relative select-none",
                  isActive
                    ? "bg-blue-50/90 text-blue-900 font-semibold border border-blue-200 shadow-xs before:absolute before:left-1 before:top-2.5 before:bottom-2.5 before:w-1 before:bg-blue-600 before:rounded-full"
                    : "text-slate-600 hover:bg-slate-100/80 hover:text-slate-900 border border-transparent"
                )}
              >
                <Icon
                  className={cn(
                    "h-4 w-4 flex-shrink-0 transition-colors",
                    isActive ? "text-blue-600" : "text-slate-400"
                  )}
                />
                <div className="flex flex-col">
                  <span className="leading-tight">{item.name}</span>
                  {item.description && (
                    <span className="text-[11px] text-slate-400 font-normal">
                      {item.description}
                    </span>
                  )}
                </div>
              </Link>
            );
          })}
        </nav>

        {/* Mobile Footer Status */}
        <div className="border-t border-slate-200 px-5 py-3.5 bg-slate-50/70">
          <button
            type="button"
            onClick={triggerHealthRetry}
            className="flex items-center gap-2 text-xs text-slate-600 hover:text-slate-900 transition-colors w-full"
          >
            <span
              className={cn(
                "h-2 w-2 rounded-full flex-shrink-0 transition-all",
                apiOnline === true
                  ? "bg-emerald-500 ring-2 ring-emerald-200"
                  : apiOnline === false
                  ? "bg-rose-500 animate-pulse ring-2 ring-rose-200"
                  : "bg-slate-400"
              )}
            />
            <span className="font-medium text-[11px] truncate">
              {apiOnline === true
                ? "API Online · Connected"
                : apiOnline === false
                ? "API Offline (Click to retry)"
                : "Checking connection…"}
            </span>
          </button>
        </div>
      </aside>

      {/* ─────────────────────────────────────────────────────────────
          2. DESKTOP COLLAPSIBLE SIDEBAR (screens >= lg)
         ───────────────────────────────────────────────────────────── */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 hidden lg:flex flex-col border-r border-slate-200 bg-white shadow-xs transition-all duration-300 ease-in-out select-none",
          isCollapsed ? "w-[72px]" : "w-60"
        )}
        aria-label="Desktop Navigation Sidebar"
      >
        {/* Brand Area */}
        <div
          className={cn(
            "flex h-14 items-center border-b border-slate-200 transition-all duration-300",
            isCollapsed ? "justify-center px-2" : "justify-between px-4"
          )}
        >
          <Link
            href="/"
            className={cn(
              "flex items-center gap-2.5 group transition-all",
              isCollapsed && "justify-center"
            )}
            title="HireMatch Home"
          >
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-blue-600 text-white font-bold text-xs shadow-xs group-hover:scale-105 transition-transform flex-shrink-0">
              H
            </span>
            {!isCollapsed && (
              <div className="flex items-center gap-2 overflow-hidden whitespace-nowrap">
                <span className="font-bold text-slate-900 text-base tracking-tight">
                  HireMatch
                </span>
                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 border border-slate-200 font-semibold">
                  v1.0
                </span>
              </div>
            )}
          </Link>

          {/* Collapse button on top when expanded */}
          {!isCollapsed && (
            <button
              type="button"
              onClick={toggleCollapsed}
              className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
              title="Collapse navigation (Ctrl+B)"
              aria-label="Collapse navigation"
            >
              <PanelLeftClose className="h-4 w-4" />
            </button>
          )}
        </div>

        {/* Navigation Items */}
        <nav className="flex-1 overflow-y-auto px-2.5 py-4 space-y-1">
          {!isCollapsed && (
            <div className="flex items-center justify-between px-2.5 mb-2">
              <p className="text-[10px] font-semibold tracking-wider text-slate-400 uppercase">
                Workspace
              </p>
              <span className="text-[10px] text-slate-400 font-mono tracking-tighter">
                Ctrl+B
              </span>
            </div>
          )}

          {navItems.map((item) => {
            const isActive =
              item.href === "/"
                ? pathname === "/"
                : pathname === item.href || pathname.startsWith(item.href + "/");
            const Icon = item.icon;

            return (
              <div key={item.href} className="relative group">
                <Link
                  href={item.href}
                  className={cn(
                    "flex items-center rounded-lg transition-all duration-200 select-none relative",
                    isCollapsed
                      ? "justify-center h-10 w-10 mx-auto"
                      : "gap-2.5 px-3 py-2 text-xs sm:text-sm",
                    isActive
                      ? isCollapsed
                        ? "bg-blue-600 text-white shadow-xs ring-2 ring-blue-300"
                        : "bg-blue-50/80 text-blue-900 font-semibold border border-blue-200/80 shadow-xs pl-3.5 before:absolute before:left-1 before:top-2 before:bottom-2 before:w-1 before:bg-blue-600 before:rounded-full"
                      : "text-slate-600 hover:bg-slate-100/70 hover:text-slate-900 border border-transparent"
                  )}
                  aria-current={isActive ? "page" : undefined}
                >
                  <Icon
                    className={cn(
                      "flex-shrink-0 transition-colors",
                      isCollapsed ? "h-4 w-4" : "h-4 w-4",
                      isActive
                        ? isCollapsed
                          ? "text-white"
                          : "text-blue-600"
                        : "text-slate-400 group-hover:text-slate-600"
                    )}
                  />
                  {!isCollapsed && <span className="truncate">{item.name}</span>}
                </Link>

                {/* Floating Tooltip in Collapsed Rail Mode */}
                {isCollapsed && (
                  <div
                    role="tooltip"
                    className="pointer-events-none invisible opacity-0 group-hover:visible group-hover:opacity-100 transition-all duration-150 absolute left-full top-1/2 -translate-y-1/2 ml-3 z-50 whitespace-nowrap"
                  >
                    <div className="bg-slate-900 text-white text-xs rounded-lg py-1.5 px-3 shadow-xl flex flex-col gap-0.5 border border-slate-800 relative">
                      {/* Left pointer notch */}
                      <span className="absolute right-full top-1/2 -translate-y-1/2 border-4 border-transparent border-r-slate-900" />
                      <div className="flex items-center gap-1.5 font-semibold text-slate-100">
                        <span>{item.name}</span>
                        {isActive && (
                          <span className="text-[10px] text-blue-400 font-mono">
                            (Active)
                          </span>
                        )}
                      </div>
                      {item.description && (
                        <span className="text-[10px] text-slate-400 font-normal">
                          {item.description}
                        </span>
                      )}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </nav>

        {/* Expand Toggle Button in Collapsed Mode */}
        {isCollapsed && (
          <div className="px-2 py-2 border-t border-slate-100 flex justify-center">
            <button
              type="button"
              onClick={toggleCollapsed}
              className="group relative flex h-9 w-9 items-center justify-center rounded-lg text-slate-400 hover:text-slate-900 hover:bg-slate-100 transition-colors"
              title="Expand sidebar (Ctrl+B)"
              aria-label="Expand sidebar"
            >
              <PanelLeftOpen className="h-4 w-4" />
              <div
                role="tooltip"
                className="pointer-events-none invisible opacity-0 group-hover:visible group-hover:opacity-100 transition-all duration-150 absolute left-full top-1/2 -translate-y-1/2 ml-3 z-50 whitespace-nowrap"
              >
                <div className="bg-slate-900 text-white text-xs rounded-md py-1 px-2.5 shadow-xl border border-slate-800">
                  Expand sidebar (Ctrl+B)
                </div>
              </div>
            </button>
          </div>
        )}

        {/* API Health Status Footer */}
        <div
          className={cn(
            "border-t border-slate-200 bg-slate-50/70 transition-all duration-300",
            isCollapsed ? "py-3 px-2 flex justify-center" : "px-4 py-3"
          )}
        >
          {isCollapsed ? (
            <button
              type="button"
              onClick={triggerHealthRetry}
              className="group relative flex h-8 w-8 items-center justify-center rounded-lg hover:bg-slate-200/60 transition-colors"
              title={
                apiOnline === true
                  ? "API Connected (Click to test)"
                  : apiOnline === false
                  ? "API Offline (Click to retry)"
                  : "Checking API connection"
              }
              aria-label="API status"
            >
              <span
                className={cn(
                  "h-2.5 w-2.5 rounded-full flex-shrink-0 transition-all",
                  apiOnline === true
                    ? "bg-emerald-500 ring-2 ring-emerald-200"
                    : apiOnline === false
                    ? "bg-rose-500 animate-pulse ring-2 ring-rose-200"
                    : "bg-slate-400"
                )}
              />
              <div
                role="tooltip"
                className="pointer-events-none invisible opacity-0 group-hover:visible group-hover:opacity-100 transition-all duration-150 absolute left-full top-1/2 -translate-y-1/2 ml-3 z-50 whitespace-nowrap"
              >
                <div className="bg-slate-900 text-white text-xs rounded-md py-1 px-2.5 shadow-xl border border-slate-800">
                  {apiOnline === true
                    ? "API Connected · Click to test"
                    : apiOnline === false
                    ? "API Offline · Click to retry"
                    : "Checking connection…"}
                </div>
              </div>
            </button>
          ) : (
            <div className="flex flex-col gap-2">
              <button
                type="button"
                onClick={triggerHealthRetry}
                className="flex items-center gap-2 text-xs text-slate-500 hover:text-slate-900 transition-colors w-full"
              >
                <span
                  className={cn(
                    "h-2 w-2 rounded-full flex-shrink-0 transition-all",
                    apiOnline === true
                      ? "bg-emerald-500 ring-2 ring-emerald-200"
                      : apiOnline === false
                      ? "bg-rose-500 animate-pulse ring-2 ring-rose-200"
                      : "bg-slate-400"
                  )}
                />
                <span className="font-medium text-[11px] truncate">
                  {apiOnline === true
                    ? "API Online · Connected"
                    : apiOnline === false
                    ? "API Offline (Click to retry)"
                    : "Checking connection…"}
                </span>
              </button>

              <button
                type="button"
                onClick={toggleCollapsed}
                className="flex items-center justify-between text-[11px] text-slate-400 hover:text-slate-700 pt-1.5 border-t border-slate-200/60 transition-colors"
              >
                <span className="flex items-center gap-1.5">
                  <ChevronLeft className="h-3.5 w-3.5" />
                  <span>Collapse navigation</span>
                </span>
                <kbd className="text-[10px] font-mono bg-slate-200/80 text-slate-600 px-1.5 py-0.5 rounded border border-slate-300/60">
                  Ctrl+B
                </kbd>
              </button>
            </div>
          )}
        </div>
      </aside>

      {/* ─────────────────────────────────────────────────────────────
          3. MAIN CONTENT (Expands smoothly when sidebar collapses)
         ───────────────────────────────────────────────────────────── */}
      <div
        className={cn(
          "flex flex-1 flex-col min-h-screen transition-all duration-300 ease-in-out pl-0",
          isCollapsed ? "lg:pl-[72px]" : "lg:pl-60"
        )}
      >
        {/* Top Header */}
        <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-slate-200 bg-white/95 backdrop-blur-md px-4 sm:px-6 lg:px-8 shadow-xs transition-all">
          <div className="flex items-center gap-3">
            {/* Mobile Menu Toggle Button (< lg) */}
            <button
              type="button"
              onClick={() => setMobileOpen((prev) => !prev)}
              className="lg:hidden p-2 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors -ml-1"
              aria-label="Toggle navigation drawer"
              title="Open Navigation Menu"
            >
              <Menu className="h-5 w-5" />
            </button>

            {/* Desktop Sidebar Toggle Button (>= lg) */}
            <button
              type="button"
              onClick={toggleCollapsed}
              className="hidden lg:flex p-1.5 rounded-lg text-slate-400 hover:text-slate-800 hover:bg-slate-100 transition-colors items-center justify-center -ml-1"
              title={isCollapsed ? "Expand navigation (Ctrl+B)" : "Collapse navigation (Ctrl+B)"}
              aria-label={isCollapsed ? "Expand sidebar navigation" : "Collapse sidebar navigation"}
            >
              {isCollapsed ? (
                <PanelLeftOpen className="h-4 w-4" />
              ) : (
                <PanelLeftClose className="h-4 w-4" />
              )}
            </button>

            {/* Breadcrumb Path */}
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <Link href="/" className="text-slate-400 hover:text-slate-700 transition-colors font-medium">
                HireMatch
              </Link>
              <span className="text-slate-300">/</span>
              <span className="font-semibold text-slate-900">
                {activePage?.name ?? "Platform"}
              </span>
            </div>
          </div>

          {/* Header Right Actions */}
          <div className="flex items-center gap-2.5">
            {/* Quick Shortcut Indicator */}
            <span
              className="hidden sm:inline-flex items-center gap-1 text-[11px] text-slate-400 bg-slate-100 border border-slate-200 px-2 py-1 rounded-md font-mono"
              title="Shortcut: Ctrl+B to toggle sidebar"
            >
              <kbd className="font-semibold">Ctrl+B</kbd>
              <span className="text-slate-300">·</span>
              <span>toggle nav</span>
            </span>

            <Link
              href="/screenings/new"
              className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-3.5 py-1.5 text-xs font-semibold text-white shadow-xs hover:bg-blue-700 transition-all active:scale-[0.98]"
            >
              <PlusCircle className="h-3.5 w-3.5" />
              <span>New Screening</span>
            </Link>
          </div>
        </header>

        {/* Page Content with smooth fade */}
        <main className="flex-1 p-4 sm:p-6 lg:p-8 max-w-screen-xl w-full page-enter">
          {children}
        </main>
      </div>
    </div>
  );
}
