"use client";

import React, { useState } from "react";
import { FileCheck, AlertCircle, Info, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";

interface DecoupledQualityMatrixProps {
  totalCandidates: number;
  className?: string;
}

export function DecoupledQualityMatrix({
  totalCandidates,
  className,
}: DecoupledQualityMatrixProps) {
  const [activeQuadrant, setActiveQuadrant] = useState<number | null>(null);

  const quadrants = [
    {
      id: 1,
      title: "Strong Match · Good Document",
      desc: "Top candidates with clear presentation and high qualifications.",
      color: "border-olive-300 bg-olive-50/70 text-stone-900",
      accent: "text-olive-800",
    },
    {
      id: 2,
      title: "Strong Match · Developing Document",
      desc: "High potential candidates with non-standard formatting. Highly recommended for interview despite formatting.",
      color: "border-sage-300 bg-sage-50 text-stone-900",
      accent: "text-olive-700",
    },
    {
      id: 3,
      title: "Moderate Match · Polished Document",
      desc: "Well-crafted resume but lacks direct verifiable evidence for core requirements.",
      color: "border-stone-300 bg-stone-100/80 text-stone-800",
      accent: "text-stone-700",
    },
    {
      id: 4,
      title: "Low Match · Developing Document",
      desc: "Unmet mandatory criteria with sparse work documentation.",
      color: "border-terracotta-200 bg-terracotta-50/60 text-stone-800",
      accent: "text-terracotta-700",
    },
  ];

  return (
    <div
      className={cn(
        "rounded-2xl border border-stone-300 bg-white p-5 sm:p-6 shadow-subtle space-y-4",
        className
      )}
    >
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-stone-200 pb-3">
        <div>
          <h3 className="text-sm font-semibold text-stone-900 flex items-center gap-2">
            <FileCheck className="h-4 w-4 text-olive-700" />
            <span>Decoupled Signals: Qualification vs. Document Quality</span>
          </h3>
          <p className="text-xs text-stone-500 mt-0.5">
            Document presentation does not alter job suitability rankings.
          </p>
        </div>

        <span className="rounded-full bg-stone-100 border border-stone-300 px-2 py-0.5 text-[11px] font-medium text-stone-600">
          Independent Rubric
        </span>
      </div>

      {/* 2x2 Matrix */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {quadrants.map((q) => {
          const isSelected = activeQuadrant === q.id;

          return (
            <div
              key={q.id}
              onClick={() => setActiveQuadrant(isSelected ? null : q.id)}
              className={cn(
                "p-3.5 rounded-xl border text-left cursor-pointer transition-all duration-150",
                q.color,
                isSelected ? "ring-2 ring-olive-500/50 shadow-sm" : "hover:shadow-subtle"
              )}
            >
              <div className="flex items-center justify-between">
                <span className={cn("text-xs font-semibold", q.accent)}>
                  {q.title}
                </span>
              </div>
              <p className="text-[11px] text-stone-600 mt-1 leading-relaxed">
                {q.desc}
              </p>
            </div>
          );
        })}
      </div>

      {/* Responsible AI Notice */}
      <div className="rounded-xl border border-stone-300 bg-[#FAF9F6] p-3 text-xs text-stone-600 flex items-start gap-2.5">
        <Info className="h-4 w-4 text-stone-400 shrink-0 mt-0.5" />
        <p className="leading-relaxed">
          <strong className="text-stone-900 font-medium">Responsible AI Notice:</strong>{" "}
          Resume quality reflects how clearly and consistently information is communicated.
          It is strictly decoupled from the candidate&apos;s match score.{" "}
          <em>Resume quality is NOT candidate quality.</em>
        </p>
      </div>
    </div>
  );
}
