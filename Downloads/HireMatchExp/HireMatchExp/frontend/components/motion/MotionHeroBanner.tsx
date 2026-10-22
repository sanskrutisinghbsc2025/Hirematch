"use client";

import React, { useEffect, useRef, useState } from "react";
import {
  Sparkles,
  Play,
  Pause,
  ChevronRight,
  ChevronLeft,
  FileText,
  KeyRound,
  Cpu,
  Scale,
  UserCheck,
  CheckCircle2,
  Shield,
  Lock,
  RotateCcw,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface WalkthroughStage {
  id: number;
  layer: string;
  name: string;
  title: string;
  tagline: string;
  badge: string;
  icon: React.ComponentType<{ className?: string }>;
  description: string;
  rule: string;
  guarantee: string;
  telemetryType: "pii" | "skills" | "vectors" | "timeline" | "recruiter";
  highlights: string[];
}

const WALKTHROUGH_STAGES: WalkthroughStage[] = [
  {
    id: 1,
    layer: "Step 1",
    name: "Resume Upload",
    title: "1. Secure Upload & Privacy Protection",
    tagline: "Automated text cleanup & personal info protection",
    badge: "Privacy Protected",
    icon: FileText,
    telemetryType: "pii",
    description:
      "Resumes are converted into clean text. Personal details like names, photos, and contact info are automatically hidden so candidates are judged purely on their actual skills and experience.",
    rule: "Reviews candidates based purely on their qualifications, free from personal bias.",
    guarantee: "Personal details stay hidden throughout initial screening.",
    highlights: ["Personal Info Hidden", "Clean Text Reading", "Zero Demographic Bias"],
  },
  {
    id: 2,
    layer: "Step 2",
    name: "Skill Matching",
    title: "2. Skill & Requirement Check",
    tagline: "Checks job requirements against candidate experience",
    badge: "500+ Skills Recognized",
    icon: KeyRound,
    telemetryType: "skills",
    description:
      "Checks candidate resumes against the skills required for the role. Real work experience carries much more weight than brief mentions in a summary or skills list.",
    rule: "Smart phrasing checks prevent giving credit for skills a candidate says they don't have (like 'no AWS experience').",
    guarantee: "Accurate skill matching that recognizes different ways of naming the same skill.",
    highlights: ["Recognizes Skill Variations", "Work History Weighted Higher", "Smart Negative Phrasing Check"],
  },
  {
    id: 3,
    layer: "Step 3",
    name: "Smart Meaning",
    title: "3. Smart Meaning & Experience",
    tagline: "Understands real-world experience beyond simple keywords",
    badge: "Understands Context",
    icon: Cpu,
    telemetryType: "vectors",
    description:
      "Understands what a candidate actually accomplished, even if they used different words or job titles than what is written in your job description.",
    rule: "Spots strong relevant experience even when candidates describe their work in different phrasing.",
    guarantee: "Fair evaluation based on real capability, not keyword games.",
    highlights: ["Understands Synonyms & Context", "Clear Match Levels", "Spots Relevant Experience"],
  },
  {
    id: 4,
    layer: "Step 4",
    name: "Fair Scoring",
    title: "4. Fair & Transparent Scoring",
    tagline: "Combines skills, timeline, and experience into a clear score",
    badge: "Clear Score Breakdown",
    icon: Scale,
    telemetryType: "timeline",
    description:
      "Combines skill matches, work history, and experience length into one clear overall score (0–100). Also checks work timelines for unusual gaps or conflicting dates.",
    rule: "Calculated using a transparent, open formula so you always know exactly why someone received their score.",
    guarantee: "100% transparent score calculation with no hidden black-box decisions.",
    highlights: ["Career Timeline Check", "Balanced Weighting", "Open & Auditable Score"],
  },
  {
    id: 5,
    layer: "Step 5",
    name: "Final Review",
    title: "5. Recruiter in Full Control",
    tagline: "Every score backed by real quotes from the resume",
    badge: "Recruiter Decides",
    icon: UserCheck,
    telemetryType: "recruiter",
    description:
      "HireMatch never automatically rejects any candidate. Every score points directly to exact sentences in the resume so you can verify the evidence yourself and make the final call.",
    rule: "Zero automated rejections: Recruiters make 100% of shortlisting and interview decisions.",
    guarantee: "You retain complete control with full evidence for every candidate.",
    highlights: ["Exact Resume Quotes", "Adjustable Priority Sliders", "Recruiter Makes Final Call"],
  },
];

interface MotionHeroBannerProps {
  title?: string;
  subtitle?: string;
  onOpenDemo?: () => void;
  className?: string;
}

export function MotionHeroBanner({
  title = "HireMatch",
  subtitle = "Clear, unbiased resume screening. You stay in full control of every hiring decision.",
  onOpenDemo,
  className,
}: MotionHeroBannerProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const spotlightRef = useRef<HTMLDivElement | null>(null);

  const [activeStageIdx, setActiveStageIdx] = useState(2); // Start on Layer 3 (Vector AI)
  const [isPlaying, setIsPlaying] = useState(true); // Autoplay live walkthrough at top
  const [progress, setProgress] = useState(0);
  const [isReducedMotion, setIsReducedMotion] = useState(false);

  // Mouse coordinates relative to container in CSS pixels
  const mousePosRef = useRef<{ x: number; y: number; active: boolean }>({
    x: 0,
    y: 0,
    active: false,
  });

  // Check reduced motion preference
  useEffect(() => {
    if (typeof window !== "undefined") {
      const mediaQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
      setIsReducedMotion(mediaQuery.matches);
      if (mediaQuery.matches) setIsPlaying(false);

      const handleChange = (e: MediaQueryListEvent) => {
        setIsReducedMotion(e.matches);
        if (e.matches) setIsPlaying(false);
      };
      mediaQuery.addEventListener("change", handleChange);
      return () => mediaQuery.removeEventListener("change", handleChange);
    }
  }, []);

  // Autoplay live walkthrough timer (smooth 50ms tick, 6.5s per stage)
  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (isPlaying && !isReducedMotion) {
      const stepInterval = 50;
      const totalDuration = 6500;
      const stepIncrement = (stepInterval / totalDuration) * 100;

      interval = setInterval(() => {
        setProgress((prev) => {
          if (prev >= 100) {
            setActiveStageIdx((cur) => (cur + 1) % WALKTHROUGH_STAGES.length);
            return 0;
          }
          return prev + stepIncrement;
        });
      }, stepInterval);
    } else {
      setProgress(0);
    }
    return () => clearInterval(interval);
  }, [isPlaying, isReducedMotion]);

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    mousePosRef.current = { x, y, active: true };

    if (spotlightRef.current) {
      spotlightRef.current.style.background = `radial-gradient(400px circle at ${x}px ${y}px, rgba(37, 99, 235, 0.10), transparent 70%)`;
      spotlightRef.current.style.opacity = "1";
    }
  };

  const handleMouseLeave = () => {
    mousePosRef.current.active = false;
    if (spotlightRef.current) {
      spotlightRef.current.style.opacity = "0";
    }
  };

  // High-Visibility Interactive Background Particle & Laser Vector Canvas
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animId: number;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);

    let width = (canvas.width = canvas.offsetWidth * dpr);
    let height = (canvas.height = canvas.offsetHeight * dpr);

    const handleResize = () => {
      if (!canvas) return;
      width = canvas.width = canvas.offsetWidth * dpr;
      height = canvas.height = canvas.offsetHeight * dpr;
    };
    window.addEventListener("resize", handleResize);

    const nodeCount = 26;
    interface ConstellationNode {
      x: number;
      y: number;
      vx: number;
      vy: number;
      radius: number;
      color: string;
      glowColor: string;
      pulse: number;
    }

    const nodePresets = [
      { color: "#2563EB", glow: "rgba(37, 99, 235, 0.25)" },
      { color: "#06B6D4", glow: "rgba(6, 182, 212, 0.25)" },
      { color: "#10B981", glow: "rgba(16, 185, 129, 0.25)" },
      { color: "#8B5CF6", glow: "rgba(139, 92, 246, 0.25)" },
      { color: "#0284C7", glow: "rgba(2, 132, 199, 0.25)" },
      { color: "#6366F1", glow: "rgba(99, 102, 241, 0.25)" },
    ];

    const nodes: ConstellationNode[] = [];
    for (let i = 0; i < nodeCount; i++) {
      const preset = nodePresets[i % nodePresets.length];
      nodes.push({
        x: Math.random() * width,
        y: Math.random() * height,
        vx: (Math.random() - 0.5) * 0.35 * dpr,
        vy: (Math.random() - 0.5) * 0.35 * dpr,
        radius: (Math.random() * 0.6 + 1.2) * dpr, // Small, subtle dots (1.2px - 1.8px)
        color: preset.color,
        glowColor: preset.glow,
        pulse: Math.random() * Math.PI * 2,
      });
    }

    let lerpX = width / 2;
    let lerpY = height / 2;
    let scanAngle = 0;

    const render = () => {
      ctx.clearRect(0, 0, width, height);

      const container = containerRef.current;
      const cssW = container ? container.offsetWidth : width / dpr;
      const cssH = container ? container.offsetHeight : height / dpr;
      const scaleX = width / cssW;
      const scaleY = height / cssH;

      const targetX = mousePosRef.current.active
        ? mousePosRef.current.x * scaleX
        : width * 0.5 + Math.cos(scanAngle * 0.5) * (width * 0.35);
      const targetY = mousePosRef.current.active
        ? mousePosRef.current.y * scaleY
        : height * 0.4 + Math.sin(scanAngle * 0.5) * (height * 0.25);

      lerpX += (targetX - lerpX) * 0.15;
      lerpY += (targetY - lerpY) * 0.15;
      scanAngle += 0.02;

      // ─── 1. Subtle Inter-Node Base Mesh Lines ───────────────────────
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const dx = nodes[i].x - nodes[j].x;
          const dy = nodes[i].y - nodes[j].y;
          const dist = Math.sqrt(dx * dx + dy * dy);

          if (dist < 110 * dpr) {
            const alpha = (1 - dist / (110 * dpr)) * 0.18;
            ctx.beginPath();
            ctx.moveTo(nodes[i].x, nodes[i].y);
            ctx.lineTo(nodes[j].x, nodes[j].y);
            ctx.strokeStyle = `rgba(148, 163, 184, ${alpha})`;
            ctx.lineWidth = 0.75 * dpr;
            ctx.stroke();
          }
        }
      }

      // ─── 2. Fine-Line Cursor Laser Connections & Gentle Attraction ─
      const mouseRadius = 180 * dpr;
      const closeNodes = nodes
        .map((n) => {
          const dx = lerpX - n.x;
          const dy = lerpY - n.y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          return { node: n, dist, dx, dy };
        })
        .filter((item) => item.dist < mouseRadius)
        .sort((a, b) => a.dist - b.dist);

      const maxLinks = Math.min(4, closeNodes.length);

      for (let i = 0; i < maxLinks; i++) {
        const { node, dist, dx, dy } = closeNodes[i];

        if (dist > 1) {
          const force = (1 - dist / mouseRadius) * 1.5 * dpr;
          node.x += (dx / dist) * force * 0.3;
          node.y += (dy / dist) * force * 0.3;

          const lineAlpha = (1 - dist / mouseRadius) * 0.65;
          ctx.beginPath();
          ctx.moveTo(lerpX, lerpY);
          ctx.lineTo(node.x, node.y);
          ctx.strokeStyle = `rgba(37, 99, 235, ${lineAlpha})`;
          ctx.lineWidth = (1.1 - i * 0.2) * dpr;
          ctx.stroke();
        }
      }

      // ─── 3. Sleek, Compact Cursor Reticle (Minimal Footprint) ─────
      const halo = ctx.createRadialGradient(lerpX, lerpY, 0, lerpX, lerpY, 18 * dpr);
      halo.addColorStop(0, "rgba(37, 99, 235, 0.15)");
      halo.addColorStop(0.6, "rgba(6, 182, 212, 0.05)");
      halo.addColorStop(1, "rgba(255, 255, 255, 0)");
      ctx.beginPath();
      ctx.arc(lerpX, lerpY, 18 * dpr, 0, Math.PI * 2);
      ctx.fillStyle = halo;
      ctx.fill();

      // Delicate dashed ring
      ctx.beginPath();
      ctx.arc(lerpX, lerpY, 9 * dpr, 0, Math.PI * 2);
      ctx.strokeStyle = "rgba(37, 99, 235, 0.6)";
      ctx.lineWidth = 1 * dpr;
      ctx.setLineDash([3 * dpr, 2.5 * dpr]);
      ctx.stroke();
      ctx.setLineDash([]);

      // Center dot
      ctx.beginPath();
      ctx.arc(lerpX, lerpY, 1.8 * dpr, 0, Math.PI * 2);
      ctx.fillStyle = "#2563EB";
      ctx.fill();

      // Rotating mini radar sweep
      const radarLength = 12 * dpr;
      ctx.beginPath();
      ctx.moveTo(lerpX, lerpY);
      ctx.lineTo(
        lerpX + Math.cos(scanAngle * 3) * radarLength,
        lerpY + Math.sin(scanAngle * 3) * radarLength
      );
      ctx.strokeStyle = "rgba(6, 182, 212, 0.7)";
      ctx.lineWidth = 1 * dpr;
      ctx.stroke();

      // ─── 4. Render Small, Elegant Micro-Dots ─────────────────────
      for (let i = 0; i < nodes.length; i++) {
        const node = nodes[i];

        node.x += node.vx;
        node.y += node.vy;

        if (node.x < 10 * dpr || node.x > width - 10 * dpr) node.vx *= -1;
        if (node.y < 10 * dpr || node.y > height - 10 * dpr) node.vy *= -1;

        node.pulse += 0.04;
        const currentR = node.radius + Math.sin(node.pulse) * 0.3 * dpr;

        // Subtle soft halo
        ctx.beginPath();
        ctx.arc(node.x, node.y, currentR * 1.4, 0, Math.PI * 2);
        ctx.fillStyle = node.glowColor;
        ctx.fill();

        // Crisp compact dot
        ctx.beginPath();
        ctx.arc(node.x, node.y, currentR, 0, Math.PI * 2);
        ctx.fillStyle = node.color;
        ctx.fill();
      }

      animId = requestAnimationFrame(render);
    };

    render();

    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener("resize", handleResize);
    };
  }, [isReducedMotion]);

  const currentStage = WALKTHROUGH_STAGES[activeStageIdx];
  const StageIcon = currentStage.icon;

  return (
    <div
      ref={containerRef}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      className={cn(
        "relative overflow-hidden rounded-2xl border border-slate-200/90 bg-white p-5 sm:p-6 shadow-card space-y-4 cursor-crosshair",
        className
      )}
    >
      {/* ─── DYNAMIC CURSOR SPOTLIGHT IN BACKGROUND ─────────────────── */}
      <div
        ref={spotlightRef}
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 transition-opacity duration-300 opacity-0 z-0"
      />

      {/* ─── LIVE CURSOR-BASED GRAPHICS IN BACKGROUND ───────────────── */}
      <canvas
        ref={canvasRef}
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 h-full w-full opacity-85 z-0"
      />

      {/* ─── TOP BAR: APPLICATION TITLE & LIVE PLAYING CONTROLS ─────── */}
      <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-slate-200/80 pb-3">
        {/* Title Block: strictly HireMatch */}
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-slate-900 leading-none">
              {title}
            </h1>
            <span className="inline-flex items-center gap-1 rounded-full border border-blue-200 bg-blue-50/90 px-2.5 py-0.5 text-[11px] font-semibold text-blue-700 shadow-xs">
              <Sparkles className="h-3 w-3 text-blue-600 animate-pulse-subtle" />
              <span>Interactive Walkthrough</span>
            </span>
          </div>
          <p className="text-xs sm:text-sm text-slate-500 font-normal mt-1 max-w-xl">
            {subtitle}
          </p>
        </div>

        {/* Live Playing Autoplay & Steppers (Directly At The Top) */}
        <div className="flex items-center gap-2 self-start md:self-center flex-shrink-0">
          <button
            type="button"
            onClick={() => setIsPlaying(!isPlaying)}
            className={cn(
              "inline-flex items-center gap-2 rounded-lg border px-3 py-1.5 text-xs font-semibold shadow-xs transition-all active:scale-[0.98]",
              isPlaying
                ? "bg-blue-600 text-white border-blue-700 hover:bg-blue-700"
                : "bg-white/95 backdrop-blur-xs text-slate-700 border-slate-300 hover:bg-white"
            )}
            title={isPlaying ? "Pause live walkthrough" : "Start live walkthrough"}
          >
            {isPlaying ? (
              <>
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-300 opacity-75" />
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-400" />
                </span>
                <Pause className="h-3.5 w-3.5" />
                <span>Live Playing</span>
              </>
            ) : (
              <>
                <Play className="h-3.5 w-3.5" />
                <span>Play Tour</span>
              </>
            )}
          </button>

          {/* Steppers */}
          <div className="flex items-center rounded-lg border border-slate-300 bg-white/95 backdrop-blur-xs p-0.5 shadow-xs">
            <button
              type="button"
              onClick={() => {
                setActiveStageIdx((prev) => (prev - 1 + WALKTHROUGH_STAGES.length) % WALKTHROUGH_STAGES.length);
                setProgress(0);
              }}
              className="p-1 rounded text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors"
              title="Previous stage"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <span className="px-2 text-[11px] font-mono font-semibold text-slate-700">
              {activeStageIdx + 1} / {WALKTHROUGH_STAGES.length}
            </span>
            <button
              type="button"
              onClick={() => {
                setActiveStageIdx((prev) => (prev + 1) % WALKTHROUGH_STAGES.length);
                setProgress(0);
              }}
              className="p-1 rounded text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors"
              title="Next stage"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>

          <button
            type="button"
            onClick={() => {
              setActiveStageIdx(0);
              setProgress(0);
              setIsPlaying(true);
            }}
            className="p-1.5 rounded-lg border border-slate-300 bg-white/95 backdrop-blur-xs text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors shadow-xs"
            title="Reset to Stage 1"
          >
            <RotateCcw className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {/* ─── 5-STAGE PIPELINE TABS (COMPACT, AT THE TOP) ─────────────── */}
      <div className="relative z-10 grid grid-cols-2 sm:grid-cols-5 gap-2">
        {WALKTHROUGH_STAGES.map((stg, idx) => {
          const Icon = stg.icon;
          const isActive = idx === activeStageIdx;

          return (
            <button
              key={stg.id}
              type="button"
              onClick={() => {
                setActiveStageIdx(idx);
                setProgress(0);
              }}
              className={cn(
                "group relative flex flex-col items-start p-2 rounded-xl border text-left transition-all duration-150 select-none",
                isActive
                  ? "bg-white/95 backdrop-blur-xs border-blue-600 shadow-md ring-2 ring-blue-600/15"
                  : "bg-white/75 backdrop-blur-xs border-slate-200 hover:border-slate-300 hover:bg-white"
              )}
            >
              <div className="flex items-center justify-between w-full mb-0.5">
                <span
                  className={cn(
                    "text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.2 rounded font-mono",
                    isActive ? "bg-blue-100 text-blue-800" : "bg-slate-100 text-slate-600"
                  )}
                >
                  {stg.layer}
                </span>

                <div
                  className={cn(
                    "h-4 w-4 rounded flex items-center justify-center transition-colors",
                    isActive ? "text-blue-600" : "text-slate-400"
                  )}
                >
                  <Icon className="h-3 w-3" />
                </div>
              </div>

              <span className="text-xs font-semibold text-slate-900 truncate w-full">
                {stg.name}
              </span>
              <span className="text-[10px] text-slate-500 truncate w-full font-normal">
                {stg.badge}
              </span>

              {/* Progress bar during live play */}
              {isActive && isPlaying && (
                <div className="absolute bottom-0 left-2 right-2 h-0.5 bg-slate-200 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-blue-600 transition-all duration-75"
                    style={{ width: `${progress}%` }}
                  />
                </div>
              )}
            </button>
          );
        })}
      </div>

      {/* ─── LIVE STAGE VISUAL CONSOLE (COMPACT & 100% VISIBLE AT TOP) ─ */}
      <div className="relative z-10 rounded-xl border border-slate-200 bg-white/95 backdrop-blur-sm p-3.5 sm:p-4 shadow-subtle grid grid-cols-1 lg:grid-cols-12 gap-4 items-center">
        {/* Left: Stage Deep Dive (Compact, informative) */}
        <div className="lg:col-span-7 space-y-2">
          <div className="flex items-center gap-2">
            <span className="h-6 w-6 rounded-lg bg-blue-50 border border-blue-200 flex items-center justify-center text-blue-600 shadow-xs">
              <StageIcon className="h-3.5 w-3.5" />
            </span>
            <div>
              <span className="text-[10px] font-mono uppercase tracking-wider text-blue-600 font-bold">
                {currentStage.layer} · How It Works
              </span>
              <h3 className="text-sm font-bold text-slate-900 leading-tight">
                {currentStage.title}
              </h3>
            </div>
          </div>

          <p className="text-xs text-slate-600 leading-snug">
            {currentStage.description}
          </p>

          <div className="rounded-lg border border-slate-200 bg-slate-50/80 px-2.5 py-1.5 flex items-center gap-2">
            <CheckCircle2 className="h-3.5 w-3.5 text-blue-600 flex-shrink-0" />
            <p className="text-[11px] text-slate-700 leading-tight">
              <span className="font-semibold text-slate-900">Guarantee: </span>
              {currentStage.rule}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-1.5 pt-0.5">
            {currentStage.highlights.map((h, i) => (
              <span
                key={i}
                className="inline-flex items-center gap-1 text-[10px] font-medium bg-white border border-slate-200 text-slate-700 px-2 py-0.5 rounded shadow-xs"
              >
                <span className="h-1 w-1 rounded-full bg-blue-500" />
                {h}
              </span>
            ))}
          </div>
        </div>

        {/* Right: Live Interactive Telemetry Simulation (Fits without scrolling!) */}
        <div className="lg:col-span-5 bg-slate-50/90 rounded-xl border border-slate-200 p-3 space-y-2 shadow-inner">
          <div className="flex items-center justify-between border-b border-slate-200 pb-1.5 text-xs">
            <span className="font-semibold text-slate-800 flex items-center gap-1.5 text-[11px]">
              <Shield className="h-3 w-3 text-blue-600" />
              <span>Behind the Scenes</span>
            </span>
            <span className="font-mono text-[9px] px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-800 font-semibold">
              ● ACTIVE
            </span>
          </div>

          {activeStageIdx === 0 && (
            <div className="space-y-1.5 text-xs">
              <div className="p-2 rounded bg-white border border-slate-200 space-y-1">
                <div className="flex items-center justify-between text-[10px]">
                  <span className="font-semibold text-slate-800 flex items-center gap-1">
                    <Lock className="h-2.5 w-2.5 text-blue-600" />
                    Personal Info Shield
                  </span>
                  <span className="text-emerald-600 font-mono text-[9px]">PROTECTED</span>
                </div>
                <div className="grid grid-cols-2 gap-1 font-mono text-[9px]">
                  <span className="p-1 rounded bg-slate-100 text-slate-600">NAME: [HIDDEN]</span>
                  <span className="p-1 rounded bg-slate-100 text-slate-600">PHONE: [HIDDEN]</span>
                  <span className="p-1 rounded bg-slate-100 text-slate-600">GENDER: [EXCLUDED]</span>
                  <span className="p-1 rounded bg-slate-100 text-slate-600">AGE: [EXCLUDED]</span>
                </div>
              </div>
              <p className="text-[10px] text-slate-500 leading-tight">
                Only actual job skills, experience, and qualifications are used for evaluation.
              </p>
            </div>
          )}

          {activeStageIdx === 1 && (
            <div className="space-y-1.5 text-xs">
              <div className="p-2 rounded bg-white border border-slate-200 space-y-1">
                <span className="font-semibold text-slate-800 text-[10px] block">
                  Skill Matching & Negative Phrasing Check:
                </span>
                <div className="space-y-1 font-mono text-[9px]">
                  <div className="flex items-center justify-between p-1 rounded bg-blue-50 border border-blue-200 text-blue-800">
                    <span>Python · Core Required Skill</span>
                    <span className="font-bold">WEIGHT: High</span>
                  </div>
                  <div className="flex items-center justify-between p-1 rounded bg-blue-50 border border-blue-200 text-blue-800">
                    <span>FastAPI · Web API Framework</span>
                    <span className="font-bold">WEIGHT: Match</span>
                  </div>
                  <div className="flex items-center justify-between p-1 rounded bg-rose-50 border border-rose-200 text-rose-800">
                    <span>AWS · "no AWS experience"</span>
                    <span className="font-bold">0% (IGNORED)</span>
                  </div>
                </div>
              </div>
              <p className="text-[10px] text-slate-500 leading-tight">
                Candidates are never credited for tools or skills they specifically state they don't have.
              </p>
            </div>
          )}

          {activeStageIdx === 2 && (
            <div className="space-y-1.5 text-xs">
              <div className="p-2 rounded bg-white border border-slate-200 space-y-1.5">
                <div className="flex items-center justify-between text-[10px]">
                  <span className="font-semibold text-slate-800">Overall Role & Experience Alignment</span>
                  <span className="font-mono text-blue-800 font-bold">91% Strong Match</span>
                </div>
                <div className="h-1.5 w-full bg-slate-100 rounded-full overflow-hidden">
                  <div className="h-full bg-blue-600 rounded-full transition-all duration-300" style={{ width: "91.4%" }} />
                </div>
                <div className="flex items-center justify-between text-[9px] text-slate-500 font-mono">
                  <span>Weak (&lt;60%)</span>
                  <span>Moderate (60-79%)</span>
                  <span className="text-emerald-600 font-semibold">Strong (≥80%)</span>
                </div>
              </div>
              <p className="text-[10px] text-slate-500 leading-tight">
                Understands relevant engineering and system experience even with alternative wording.
              </p>
            </div>
          )}

          {activeStageIdx === 3 && (
            <div className="space-y-1.5 text-xs">
              <div className="p-2 rounded bg-white border border-slate-200 space-y-1">
                <span className="font-semibold text-slate-800 text-[10px] block">
                  Career Timeline & History Check:
                </span>
                <div className="space-y-1 text-[10px]">
                  <div className="flex items-center justify-between p-1 rounded bg-slate-50 border border-slate-200">
                    <span className="text-slate-700">Career Gap Check (&gt;9 mo)</span>
                    <span className="text-emerald-600 font-semibold font-mono text-[9px]">PASSED (NO UNEXPLAINED GAPS)</span>
                  </div>
                  <div className="flex items-center justify-between p-1 rounded bg-slate-50 border border-slate-200">
                    <span className="text-slate-700">Simultaneous Roles (&gt;90 d)</span>
                    <span className="text-emerald-600 font-semibold font-mono text-[9px]">CONSISTENT</span>
                  </div>
                </div>
              </div>
              <p className="text-[10px] text-slate-500 leading-tight">
                Highlights career milestones and flags any timeline discrepancies before final review.
              </p>
            </div>
          )}

          {activeStageIdx === 4 && (
            <div className="space-y-1.5 text-xs">
              <div className="p-2 rounded bg-white border border-slate-200 space-y-1">
                <span className="font-semibold text-slate-800 text-[10px] block">
                  Evidence from Candidate Resume:
                </span>
                <div className="p-1 rounded bg-slate-50 border-l-2 border-blue-600 text-[10px] italic text-slate-700 line-clamp-2">
                  "...architected distributed data pipeline processing 20M events/day using PyTorch and Kafka..."
                </div>
                <div className="flex items-center justify-between text-[9px]">
                  <span className="text-slate-500 font-mono">CITATION: Resume Page 2</span>
                  <span className="text-emerald-600 font-bold">+18.0 pts</span>
                </div>
              </div>
              <p className="text-[10px] text-slate-500 leading-tight">
                Every point is backed by real text from the resume. You decide who gets interviewed.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
