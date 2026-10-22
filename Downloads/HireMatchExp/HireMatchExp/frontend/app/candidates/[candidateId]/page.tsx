"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import {
  ArrowLeft,
  Mail,
  Phone,
  FileText,
  Award,
  AlertTriangle,
  CheckCircle2,
  Save,
  Download,
  RotateCcw,
  Briefcase,
  GraduationCap,
  Building,
  MapPin,
  ExternalLink,
  Globe,
  Copy,
  Check,
  XCircle,
  AlertCircle,
  FolderGit2,
  Layers,
  FileCode,
  Star,
  AlertOctagon,
  Info,
  ShieldAlert,
} from "lucide-react";
import { apiClient } from "@/lib/api/client";
import { CandidateDetail, CandidateEvaluation, ResumeQualityReport } from "@/lib/types/api";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/Tabs";
import { getScoreColor, cn } from "@/lib/utils";

function ScreeningNarrativeView({ text }: { text: string }) {
  if (!text) return null;

  const rawSections = text.split("\n\n");

  return (
    <div className="space-y-4">
      {rawSections.map((sec, idx) => {
        const trimmed = sec.trim();
        if (!trimmed) return null;

        // Check for Disclaimer
        if (trimmed.startsWith("*Note:") || trimmed.startsWith("*Responsible AI")) {
          return (
            <p key={idx} className="text-xs italic text-stone-400 border-t border-stone-200 pt-3">
              {trimmed.replace(/^\*|\*$/g, "")}
            </p>
          );
        }

        // Check for section headers like **Header**
        const headerMatch = trimmed.match(/^\*\*([^*]+)\*\*\n?([\s\S]*)$/);
        if (headerMatch) {
          const title = headerMatch[1];
          const body = headerMatch[2];

          const isStrengths = title.toLowerCase().includes("strength") || title.toLowerCase().includes("matched");
          const isGaps = title.toLowerCase().includes("deficienc") || title.toLowerCase().includes("gap") || title.toLowerCase().includes("lack");
          const isQuestions = title.toLowerCase().includes("question") || title.toLowerCase().includes("probe");

          const lines = body.split("\n").filter(Boolean);

          return (
            <div
              key={idx}
              className={cn(
                "rounded-lg p-4 border text-xs leading-relaxed",
                isStrengths
                  ? "bg-olive-50 border-olive-200 text-olive-900"
                  : isGaps
                  ? "bg-terra-50 border-terra-200 text-terra-900"
                  : isQuestions
                  ? "bg-stone-50 border-stone-200 text-stone-800"
                  : "bg-stone-50 border-stone-200 text-stone-800"
              )}
            >
              <h4
                className={cn(
                  "text-xs font-semibold uppercase tracking-wide mb-2 flex items-center gap-1.5",
                  isStrengths
                    ? "text-olive-700"
                    : isGaps
                    ? "text-terra-700"
                    : "text-stone-700"
                )}
              >
                {isStrengths && <CheckCircle2 className="h-3.5 w-3.5" />}
                {isGaps && <AlertTriangle className="h-3.5 w-3.5" />}
                {title}
              </h4>

              {lines.length > 1 || lines[0]?.startsWith("•") || lines[0]?.match(/^\d+\./) ? (
                <div className="space-y-1.5 mt-1">
                  {lines.map((line, lIdx) => {
                    const cleanLine = line.replace(/^[•\-\*]\s*|^\d+\.\s*/, "");
                    const parts = cleanLine.split(/(\*\*[^*]+\*\*)/g);
                    return (
                      <div key={lIdx} className="flex items-start gap-2">
                        <span className="text-stone-400 select-none mt-0.5">•</span>
                        <div className="flex-1">
                          {parts.map((p, pIdx) => {
                            if (p.startsWith("**") && p.endsWith("**")) {
                              return (
                                <strong key={pIdx} className="font-semibold text-charcoal-900">
                                  {p.slice(2, -2)}
                                </strong>
                              );
                            }
                            return <span key={pIdx}>{p}</span>;
                          })}
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <p className="mt-1 leading-relaxed">{body}</p>
              )}
            </div>
          );
        }

        return (
          <p key={idx} className="text-xs text-stone-600 leading-relaxed">
            {trimmed}
          </p>
        );
      })}
    </div>
  );
}

export default function CandidateDossierPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const candidateId = params.candidateId as string;
  const sessionId = searchParams.get("session") || "";

  const [candidate, setCandidate] = useState<CandidateDetail | null>(null);
  const [evaluation, setEvaluation] = useState<CandidateEvaluation | null>(null);
  const [qualityAssessment, setQualityAssessment] = useState<ResumeQualityReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [copiedText, setCopiedText] = useState(false);

  // Recruiter Decision Panel State
  const [reviewStatus, setReviewStatus] = useState<string>("IN_REVIEW");
  const [reviewerNotes, setReviewerNotes] = useState<string>("");
  const [isSavingDecision, setIsSavingDecision] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  useEffect(() => {
    const fetchCandidateData = async () => {
      try {
        setLoading(true);
        const [candData, evalData, qualData] = await Promise.all([
          apiClient.getCandidate(candidateId, sessionId || undefined),
          apiClient.getCandidateEvaluation(candidateId).catch(() => null),
          apiClient.getCandidateQuality(candidateId, sessionId).catch(() => null),
        ]);
        setCandidate(candData);
        setEvaluation(evalData);
        setQualityAssessment(candData.resume_quality || qualData);
        if (candData.review_status) {
          setReviewStatus(candData.review_status.toUpperCase());
        }
        const existingNote = candData.reviewer_notes ?? candData.notes ?? "";
        setReviewerNotes(existingNote);
      } catch (err: any) {
        console.error("Failed to load candidate dossier:", err);
      } finally {
        setLoading(false);
      }
    };

    if (candidateId) fetchCandidateData();
  }, [candidateId, sessionId]);

  const handleSaveDecision = async () => {
    try {
      setIsSavingDecision(true);
      await apiClient.updateShortlistStatus(
        candidateId,
        {
          review_status: reviewStatus,
          reviewer_notes: reviewerNotes,
        },
        sessionId || undefined
      );
      setCandidate((prev) =>
        prev
          ? {
              ...prev,
              review_status: reviewStatus,
              reviewer_notes: reviewerNotes,
              notes: reviewerNotes,
            }
          : prev
      );
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err: any) {
      alert("Failed to save decision: " + err.message);
    } finally {
      setIsSavingDecision(false);
    }
  };

  const handleQuickToggleShortlist = async () => {
    const isCurrentlyShortlisted = reviewStatus.toUpperCase() === "SHORTLISTED";
    const nextStatus = isCurrentlyShortlisted ? "IN_REVIEW" : "SHORTLISTED";
    const prevStatus = reviewStatus;
    setReviewStatus(nextStatus);
    try {
      await apiClient.updateShortlistStatus(
        candidateId,
        {
          review_status: nextStatus,
          reviewer_notes: reviewerNotes,
        },
        sessionId || undefined
      );
      setCandidate((prev) =>
        prev
          ? {
              ...prev,
              review_status: nextStatus,
              reviewer_notes: reviewerNotes,
              notes: reviewerNotes,
            }
          : prev
      );
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err: any) {
      setReviewStatus(prevStatus);
      alert("Failed to update shortlist status: " + err.message);
    }
  };

  const handleDownloadReport = () => {
    window.open(`/api/candidates/${candidateId}/report?format=json`, "_blank");
  };

  if (loading) {
    return (
      <div className="py-24 text-center text-stone-400">
        <RotateCcw className="h-5 w-5 animate-spin mx-auto mb-2 text-terra-500" />
        <p className="text-sm">Loading candidate profile...</p>
      </div>
    );
  }

  if (!candidate) {
    return (
      <div className="p-8 text-center text-stone-500 text-sm">
        Candidate not found.
      </div>
    );
  }

  const score = Math.round(candidate.overall_score ?? evaluation?.overall_score ?? 0);
  const isShortlisted = reviewStatus === "SHORTLISTED";

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* ── Breadcrumb & Header ── */}
      <div>
        <div className="flex items-center gap-1.5 text-xs text-stone-400 mb-2">
          <Link
            href={sessionId ? `/screenings/${sessionId}` : "/screenings"}
            className="hover:text-stone-600 transition-colors flex items-center gap-1"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Back to session
          </Link>
        </div>

        <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2.5">
              <h1 className="text-xl font-semibold text-charcoal-900">
                {candidate.name || candidate.original_filename || "Candidate"}
              </h1>
              <Badge tier={candidate.fit_tier ?? evaluation?.fit_tier}>
                {candidate.fit_tier ?? evaluation?.fit_tier ?? "Evaluated"}
              </Badge>
              {candidate.rank && (
                <span className="font-mono text-xs font-medium text-stone-600 bg-stone-100 px-2 py-0.5 rounded">
                  #{candidate.rank}
                </span>
              )}
            </div>
            <div className="flex items-center gap-4 text-xs text-stone-500 mt-1">
              {candidate.email && (
                <span className="flex items-center gap-1">
                  <Mail className="h-3 w-3 text-stone-400" />
                  {candidate.email}
                </span>
              )}
              {candidate.phone && (
                <span className="flex items-center gap-1">
                  <Phone className="h-3 w-3 text-stone-400" />
                  {candidate.phone}
                </span>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleQuickToggleShortlist}
              className={cn(
                "px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-all border",
                isShortlisted
                  ? "bg-amber-50 text-amber-800 border-amber-300 hover:bg-amber-100"
                  : "bg-white text-stone-600 border-stone-200 hover:bg-stone-50"
              )}
            >
              <Star className={cn("h-3.5 w-3.5", isShortlisted && "fill-amber-400 text-amber-500")} />
              <span>{isShortlisted ? "Shortlisted" : "Shortlist"}</span>
            </button>

            <Button
              variant="outline"
              size="sm"
              onClick={handleDownloadReport}
              leftIcon={<Download className="h-3.5 w-3.5 text-stone-400" />}
            >
              Export JSON
            </Button>
          </div>
        </div>
      </div>

      {/* ── Responsible Interpretation & Decoupling Notice ── */}
      <div className="bg-[#FAF8F5] border border-[#E8E3DA] rounded-2xl p-5 text-xs text-stone-600 flex items-start gap-3.5 shadow-subtle">
        <div className="mt-0.5 rounded-xl p-2 bg-white border border-[#E8E3DA] text-terra-600 shrink-0">
          <FileText className="h-4 w-4" />
        </div>
        <div className="flex-1 leading-relaxed">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-semibold text-charcoal-900">
              Responsible Evaluation Notice:
            </span>
            <span className="text-stone-600">
              Resume quality evaluates the communicative clarity and structural consistency of the submitted document. It is strictly separate from the candidate&apos;s job match score.
            </span>
          </div>
          <p className="text-stone-500 mt-1">
            <strong className="text-charcoal-900 font-medium">Resume quality is not candidate quality.</strong> A poorly formatted resume can belong to a highly qualified candidate, and a polished resume does not prove job performance. Do not infer personality, intelligence, or suitability from document formatting alone.
          </p>
        </div>
      </div>

      {/* ── Score & Decision Row ── */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {/* Match Score Card */}
        <Card className="p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <span className="text-xs font-medium text-stone-500 uppercase tracking-wide block">
                Job match score
              </span>
              <span className="text-2xs text-stone-400">Alignment to role requirements</span>
            </div>
            <span className={cn("font-mono text-2xl font-bold", getScoreColor(score))}>
              {score}%
            </span>
          </div>
          <ProgressBar value={score} size="md" colorScheme="score" />

          <div className="rounded-lg bg-stone-50 p-3 text-xs space-y-2 border border-stone-100">
            <div className="flex justify-between text-stone-600">
              <span className="text-stone-400">Model:</span>
              <span className="font-mono">{evaluation?.semantic_summary?.model_name || "MiniLM-L6-v2"}</span>
            </div>
            <div className="flex justify-between text-stone-600">
              <span className="text-stone-400">Evidence coverage:</span>
              <span className="font-mono">
                {evaluation?.evidence_coverage !== undefined ? `${Math.round(evaluation.evidence_coverage)}%` : "N/A"}
              </span>
            </div>
            <div className="flex justify-between text-stone-600">
              <span className="text-stone-400">Mandatory criteria:</span>
              <span>
                {evaluation?.unmet_mandatory_criteria && evaluation.unmet_mandatory_criteria.length > 0 ? (
                  <span className="text-terra-600 font-medium">{evaluation.unmet_mandatory_criteria.length} unmet</span>
                ) : (
                  <span className="text-olive-700 font-medium">All satisfied</span>
                )}
              </span>
            </div>
          </div>
        </Card>

        {/* Resume Quality Card */}
        <Card className="p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <span className="text-xs font-medium text-stone-500 uppercase tracking-wide block">
                Resume quality
              </span>
              <span className="text-2xs text-stone-400">Clarity & structural completeness</span>
            </div>
            {qualityAssessment ? (
              <div className="text-right">
                <span className="font-mono text-2xl font-bold text-stone-800">
                  {Math.round(qualityAssessment.overall_score)}%
                </span>
                <span
                  className={cn(
                    "block px-2 py-0.5 rounded text-2xs font-medium border text-center mt-0.5",
                    (qualityAssessment.quality_label || "").toLowerCase().includes("good")
                      ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                      : (qualityAssessment.quality_label || "").toLowerCase().includes("moderate")
                      ? "bg-amber-50 text-amber-800 border-amber-200"
                      : "bg-rose-50 text-rose-800 border-rose-200"
                  )}
                >
                  {qualityAssessment.quality_label}
                </span>
              </div>
            ) : (
              <span className="text-xs text-stone-400 font-mono">Pending</span>
            )}
          </div>
          <ProgressBar
            value={qualityAssessment?.overall_score ?? 0}
            size="md"
            barClassName={cn(
              (qualityAssessment?.quality_label || "").toLowerCase().includes("good")
                ? "bg-emerald-600"
                : (qualityAssessment?.quality_label || "").toLowerCase().includes("moderate")
                ? "bg-amber-500"
                : "bg-rose-500"
            )}
          />

          <div className="rounded-lg bg-stone-50 p-3 text-xs space-y-2 border border-stone-100">
            <div className="flex justify-between text-stone-600">
              <span className="text-stone-400">Readability level:</span>
              <span className="font-medium text-stone-700">
                {qualityAssessment?.readability_metrics?.readability_level || "Standard"}
              </span>
            </div>
            <div className="flex justify-between text-stone-600">
              <span className="text-stone-400">Document length:</span>
              <span className="font-mono">
                {qualityAssessment?.readability_metrics?.word_count || "—"} words
              </span>
            </div>
            <div className="flex justify-between text-stone-600">
              <span className="text-stone-400">Formatting issues:</span>
              <span>
                {qualityAssessment?.detected_issues && qualityAssessment.detected_issues.length > 0 ? (
                  <span className="text-amber-700 font-medium">{qualityAssessment.detected_issues.length} detected</span>
                ) : (
                  <span className="text-emerald-700 font-medium">None flagged</span>
                )}
              </span>
            </div>
          </div>
        </Card>

        {/* Recruiter Review Decision */}
        <Card className="p-5 space-y-4">
          <div className="flex items-center justify-between border-b border-stone-100 pb-3">
            <h3 className="text-sm font-semibold text-charcoal-900">Recruiter decision & notes</h3>
            <span className="text-xs text-stone-400">Audit log</span>
          </div>

          {saveSuccess && (
            <div className="rounded-lg border border-olive-200 bg-olive-50 p-2 text-xs text-olive-700 flex items-center gap-1.5">
              <CheckCircle2 className="h-3.5 w-3.5 text-olive-600" />
              <span>Decision saved.</span>
            </div>
          )}

          <div className="space-y-3">
            <div>
              <label className="text-xs font-medium text-stone-500 block mb-1">
                Candidate status
              </label>
              <select
                value={reviewStatus}
                onChange={(e) => setReviewStatus(e.target.value)}
                className="w-full rounded-lg border border-stone-200 bg-white py-1.5 px-2.5 text-xs text-stone-800 focus:border-terra-400 focus:outline-none"
              >
                <option value="SHORTLISTED">Shortlisted</option>
                <option value="IN_REVIEW">Under review</option>
                <option value="NEEDS_REVIEW">Needs review</option>
                <option value="NOT_SHORTLISTED">Not shortlisted</option>
              </select>
            </div>

            <div>
              <label className="text-xs font-medium text-stone-500 block mb-1">
                Notes
              </label>
              <div className="flex gap-2">
                <input
                  type="text"
                  placeholder="Evaluation notes..."
                  value={reviewerNotes}
                  onChange={(e) => setReviewerNotes(e.target.value)}
                  className="flex-1 rounded-lg border border-stone-200 bg-white px-3 py-1.5 text-xs text-stone-800 placeholder-stone-400 focus:border-terra-400 focus:outline-none"
                />
                <Button
                  variant="primary"
                  size="sm"
                  isLoading={isSavingDecision}
                  onClick={handleSaveDecision}
                  leftIcon={<Save className="h-3.5 w-3.5" />}
                >
                  Save
                </Button>
              </div>
            </div>
          </div>
        </Card>
      </div>

      {/* ── Evaluation Summary ── */}
      {(evaluation?.explanation || candidate?.explanation || evaluation?.ai_review || candidate?.ai_review) && (
        <Card className="p-5 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-charcoal-900">Evaluation summary</h3>
            <span className="text-xs text-stone-400 font-mono">
              Model: {evaluation?.semantic_summary?.model_name || "MiniLM-L6-v2"}
            </span>
          </div>
          <ScreeningNarrativeView
            text={
              evaluation?.explanation ||
              candidate?.explanation ||
              evaluation?.ai_review ||
              candidate?.ai_review ||
              ""
            }
          />
        </Card>
      )}

      {/* ── Tabs: Evidence, Discrepancies, Resume Details ── */}
      <Tabs defaultValue="evidence">
        <TabsList>
          <TabsTrigger value="evidence">Role criteria match</TabsTrigger>
          <TabsTrigger value="quality">
            Resume quality
            {qualityAssessment && (
              <span
                className={cn(
                  "ml-1.5 text-2xs px-1.5 py-0.5 rounded-full font-medium border",
                  (qualityAssessment.quality_label || "").toLowerCase().includes("good")
                    ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                    : (qualityAssessment.quality_label || "").toLowerCase().includes("moderate")
                    ? "bg-amber-50 text-amber-800 border-amber-200"
                    : "bg-rose-50 text-rose-800 border-rose-200"
                )}
              >
                {Math.round(qualityAssessment.overall_score)}%
              </span>
            )}
          </TabsTrigger>
          <TabsTrigger value="discrepancies">
            Flags & anomalies
            {(() => {
              const dList =
                (evaluation?.discrepancies && evaluation.discrepancies.length > 0)
                  ? evaluation.discrepancies
                  : ((candidate as any)?.discrepancies && (candidate as any).discrepancies.length > 0)
                  ? (candidate as any).discrepancies
                  : [];
              if (dList.length === 0) return null;
              return (
                <span className="ml-1.5 text-2xs px-1.5 py-0.5 rounded-full bg-terra-100 text-terra-700 font-medium">
                  {dList.length}
                </span>
              );
            })()}
          </TabsTrigger>
          <TabsTrigger value="resume">Resume details</TabsTrigger>
        </TabsList>

        {/* ── Tab 1: Criteria Breakdown ── */}
        <TabsContent value="evidence" className="space-y-3">
          {(() => {
            const criteriaList: any[] =
              evaluation?.criteria_scores && evaluation.criteria_scores.length > 0
                ? evaluation.criteria_scores
                : ((evaluation?.criterion_results || []) as any[]).map((r) => ({
                    criterion_name: r.criterion_name,
                    score: Math.round(r.score <= 1.0 ? r.score * 100 : r.score),
                    weight: r.weight,
                    is_required: r.criterion_type === "REQUIRED",
                    explanation: r.explanation,
                    evidence: r.supporting_evidence || [],
                    match_status: r.match_status,
                  }));

            if (criteriaList.length === 0) {
              return (
                <Card>
                  <CardContent className="p-8 text-center text-stone-400 text-xs">
                    Criteria scores are not available yet.
                  </CardContent>
                </Card>
              );
            }

            return (
              <div className="space-y-3">
                {criteriaList.map((cs: any, idx: number) => {
                  const cScore = Math.round(cs.score ?? 0);
                  const evidenceList: any[] = cs.evidence || cs.supporting_evidence || [];
                  const isMatch = cScore >= 80;
                  const isPartial = cScore > 0 && cScore < 80;
                  const isUnmet = cScore === 0;

                  return (
                    <div
                      key={idx}
                      className="rounded-xl border border-stone-200 bg-white p-4 space-y-3 shadow-subtle"
                    >
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="font-semibold text-charcoal-900 text-sm">
                            {cs.criterion_name}
                          </span>
                          {cs.is_required && (
                            <span className="text-2xs font-medium text-amber-700 bg-amber-50 border border-amber-200 px-1.5 py-0.5 rounded">
                              Required
                            </span>
                          )}
                          <span className="text-xs text-stone-400 font-mono">
                            Weight: {cs.weight ?? 0.2}
                          </span>
                          {isMatch ? (
                            <span className="text-xs text-olive-700 font-medium">
                              Satisfied ({cScore}%)
                            </span>
                          ) : isPartial ? (
                            <span className="text-xs text-amber-700 font-medium">
                              Partial ({cScore}%)
                            </span>
                          ) : (
                            <span className="text-xs text-terra-700 font-medium">
                              Unmet (0%)
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-2">
                          <span className={cn("font-mono text-xs font-semibold", getScoreColor(cScore))}>
                            {cScore}%
                          </span>
                          <div className="w-20">
                            <ProgressBar value={cScore} size="sm" colorScheme="score" />
                          </div>
                        </div>
                      </div>

                      {/* Explanation */}
                      <p className="text-xs text-stone-600 leading-relaxed bg-stone-50 p-2.5 rounded-lg border border-stone-100">
                        {cs.explanation || (isUnmet
                          ? `No verifiable experience or skills found for '${cs.criterion_name}'.`
                          : `Criterion satisfied based on resume analysis.`
                        )}
                      </p>

                      {/* Evidence Quotes */}
                      {evidenceList.length > 0 && (
                        <div className="space-y-1.5 pt-1">
                          <p className="text-2xs font-medium text-stone-400 uppercase tracking-wide">
                            Resume citations ({evidenceList.length}):
                          </p>
                          <div className="space-y-1">
                            {evidenceList.map((ev: any, evIdx: number) => {
                              const text = typeof ev === "string" ? ev : ev.text || ev.snippet || JSON.stringify(ev);
                              return (
                                <div
                                  key={evIdx}
                                  className="text-xs text-stone-700 bg-stone-50 p-2 rounded border-l-2 border-stone-300 font-mono leading-relaxed"
                                >
                                  "{text}"
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            );
          })()}
        </TabsContent>

        {/* ── Tab: Resume Quality Assessment ── */}
        <TabsContent value="quality" className="space-y-6">
          {!qualityAssessment ? (
            <Card className="p-8 text-center text-stone-400">
              <FileText className="h-8 w-8 text-stone-300 mx-auto mb-2" />
              <p className="text-sm font-medium text-stone-700">Resume Quality Assessment Pending</p>
              <p className="text-xs text-stone-500 mt-1 max-w-sm mx-auto">
                Quality metrics evaluate communicative clarity and structural consistency once text extraction is complete.
              </p>
            </Card>
          ) : (
            <>
              {/* Executive Summary Card */}
              <Card className="p-5 space-y-3">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-stone-100 pb-3">
                  <div>
                    <h3 className="text-sm font-semibold text-charcoal-900 flex items-center gap-2">
                      <FileText className="h-4 w-4 text-terra-600" />
                      Resume Document Quality Report
                    </h3>
                    <p className="text-xs text-stone-500 mt-0.5">
                      Evaluated against the 10-criterion communicative rubric independently from job-match criteria.
                    </p>
                  </div>
                  <div className="flex items-center gap-2 self-start sm:self-auto">
                    <span className="font-mono text-lg font-bold text-stone-800">
                      {Math.round(qualityAssessment.overall_score)}/100
                    </span>
                    <span
                      className={cn(
                        "px-2.5 py-1 rounded text-xs font-medium border",
                        (qualityAssessment.quality_label || "").toLowerCase().includes("good")
                          ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                          : (qualityAssessment.quality_label || "").toLowerCase().includes("moderate")
                          ? "bg-amber-50 text-amber-800 border-amber-200"
                          : "bg-rose-50 text-rose-800 border-rose-200"
                      )}
                    >
                      {qualityAssessment.quality_label}
                    </span>
                  </div>
                </div>

                <p className="text-xs text-stone-700 leading-relaxed">
                  {qualityAssessment.executive_summary}
                </p>

                {qualityAssessment.responsible_ai_notice && (
                  <p className="text-2xs text-stone-400 italic pt-2 border-t border-stone-100">
                    {qualityAssessment.responsible_ai_notice}
                  </p>
                )}
              </Card>

              {/* Rubric Breakdown by Criterion */}
              <Card className="p-5 space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-charcoal-900">
                    Evaluation by Quality Criterion
                  </h3>
                  <span className="text-xs text-stone-400 font-mono">10-point transparent rubric</span>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="border-b border-stone-200 bg-stone-50 text-2xs uppercase tracking-wide text-stone-500">
                        <th className="py-2.5 px-3">Criterion</th>
                        <th className="py-2.5 px-3 w-20">Weight</th>
                        <th className="py-2.5 px-3 w-28">Score</th>
                        <th className="py-2.5 px-3 w-32">Status</th>
                        <th className="py-2.5 px-3">Observable Evidence & Notes</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-stone-100">
                      {qualityAssessment.criterion_results.map((c) => {
                        const cScore = Math.round(c.score);
                        return (
                          <tr key={c.criterion_key} className="hover:bg-stone-50/60 transition-colors">
                            <td className="py-3 px-3">
                              <span className="font-medium text-stone-800 block">{c.criterion_name}</span>
                              <span className="text-2xs font-mono text-stone-400">{c.criterion_key}</span>
                            </td>
                            <td className="py-3 px-3 font-mono text-stone-500">
                              {Math.round(c.weight * 100)}%
                            </td>
                            <td className="py-3 px-3">
                              <div className="flex items-center gap-1.5">
                                <span className={cn(
                                  "font-mono font-semibold",
                                  cScore >= 75 ? "text-emerald-700" : cScore >= 50 ? "text-amber-700" : "text-rose-700"
                                )}>
                                  {cScore}
                                </span>
                                <span className="text-stone-300">/100</span>
                              </div>
                            </td>
                            <td className="py-3 px-3">
                              <span
                                className={cn(
                                  "inline-flex items-center px-2 py-0.5 rounded text-2xs font-medium border",
                                  c.status.toLowerCase().includes("good") || c.status.toLowerCase().includes("high") || c.status.toLowerCase().includes("clear")
                                    ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                                    : c.status.toLowerCase().includes("moderate") || c.status.toLowerCase().includes("acceptable")
                                    ? "bg-amber-50 text-amber-800 border-amber-200"
                                    : "bg-rose-50 text-rose-800 border-rose-200"
                                )}
                              >
                                {c.status}
                              </span>
                            </td>
                            <td className="py-3 px-3 text-stone-600 leading-relaxed">
                              <p>{c.observations}</p>
                              {c.evidence_snippets && c.evidence_snippets.length > 0 && (
                                <div className="mt-1 flex flex-wrap gap-1">
                                  {c.evidence_snippets.slice(0, 3).map((snippet, sIdx) => (
                                    <span
                                      key={sIdx}
                                      className="inline-block bg-stone-100 text-stone-600 text-2xs px-1.5 py-0.5 rounded border border-stone-200 font-mono max-w-md truncate"
                                      title={snippet}
                                    >
                                      &quot;{snippet}&quot;
                                    </span>
                                  ))}
                                </div>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </Card>

              {/* Strengths & Improvement Areas Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                {/* Strengths */}
                <Card className="p-5 space-y-3 bg-emerald-50/20 border-emerald-200/60">
                  <h4 className="text-xs font-semibold uppercase tracking-wide text-emerald-800 flex items-center gap-1.5">
                    <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                    Strong Document Attributes
                  </h4>
                  {qualityAssessment.strong_areas.length === 0 ? (
                    <p className="text-xs text-stone-500 italic">No specific standout strengths highlighted.</p>
                  ) : (
                    <div className="space-y-3">
                      {qualityAssessment.strong_areas.map((str, sIdx) => (
                        <div key={sIdx} className="rounded-lg bg-white p-3 border border-emerald-100 shadow-2xs space-y-1">
                          <p className="text-xs font-medium text-emerald-950">{str.title}</p>
                          <p className="text-xs text-stone-600">{str.description}</p>
                          {str.evidence_quote && (
                            <p className="text-2xs text-stone-500 italic bg-stone-50 p-1.5 rounded border border-stone-100 font-mono">
                              &quot;{str.evidence_quote}&quot;
                            </p>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </Card>

                {/* Improvements */}
                <Card className="p-5 space-y-3 bg-amber-50/20 border-amber-200/60">
                  <h4 className="text-xs font-semibold uppercase tracking-wide text-amber-800 flex items-center gap-1.5">
                    <AlertCircle className="h-4 w-4 text-amber-600" />
                    Areas for Improvement
                  </h4>
                  {qualityAssessment.areas_for_improvement.length === 0 ? (
                    <p className="text-xs text-stone-500 italic">No critical improvement areas identified.</p>
                  ) : (
                    <div className="space-y-3">
                      {qualityAssessment.areas_for_improvement.map((imp, iIdx) => (
                        <div key={iIdx} className="rounded-lg bg-white p-3 border border-amber-100 shadow-2xs space-y-1">
                          <p className="text-xs font-medium text-amber-950">{imp.title}</p>
                          <p className="text-xs text-stone-700">{imp.recommendation}</p>
                          <p className="text-2xs text-stone-500">{imp.rationale}</p>
                        </div>
                      ))}
                    </div>
                  )}
                </Card>
              </div>

              {/* Detected Issues */}
              {qualityAssessment.detected_issues && qualityAssessment.detected_issues.length > 0 && (
                <Card className="p-5 space-y-3">
                  <h4 className="text-xs font-semibold uppercase tracking-wide text-charcoal-900 flex items-center gap-1.5">
                    <AlertTriangle className="h-4 w-4 text-amber-600" />
                    Detected Document & Formatting Issues ({qualityAssessment.detected_issues.length})
                  </h4>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead>
                        <tr className="border-b border-stone-200 bg-stone-50 text-2xs uppercase tracking-wide text-stone-500">
                          <th className="py-2 px-3 w-28">Severity</th>
                          <th className="py-2 px-3 w-40">Issue Type</th>
                          <th className="py-2 px-3">Description</th>
                          <th className="py-2 px-3">Context</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-stone-100">
                        {qualityAssessment.detected_issues.map((issue, isIdx) => (
                          <tr key={isIdx} className="hover:bg-stone-50/50">
                            <td className="py-2 px-3">
                              <span
                                className={cn(
                                  "px-2 py-0.5 rounded text-2xs font-medium border",
                                  issue.severity === "HIGH"
                                    ? "bg-rose-50 text-rose-700 border-rose-200"
                                    : issue.severity === "MEDIUM"
                                    ? "bg-amber-50 text-amber-700 border-amber-200"
                                    : "bg-stone-100 text-stone-600 border-stone-200"
                                )}
                              >
                                {issue.severity}
                              </span>
                            </td>
                            <td className="py-2 px-3 font-mono text-stone-700">{issue.issue_type}</td>
                            <td className="py-2 px-3 text-stone-800">{issue.description}</td>
                            <td className="py-2 px-3 text-stone-500 font-mono text-2xs">
                              {issue.context || "—"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </Card>
              )}

              {/* Readability Metrics & Extraction Diagnostics */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                {/* Readability Metrics */}
                <Card className="p-5 space-y-3">
                  <h4 className="text-xs font-semibold uppercase tracking-wide text-charcoal-900">
                    Readability & Structure Metrics
                  </h4>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div className="p-2.5 bg-stone-50 rounded border border-stone-100">
                      <span className="text-stone-400 block text-2xs">Word Count</span>
                      <span className="font-mono font-medium text-stone-800">
                        {qualityAssessment.readability_metrics.word_count} words
                      </span>
                    </div>
                    <div className="p-2.5 bg-stone-50 rounded border border-stone-100">
                      <span className="text-stone-400 block text-2xs">Avg Words/Sentence</span>
                      <span className="font-mono font-medium text-stone-800">
                        {qualityAssessment.readability_metrics.avg_words_per_sentence}
                      </span>
                    </div>
                    <div className="p-2.5 bg-stone-50 rounded border border-stone-100">
                      <span className="text-stone-400 block text-2xs">Bullet List Ratio</span>
                      <span className="font-mono font-medium text-stone-800">
                        {Math.round(qualityAssessment.readability_metrics.bullet_ratio * 100)}% ({qualityAssessment.readability_metrics.bullet_count} items)
                      </span>
                    </div>
                    <div className="p-2.5 bg-stone-50 rounded border border-stone-100">
                      <span className="text-stone-400 block text-2xs">Action Verbs Found</span>
                      <span className="font-mono font-medium text-stone-800">
                        {qualityAssessment.readability_metrics.action_verb_count}
                      </span>
                    </div>
                    <div className="p-2.5 bg-stone-50 rounded border border-stone-100">
                      <span className="text-stone-400 block text-2xs">Quantified Metrics</span>
                      <span className="font-mono font-medium text-stone-800">
                        {qualityAssessment.readability_metrics.quantified_metric_count} outcomes
                      </span>
                    </div>
                    <div className="p-2.5 bg-stone-50 rounded border border-stone-100">
                      <span className="text-stone-400 block text-2xs">Readability Classification</span>
                      <span className="font-medium text-stone-800">
                        {qualityAssessment.readability_metrics.readability_level}
                      </span>
                    </div>
                  </div>
                </Card>

                {/* Section Completeness Audit */}
                <Card className="p-5 space-y-3">
                  <h4 className="text-xs font-semibold uppercase tracking-wide text-charcoal-900">
                    Section Completeness Audit
                  </h4>
                  <div className="space-y-1.5 text-xs">
                    {Object.entries(qualityAssessment.section_completeness || {}).map(([secKey, secVal]: [string, any]) => (
                      <div
                        key={secKey}
                        className="flex items-center justify-between p-2 rounded bg-stone-50 border border-stone-100"
                      >
                        <span className="capitalize font-medium text-stone-700">{secKey}</span>
                        <div className="flex items-center gap-2">
                          {secVal?.word_count !== undefined && (
                            <span className="text-2xs font-mono text-stone-400">
                              {secVal.word_count} words
                            </span>
                          )}
                          <span
                            className={cn(
                              "px-2 py-0.5 rounded text-2xs font-medium border",
                              secVal?.present
                                ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                                : "bg-stone-100 text-stone-500 border-stone-200"
                            )}
                          >
                            {secVal?.status || (secVal?.present ? "Present" : "Missing")}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* Extraction Diagnostics */}
                  {qualityAssessment.extraction_diagnostics && (
                    <div className="pt-2 border-t border-stone-100 text-2xs text-stone-500 flex justify-between">
                      <span>Chars: {qualityAssessment.extraction_diagnostics.char_count}</span>
                      <span>Lines: {qualityAssessment.extraction_diagnostics.line_count}</span>
                      <span>Confidence: {Math.round(qualityAssessment.extraction_diagnostics.parse_confidence * 100)}%</span>
                      {qualityAssessment.extraction_diagnostics.ocr_needed && (
                        <span className="text-amber-600 font-medium">Scanned/OCR</span>
                      )}
                    </div>
                  )}
                </Card>
              </div>
            </>
          )}
        </TabsContent>

        {/* ── Tab 2: Discrepancies ── */}
        <TabsContent value="discrepancies" className="space-y-3">
          <Card>
            <CardHeader className="pb-3 border-b border-stone-100">
              <CardTitle className="text-sm">Detected flags & timeline checks</CardTitle>
              <CardDescription>
                Employment gaps, uncorroborated claims, and missing mandatory criteria.
              </CardDescription>
            </CardHeader>
            <CardContent className="pt-4">
              {(() => {
                const discrepanciesList =
                  evaluation?.discrepancies && evaluation.discrepancies.length > 0
                    ? evaluation.discrepancies
                    : (candidate as any)?.discrepancies && (candidate as any).discrepancies.length > 0
                    ? (candidate as any).discrepancies
                    : [
                        ...(evaluation?.conflicting_criteria || []).map((c: string) => ({
                          severity: "HIGH",
                          type: "Conflicting Evidence",
                          title: `Conflicting Evidence: ${c}`,
                          description: `Conflicting evidence flagged for criterion '${c}'`,
                          criterion_name: c,
                        })),
                        ...(evaluation?.unmet_mandatory_criteria || []).map((u: string) => ({
                          severity: "CRITICAL",
                          type: "Mandatory Requirement Unmet",
                          title: `Mandatory Requirement Unmet: ${u}`,
                          description: `Mandatory requirement '${u}' was not verified`,
                          criterion_name: u,
                        })),
                      ];

                if (discrepanciesList.length === 0) {
                  return (
                    <div className="p-8 text-center text-xs text-olive-700 flex flex-col items-center gap-2">
                      <CheckCircle2 className="h-6 w-6 text-olive-600" />
                      <span className="font-semibold text-charcoal-900">
                        No discrepancies detected
                      </span>
                      <span className="text-stone-500">
                        The candidate's credentials appear consistent with the position requirements.
                      </span>
                    </div>
                  );
                }

                return (
                  <div className="space-y-3">
                    {discrepanciesList.map((disc: any, idx: number) => {
                      const sev = (disc.severity || "MEDIUM").toUpperCase();
                      const isCritical = sev === "CRITICAL";

                      return (
                        <div
                          key={idx}
                          className={cn(
                            "rounded-lg border p-3.5 text-xs space-y-1",
                            isCritical
                              ? "border-terra-200 bg-terra-50 text-terra-900"
                              : "border-stone-200 bg-stone-50 text-stone-800"
                          )}
                        >
                          <div className="flex items-center gap-2">
                            <span
                              className={cn(
                                "text-2xs uppercase font-bold tracking-wide px-1.5 py-0.5 rounded",
                                isCritical
                                  ? "bg-terra-200 text-terra-800"
                                  : "bg-stone-200 text-stone-700"
                              )}
                            >
                              {sev}
                            </span>
                            <span className="font-semibold text-charcoal-900">
                              {disc.title || disc.type || "Flag"}
                            </span>
                          </div>
                          <p className="text-stone-600">{disc.description || disc.detail}</p>
                        </div>
                      );
                    })}
                  </div>
                );
              })()}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── Tab 3: Resume Details ── */}
        <TabsContent value="resume" className="space-y-5">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Contact */}
            <Card className="p-4 space-y-2 text-xs">
              <h4 className="font-semibold text-charcoal-900 mb-2">Contact details</h4>
              <div className="flex justify-between py-1 border-b border-stone-100">
                <span className="text-stone-400">Email:</span>
                <span className="font-mono text-charcoal-900">{candidate.email || "—"}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-stone-100">
                <span className="text-stone-400">Phone:</span>
                <span className="font-mono text-charcoal-900">{candidate.phone || "—"}</span>
              </div>
              {candidate.contact?.linkedin && (
                <div className="flex justify-between py-1 border-b border-stone-100">
                  <span className="text-stone-400">LinkedIn:</span>
                  <a
                    href={candidate.contact.linkedin.startsWith("http") ? candidate.contact.linkedin : `https://${candidate.contact.linkedin}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-terra-600 hover:underline flex items-center gap-1"
                  >
                    Profile <ExternalLink className="h-3 w-3" />
                  </a>
                </div>
              )}
            </Card>

            {/* Document Telemetry */}
            <Card className="p-4 space-y-2 text-xs">
              <h4 className="font-semibold text-charcoal-900 mb-2">Document info</h4>
              <div className="flex justify-between py-1 border-b border-stone-100">
                <span className="text-stone-400">File:</span>
                <span className="font-mono text-charcoal-900 truncate max-w-[180px]">{candidate.original_filename}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-stone-100">
                <span className="text-stone-400">Type:</span>
                <span className="font-mono uppercase text-charcoal-900">{candidate.file_type || "PDF"}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-stone-100">
                <span className="text-stone-400">Status:</span>
                <span className="text-olive-700 font-medium">{candidate.processing_status}</span>
              </div>
            </Card>
          </div>

          {/* Extracted Skills */}
          <Card className="p-4 space-y-3">
            <h4 className="text-xs font-semibold text-charcoal-900 uppercase tracking-wide">
              Extracted skills ({candidate.skills?.length || 0})
            </h4>
            {candidate.skills && candidate.skills.length > 0 ? (
              <div className="flex flex-wrap gap-1.5">
                {candidate.skills.map((skill: any, idx: number) => {
                  const skillName =
                    typeof skill === "string"
                      ? skill
                      : skill.skill_name || skill.normalized_name || skill.name || JSON.stringify(skill);
                  return (
                    <span
                      key={idx}
                      className="rounded bg-stone-100 px-2 py-1 text-xs font-mono text-stone-700 border border-stone-200"
                    >
                      {skillName}
                    </span>
                  );
                })}
              </div>
            ) : (
              <p className="text-xs text-stone-400">No skills parsed.</p>
            )}
          </Card>

          {/* Work Experience */}
          <Card className="p-4 space-y-3">
            <h4 className="text-xs font-semibold text-charcoal-900 uppercase tracking-wide">
              Experience history ({candidate.experience?.length || 0})
            </h4>
            {candidate.experience && candidate.experience.length > 0 ? (
              <div className="space-y-3">
                {candidate.experience.map((exp: any, idx: number) => {
                  const title = exp.job_title || exp.title || exp.role || "Role";
                  const company = exp.employer || exp.company || "";
                  const duration = exp.dates || exp.duration || "";
                  const description = exp.extracted_description || exp.description || "";
                  return (
                    <div key={idx} className="rounded-lg border border-stone-200 p-3 space-y-1 text-xs">
                      <div className="flex justify-between">
                        <span className="font-semibold text-charcoal-900">{title}</span>
                        {duration && <span className="text-stone-400 font-mono text-2xs">{duration}</span>}
                      </div>
                      {company && <p className="text-stone-500 font-medium">{company}</p>}
                      {description && <p className="text-stone-600 mt-1 whitespace-pre-line">{description}</p>}
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="text-xs text-stone-400">No work experience parsed.</p>
            )}
          </Card>

          {/* Full Extracted Text */}
          <Card className="p-4 space-y-2">
            <div className="flex justify-between items-center">
              <h4 className="text-xs font-semibold text-charcoal-900 uppercase tracking-wide">
                Raw resume text
              </h4>
              {candidate.extracted_text && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    navigator.clipboard.writeText(candidate.extracted_text || "");
                    setCopiedText(true);
                    setTimeout(() => setCopiedText(false), 2000);
                  }}
                  leftIcon={copiedText ? <Check className="h-3 w-3 text-olive-600" /> : <Copy className="h-3 w-3" />}
                >
                  {copiedText ? "Copied" : "Copy text"}
                </Button>
              )}
            </div>
            {candidate.extracted_text ? (
              <div className="rounded border border-stone-200 bg-stone-50 p-3 font-mono text-xs text-stone-700 max-h-80 overflow-y-auto leading-relaxed whitespace-pre-wrap select-text">
                {candidate.extracted_text}
              </div>
            ) : (
              <p className="text-xs text-stone-400">No raw text available.</p>
            )}
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
