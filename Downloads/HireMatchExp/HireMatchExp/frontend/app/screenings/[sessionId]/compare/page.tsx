"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import {
  ArrowLeft,
  Award,
  AlertTriangle,
  RotateCcw,
  GraduationCap,
  Briefcase,
} from "lucide-react";
import { apiClient } from "@/lib/api/client";
import { CandidateComparison, CandidateHeader, AlignedCriterionRow } from "@/lib/types/api";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { getScoreColor, cn } from "@/lib/utils";

export default function CandidateComparisonPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const sessionId = params.sessionId as string;
  const candidateIdsParam = searchParams.get("candidates") || "";

  const [comparison, setComparison] = useState<CandidateComparison | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchComparison = async () => {
      const ids = candidateIdsParam.split(",").filter(Boolean);
      if (ids.length < 2) {
        setError("Please select at least 2 candidates to compare.");
        setLoading(false);
        return;
      }
      try {
        setLoading(true);
        const data = await apiClient.compareCandidates(ids, sessionId);
        setComparison(data);
      } catch (err: any) {
        setError(err.message || "Failed to compare candidates");
      } finally {
        setLoading(false);
      }
    };

    fetchComparison();
  }, [candidateIdsParam, sessionId]);

  const candidatesList: CandidateHeader[] =
    comparison?.candidate_headers && comparison.candidate_headers.length > 0
      ? comparison.candidate_headers
      : comparison?.candidates || [];

  const criteriaRows: AlignedCriterionRow[] =
    comparison?.aligned_criteria_rows && comparison.aligned_criteria_rows.length > 0
      ? comparison.aligned_criteria_rows
      : comparison?.criteria_comparison || [];

  const differentiatorsList: any[] =
    comparison?.key_differentiators && comparison.key_differentiators.length > 0
      ? comparison.key_differentiators
      : comparison?.differentiators || [];

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* ── Breadcrumb & Header ── */}
      <div>
        <div className="flex items-center gap-1.5 text-xs text-stone-400 mb-2">
          <Link
            href={`/screenings/${sessionId}`}
            className="hover:text-stone-600 transition-colors flex items-center gap-1"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Back to session
          </Link>
        </div>

        <div>
          <h1 className="text-xl font-semibold text-charcoal-900">
            Candidate comparison
          </h1>
          <p className="text-sm text-stone-500 mt-0.5">
            Side-by-side evaluation against criteria and requirements.
          </p>
        </div>
      </div>

      {loading ? (
        <div className="py-20 text-center text-stone-400">
          <RotateCcw className="h-5 w-5 animate-spin mx-auto mb-2 text-olive-600" />
          <p className="text-sm">Comparing candidates...</p>
        </div>
      ) : error ? (
        <Card>
          <CardContent className="p-8 text-center text-terracotta-700">
            <AlertTriangle className="h-6 w-6 mx-auto mb-2 text-terracotta-600" />
            <p className="text-sm font-medium">{error}</p>
            <div className="mt-4">
              <Link href={`/screenings/${sessionId}`}>
                <Button variant="outline" size="sm">
                  Return to candidate list
                </Button>
              </Link>
            </div>
          </CardContent>
        </Card>
      ) : !comparison || candidatesList.length === 0 ? (
        <Card>
          <CardContent className="p-8 text-center text-stone-500">
            <p className="text-sm">No comparison data available for the selected candidates.</p>
            <div className="mt-4">
              <Link href={`/screenings/${sessionId}`}>
                <Button variant="outline" size="sm">
                  Return to candidate list
                </Button>
              </Link>
            </div>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-5">
          {/* Compatibility warnings */}
          {comparison.compatibility?.compatibility_warnings &&
            comparison.compatibility.compatibility_warnings.length > 0 && (
              <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-800 flex items-start gap-2">
                <AlertTriangle className="h-4 w-4 text-amber-600 shrink-0 mt-0.5" />
                <div className="space-y-1">
                  <span className="font-semibold">Compatibility notice:</span>
                  {comparison.compatibility.compatibility_warnings.map((w, idx) => (
                    <p key={idx}>{w}</p>
                  ))}
                </div>
              </div>
            )}

          {/* ── Candidate Cards Grid ── */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {candidatesList.map((cand, idx) => {
              const candId = cand.id || cand.candidate_id || `cand-${idx}`;
              const candName =
                cand.name ||
                cand.candidate_name ||
                cand.candidate_reference ||
                cand.original_filename ||
                `Candidate #${idx + 1}`;
              const candTier =
                cand.fit_tier ||
                (cand.overall_score !== null && cand.overall_score !== undefined
                  ? cand.overall_score >= 80
                    ? "Strong Match"
                    : cand.overall_score >= 60
                    ? "Potential Match"
                    : "Under Review"
                  : "Under Review");
              const score = Math.round(cand.overall_score ?? 0);
              return (
                <Card key={candId} className="p-4 space-y-3">
                  <div className="flex items-start justify-between">
                    <div>
                      <Link
                        href={`/candidates/${candId}?session=${sessionId}`}
                        className="text-sm font-semibold text-stone-900 hover:text-olive-700 transition-colors"
                      >
                        {candName}
                      </Link>
                      {cand.email && (
                        <p className="text-xs text-stone-400 mt-0.5 truncate max-w-[180px]">
                          {cand.email}
                        </p>
                      )}
                    </div>
                    <Badge tier={candTier}>{candTier}</Badge>
                  </div>

                  <div>
                    <div className="flex justify-between items-baseline mb-1">
                      <span className="text-xs text-stone-400">Match score</span>
                      <span className={cn("font-mono text-sm font-semibold", getScoreColor(score))}>
                        {score}%
                      </span>
                    </div>
                    <ProgressBar value={score} size="sm" colorScheme="score" />
                  </div>

                  {cand.resume_quality_score !== null && cand.resume_quality_score !== undefined && (
                    <div className="pt-2 border-t border-stone-100 flex justify-between items-center text-xs">
                      <span className="text-stone-400">Resume quality:</span>
                      <div className="flex items-center gap-1.5 font-mono text-xs font-semibold text-stone-700">
                        <span>{Math.round(cand.resume_quality_score)}%</span>
                        {cand.resume_quality_label && (
                          <span className="text-stone-500 font-sans font-normal">
                            ({cand.resume_quality_label.replace(" Quality", "")})
                          </span>
                        )}
                      </div>
                    </div>
                  )}

                  <div className="pt-2 border-t border-stone-100 flex justify-between items-center text-xs">
                    <span className="text-stone-400">Status:</span>
                    <Badge status={cand.review_status}>{cand.review_status}</Badge>
                  </div>
                </Card>
              );
            })}
          </div>

          {/* ── Key Differentiators ── */}
          {differentiatorsList.length > 0 && (
            <Card>
              <CardHeader className="pb-3 border-b border-stone-100">
                <CardTitle className="text-sm">Key differentiators</CardTitle>
                <CardDescription>
                  Noteworthy differences and highlights identified across compared candidates
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-2.5 pt-4">
                {differentiatorsList.map((diff: any, idx: number) => {
                  const isString = typeof diff === "string";
                  return (
                    <div
                      key={idx}
                      className="flex items-start gap-2.5 rounded-lg border border-stone-200 bg-stone-50 p-3 text-xs"
                    >
                      <Award className="h-4 w-4 text-amber-500 shrink-0 mt-0.5" />
                      <div>
                        {isString ? (
                          <span className="text-stone-700 font-medium">{diff}</span>
                        ) : (
                          <>
                            {diff.candidate_name && (
                              <span className="font-semibold text-charcoal-900">
                                {diff.candidate_name}:{" "}
                              </span>
                            )}
                            <span className="text-stone-600">
                              {diff.description || diff.highlight || JSON.stringify(diff)}
                            </span>
                          </>
                        )}
                      </div>
                    </div>
                  );
                })}
              </CardContent>
            </Card>
          )}

          {/* ── Detailed Matrix Table ── */}
          <div className="bg-white border border-stone-200 rounded-xl overflow-hidden shadow-subtle">
            <div className="px-6 py-4 border-b border-stone-100">
              <h3 className="text-sm font-semibold text-charcoal-900">Criteria breakdown matrix</h3>
              <p className="text-xs text-stone-400 mt-0.5">
                Comparison across all evaluated criteria and requirements
              </p>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-stone-200 bg-stone-50 text-stone-500 font-medium uppercase tracking-wide">
                    <th className="py-3 px-4">Criterion</th>
                    <th className="py-3 px-4 text-center">Type & Weight</th>
                    {candidatesList.map((cand, idx) => {
                      const candId = cand.id || cand.candidate_id || `cand-${idx}`;
                      const candName =
                        cand.name ||
                        cand.candidate_name ||
                        cand.candidate_reference ||
                        cand.original_filename ||
                        `Candidate #${idx + 1}`;
                      return (
                        <th key={candId} className="py-3 px-4 text-center">
                          {candName}
                        </th>
                      );
                    })}
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-100">
                  {criteriaRows.length === 0 ? (
                    <tr>
                      <td colSpan={2 + candidatesList.length} className="py-6 text-center text-stone-400">
                        No criteria evaluation data available.
                      </td>
                    </tr>
                  ) : (
                    criteriaRows.map((row: any, idx: number) => {
                      const isReq =
                        row.criterion_type === "REQUIRED" ||
                        row.criterion_type === "MUST_HAVE" ||
                        Boolean(row.is_required);
                      const weightPct = Math.round((row.configured_weight ?? 1.0) * 100);

                      return (
                        <tr key={row.criterion_id || idx} className="hover:bg-stone-50 transition-colors">
                          <td className="py-3 px-4 max-w-xs">
                            <div className="font-medium text-charcoal-900">{row.criterion_name}</div>
                            {row.has_meaningful_difference && row.variance_note && (
                              <p className="text-2xs text-amber-700 mt-0.5 font-sans">
                                {row.variance_note}
                              </p>
                            )}
                          </td>
                          <td className="py-3 px-4 text-center whitespace-nowrap">
                            <span
                              className={cn(
                                "text-2xs font-medium px-1.5 py-0.5 rounded border mr-1.5",
                                isReq
                                  ? "text-rose-700 bg-rose-50 border-rose-200"
                                  : "text-stone-600 bg-stone-50 border-stone-200"
                              )}
                            >
                              {isReq ? "Required" : "Preferred"}
                            </span>
                            <span className="text-2xs text-stone-400 font-mono">
                              {weightPct}% wt
                            </span>
                          </td>
                          {candidatesList.map((cand, cIdx) => {
                            const candId = cand.id || cand.candidate_id || `cand-${cIdx}`;
                            const evaluation = row.candidate_evaluations?.[candId];

                            let candScore = 0;
                            let evidenceSnippet = "";

                            if (evaluation) {
                              candScore = Math.round((evaluation.support_value ?? 0) * 100);
                              evidenceSnippet = evaluation.evidence_snippet || "";
                            } else if (row.scores?.[candId] !== undefined) {
                              candScore = Math.round(row.scores[candId]);
                            } else if (typeof row[candId] === "number") {
                              candScore = Math.round(row[candId]);
                            }

                            return (
                              <td key={candId} className="py-3 px-4 text-center">
                                <span
                                  className={cn(
                                    "inline-block px-2 py-0.5 rounded text-xs font-semibold font-mono",
                                    candScore >= 70
                                      ? "bg-olive-50 text-olive-700 border border-olive-200"
                                      : candScore >= 50
                                      ? "bg-amber-50 text-amber-700 border border-amber-200"
                                      : "bg-stone-100 text-stone-500 border border-stone-200"
                                  )}
                                >
                                  {candScore}%
                                </span>
                                {evidenceSnippet && (
                                  <p
                                    className="text-2xs text-stone-400 truncate max-w-[150px] mx-auto mt-1"
                                    title={evidenceSnippet}
                                  >
                                    {evidenceSnippet}
                                  </p>
                                )}
                              </td>
                            );
                          })}
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* ── Background & Experience Side-by-Side ── */}
          {(comparison.education_comparison || comparison.experience_comparison) && (
            <Card>
              <CardHeader className="pb-3 border-b border-stone-100">
                <CardTitle className="text-sm">Background summary</CardTitle>
                <CardDescription>
                  Education qualifications and career experience roles compared
                </CardDescription>
              </CardHeader>
              <CardContent className="pt-4 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {candidatesList.map((cand, idx) => {
                  const candId = cand.id || cand.candidate_id || `cand-${idx}`;
                  const candName =
                    cand.name ||
                    cand.candidate_name ||
                    cand.candidate_reference ||
                    cand.original_filename ||
                    `Candidate #${idx + 1}`;
                  const edu = comparison.education_comparison?.[candId];
                  const exp = comparison.experience_comparison?.[candId];
                  return (
                    <div
                      key={candId}
                      className="border border-stone-200 rounded-lg p-3 bg-stone-50/50 space-y-2 text-xs"
                    >
                      <div className="font-semibold text-charcoal-900 border-b border-stone-200 pb-1">
                        {candName}
                      </div>
                      {edu && (
                        <div>
                          <div className="flex items-center gap-1 text-stone-400 font-medium text-2xs uppercase tracking-wider mb-0.5">
                            <GraduationCap className="h-3 w-3" />
                            <span>Education</span>
                          </div>
                          <p className="text-stone-700">{edu}</p>
                        </div>
                      )}
                      {exp && (
                        <div>
                          <div className="flex items-center gap-1 text-stone-400 font-medium text-2xs uppercase tracking-wider mb-0.5">
                            <Briefcase className="h-3 w-3" />
                            <span>Experience</span>
                          </div>
                          <p className="text-stone-700">{exp}</p>
                        </div>
                      )}
                    </div>
                  );
                })}
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
