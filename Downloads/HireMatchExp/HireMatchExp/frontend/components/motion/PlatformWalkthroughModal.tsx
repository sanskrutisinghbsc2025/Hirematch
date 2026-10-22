"use client";

import React, { useState, useEffect } from "react";
import {
  X,
  Play,
  Pause,
  ChevronRight,
  ChevronLeft,
  Sparkles,
  FileText,
  Sliders,
  CheckCircle2,
  Scale,
  Shield,
  Layers,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface WalkthroughStep {
  title: string;
  badge: string;
  description: string;
  highlight: string;
  visualType: "flow" | "matrix" | "scoring" | "evidence";
}

const DEMO_STEPS: WalkthroughStep[] = [
  {
    title: "1. Requisition & Criteria Definition",
    badge: "Step 1 of 4",
    description:
      "Paste a job description or set requirements manually. The system extracts technical skills, years of experience, and credentials, giving each a deterministic weight.",
    highlight: "Deterministic weight normalization ensures complete mathematical transparency.",
    visualType: "flow",
  },
  {
    title: "2. Secure Ingestion & PII Quarantine",
    badge: "Step 2 of 4",
    description:
      "Upload batches of up to 100 PDF or DOCX resumes. Text is cleaned with Unicode NFKC normalization, while candidate PII (names, contact info) is quarantined by default.",
    highlight: "Privacy by Design ensures neutral evaluations without bias from demographic traits.",
    visualType: "matrix",
  },
  {
    title: "3. Multi-Layer Hybrid Matching",
    badge: "Step 3 of 4",
    description:
      "Evaluates candidates across lexical rules, domain taxonomy (537+ skills), and dense semantic passage embeddings (all-MiniLM-L6-v2) with strict negation guards.",
    highlight: "Sentence embeddings capture conceptual alignment even when exact keywords differ.",
    visualType: "scoring",
  },
  {
    title: "4. Verbatim Evidence & Human Shortlisting",
    badge: "Step 4 of 4",
    description:
      "Every single score is linked to exact sentence quotes from the resume. Human recruiters review evidence, inspect timeline anomalies, and make all final hiring decisions.",
    highlight: "Zero automated rejections. HireMatch is an auditable decision-support system.",
    visualType: "evidence",
  },
];

export function PlatformWalkthroughModal({
  isOpen,
  onClose,
}: {
  isOpen: boolean;
  onClose: () => void;
}) {
  const [currentIdx, setCurrentIdx] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);

  useEffect(() => {
    let timer: NodeJS.Timeout;
    if (isPlaying && isOpen) {
      timer = setInterval(() => {
        setCurrentIdx((prev) => (prev + 1) % DEMO_STEPS.length);
      }, 4500);
    }
    return () => clearInterval(timer);
  }, [isPlaying, isOpen]);

  if (!isOpen) return null;

  const current = DEMO_STEPS[currentIdx];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-charcoal-900/50 backdrop-blur-[2px] transition-opacity animate-fade-in"
        onClick={onClose}
      />

      {/* Modal Dialog */}
      <div className="relative w-full max-w-2xl rounded-2xl border border-stone-300 bg-white p-6 shadow-modal z-10 space-y-5 animate-slide-up">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-stone-200 pb-4">
          <div className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-olive-50 border border-olive-200 text-olive-700">
              <Sparkles className="h-4 w-4" />
            </span>
            <div>
              <h3 className="text-sm font-semibold text-stone-900">
                Interactive Platform Walkthrough
              </h3>
              <p className="text-xs text-stone-500">
                How HireMatch combines transparent NLP with human recruiter agency.
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-stone-400 hover:text-stone-600 hover:bg-stone-100 transition-colors"
            aria-label="Close walkthrough"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Visual Animation Player Frame */}
        <div className="relative overflow-hidden rounded-xl border border-stone-300 bg-[#FAF9F6] p-6 text-center space-y-4">
          <div className="inline-flex items-center gap-1.5 rounded-full bg-white border border-stone-300 px-3 py-1 text-xs font-medium text-stone-700 shadow-sm">
            <span>{current.badge}</span>
          </div>

          <div className="max-w-md mx-auto space-y-2">
            <h4 className="text-base font-semibold text-stone-900">
              {current.title}
            </h4>
            <p className="text-xs text-stone-600 leading-relaxed">
              {current.description}
            </p>
          </div>

          {/* Interactive Simulation Display */}
          <div className="rounded-lg bg-white border border-stone-300 p-3 max-w-lg mx-auto text-left shadow-subtle flex items-start gap-2.5">
            <Shield className="h-4 w-4 text-olive-700 shrink-0 mt-0.5" />
            <div className="text-xs text-stone-700">
              <span className="font-semibold text-stone-900">Core Assurance:</span>{" "}
              {current.highlight}
            </div>
          </div>

          {/* Stepper Dots */}
          <div className="flex justify-center gap-1.5 pt-2">
            {DEMO_STEPS.map((_, i) => (
              <button
                key={i}
                type="button"
                onClick={() => setCurrentIdx(i)}
                className={cn(
                  "h-1.5 rounded-full transition-all duration-200",
                  i === currentIdx ? "w-6 bg-olive-500" : "w-1.5 bg-stone-300 hover:bg-stone-400"
                )}
                aria-label={`Go to step ${i + 1}`}
              />
            ))}
          </div>
        </div>

        {/* Player Controls */}
        <div className="flex items-center justify-between pt-1">
          <button
            type="button"
            onClick={() => setIsPlaying(!isPlaying)}
            className="inline-flex items-center gap-1.5 text-xs font-medium text-stone-600 hover:text-stone-900 transition-colors"
          >
            {isPlaying ? (
              <>
                <Pause className="h-3.5 w-3.5" />
                <span>Pause Auto-Tour</span>
              </>
            ) : (
              <>
                <Play className="h-3.5 w-3.5" />
                <span>Play Auto-Tour</span>
              </>
            )}
          </button>

          <div className="flex items-center gap-2">
            <button
              type="button"
              disabled={currentIdx === 0}
              onClick={() => setCurrentIdx((p) => Math.max(0, p - 1))}
              className="inline-flex items-center gap-1 rounded-lg border border-stone-300 px-3 py-1.5 text-xs font-medium text-stone-700 hover:bg-stone-50 disabled:opacity-40 transition-colors"
            >
              <ChevronLeft className="h-3.5 w-3.5" />
              <span>Back</span>
            </button>

            <button
              type="button"
              disabled={currentIdx === DEMO_STEPS.length - 1}
              onClick={() => setCurrentIdx((p) => Math.min(DEMO_STEPS.length - 1, p + 1))}
              className="inline-flex items-center gap-1 rounded-lg bg-olive-500 hover:bg-olive-600 text-white border border-olive-600/50 px-3.5 py-1.5 text-xs font-medium shadow-subtle disabled:opacity-40 transition-colors"
            >
              <span>Next</span>
              <ChevronRight className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
