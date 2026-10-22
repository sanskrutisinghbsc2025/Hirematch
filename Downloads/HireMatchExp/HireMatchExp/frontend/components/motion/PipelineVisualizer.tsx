"use client";

import React, { useState } from "react";
import {
  FileText,
  KeyRound,
  Cpu,
  Scale,
  UserCheck,
  Info,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface PipelineStep {
  id: number;
  name: string;
  shortDesc: string;
  details: string;
  icon: React.ComponentType<{ className?: string }>;
  tag: string;
}

const PIPELINE_STEPS: PipelineStep[] = [
  {
    id: 1,
    name: "Document Ingestion",
    shortDesc: "PyMuPDF / docx extraction",
    details:
      "Cleans raw text with Unicode NFKC normalization, strips non-printable artifacts, and applies PII quarantine.",
    icon: FileText,
    tag: "Layer 1",
  },
  {
    id: 2,
    name: "Lexical & Alias Matching",
    shortDesc: "Section-weighted taxonomy",
    details:
      "Matches against 537+ skills in skills_db.json with explicit negation guards ('no experience with AWS').",
    icon: KeyRound,
    tag: "Layer 2",
  },
  {
    id: 3,
    name: "Dense Semantic Vector AI",
    shortDesc: "Sentence-Transformers",
    details:
      "Computes passage embeddings (all-MiniLM-L6-v2) and cosine similarity across Strong, Possible, and Weak tiers.",
    icon: Cpu,
    tag: "Layer 3",
  },
  {
    id: 4,
    name: "Evidence Synthesis",
    shortDesc: "Cross-layer validation",
    details:
      "Detects conflicting evidence, checks timeline anomalies (>9mo gaps, >90d overlaps), and scores requirements.",
    icon: Scale,
    tag: "Layer 4",
  },
  {
    id: 5,
    name: "Human Recruiter Review",
    shortDesc: "Zero automated rejection",
    details:
      "All statuses default to IN_REVIEW. Recruiters inspect verbatim quote citations and make final decisions.",
    icon: UserCheck,
    tag: "Layer 5",
  },
];

export function PipelineVisualizer({ className }: { className?: string }) {
  const [activeStep, setActiveStep] = useState<number>(3);

  const current = PIPELINE_STEPS.find((s) => s.id === activeStep) || PIPELINE_STEPS[2];

  return (
    <div
      className={cn(
        "rounded-xl border border-stone-300 bg-white p-5 sm:p-6 shadow-subtle space-y-4",
        className
      )}
    >
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-stone-200 pb-3">
        <div>
          <h3 className="text-sm font-semibold text-stone-900 flex items-center gap-2">
            <span>5-Layer Screening Architecture</span>
            <span className="rounded-md bg-stone-100 border border-stone-300 px-2 py-0.5 text-[11px] font-medium text-stone-700">
              Deterministic & Semantic
            </span>
          </h3>
          <p className="text-xs text-stone-500 mt-0.5">
            Transparent processing pipeline preserving explainable evidence from ingestion to final decision.
          </p>
        </div>

        <div className="text-[11px] font-medium text-stone-400 self-start sm:self-auto">
          Click any stage to inspect
        </div>
      </div>

      {/* Interactive Pipeline Steps Flow */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 sm:gap-3">
        {PIPELINE_STEPS.map((step, idx) => {
          const Icon = step.icon;
          const isSelected = step.id === activeStep;

          return (
            <button
              key={step.id}
              type="button"
              onClick={() => setActiveStep(step.id)}
              className={cn(
                "relative flex flex-col items-start p-3 rounded-lg border text-left transition-all duration-150 focus:outline-none",
                isSelected
                  ? "bg-[#FAF9F6] border-stone-900 shadow-sm ring-1 ring-stone-900/10"
                  : "bg-white border-stone-300 hover:border-stone-400 hover:bg-stone-50"
              )}
            >
              <div className="flex items-center justify-between w-full mb-2">
                <span
                  className={cn(
                    "text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded",
                    isSelected
                      ? "bg-stone-900 text-white font-mono"
                      : "bg-stone-100 text-stone-600 font-mono"
                  )}
                >
                  {step.tag}
                </span>

                <div
                  className={cn(
                    "h-6 w-6 rounded flex items-center justify-center transition-colors",
                    isSelected ? "text-stone-900 bg-stone-200" : "text-stone-400 bg-stone-100"
                  )}
                >
                  <Icon className="h-3.5 w-3.5" />
                </div>
              </div>

              <div className="text-xs font-semibold text-stone-900 line-clamp-1">
                {step.name}
              </div>
              <div className="text-[11px] text-stone-500 line-clamp-1 mt-0.5">
                {step.shortDesc}
              </div>

              {/* Progress Connector Indicator */}
              {idx < PIPELINE_STEPS.length - 1 && (
                <div
                  className="hidden sm:block absolute -right-2 top-1/2 -translate-y-1/2 z-10 w-2 h-0.5 bg-stone-300"
                  aria-hidden="true"
                />
              )}
            </button>
          );
        })}
      </div>

      {/* Active Stage Detail Callout */}
      <div className="rounded-lg bg-stone-50 border border-stone-300 p-3.5 flex items-start gap-3 transition-all">
        <div className="h-6 w-6 rounded bg-white border border-stone-300 flex items-center justify-center text-stone-700 shrink-0 mt-0.5">
          <Info className="h-3.5 w-3.5" />
        </div>
        <div className="text-xs space-y-1">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-stone-900">{current.name}</span>
            <span className="text-stone-400">·</span>
            <span className="text-stone-500 font-mono">{current.tag}</span>
          </div>
          <p className="text-stone-600 leading-relaxed">{current.details}</p>
        </div>
      </div>
    </div>
  );
}
