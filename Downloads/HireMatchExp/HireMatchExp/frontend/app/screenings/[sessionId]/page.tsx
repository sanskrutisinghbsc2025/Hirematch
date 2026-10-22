"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  Users,
  Sliders,
  BarChart3,
  FileDown,
  ArrowRight,
  Search,
  Filter,
  CheckCircle,
  AlertTriangle,
  AlertCircle,
  Play,
  RotateCcw,
  Eye,
  CheckSquare,
  Square,
  Trash2,
  Star,
  Download,
  ChevronLeft,
  ChevronRight,
  Upload,
  FileText,
  Check,
} from "lucide-react";
import { apiClient } from "@/lib/api/client";
import { ScreeningSession, CandidateSummary } from "@/lib/types/api";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { Modal } from "@/components/ui/Modal";
import { getScoreColor, cn } from "@/lib/utils";

export default function SessionWorkspacePage() {
  const params = useParams();
  const router = useRouter();
  const sessionId = params.sessionId as string;

  const [session, setSession] = useState<ScreeningSession | null>(null);
  const [candidates, setCandidates] = useState<CandidateSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [isEvaluating, setIsEvaluating] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [uploadFiles, setUploadFiles] = useState<File[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [isRerunning, setIsRerunning] = useState(false);

  // Tabs & Views
  const [activeTab, setActiveTab] = useState<"all" | "shortlisted" | "strong" | "under_review">("all");

  // Filters & Search
  const [search, setSearch] = useState("");
  const [tierFilter, setTierFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [qualityFilter, setQualityFilter] = useState<string>("all");
  const [selectedIds, setSelectedIds] = useState<string[]>([]);

  // Pagination
  const [pageSize, setPageSize] = useState<number>(50);
  const [page, setPage] = useState<number>(1);

  const loadData = async () => {
    try {
      setLoading(true);
      const [sessRes, candRes] = await Promise.all([
        apiClient.getSession(sessionId),
        apiClient.getCandidates(sessionId, { page: 1, limit: 500 }),
      ]);
      setSession(sessRes);
      setCandidates(candRes.items);
      setTotal(candRes.total);
    } catch (err: any) {
      console.error("Error loading session:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (sessionId) loadData();
  }, [sessionId]);

  const handleDeleteSession = async () => {
    try {
      setIsDeleting(true);
      await apiClient.deleteSession(sessionId);
      router.push("/screenings");
    } catch (err: any) {
      alert("Failed to delete session: " + err.message);
    } finally {
      setIsDeleting(false);
    }
  };

  const handleRunEvaluation = async () => {
    try {
      setIsEvaluating(true);
      await apiClient.evaluateSession(sessionId);
      await loadData();
    } catch (err: any) {
      alert("Evaluation error: " + err.message);
    } finally {
      setIsEvaluating(false);
    }
  };

  const handleRerunFullPipeline = async () => {
    try {
      setIsRerunning(true);
      await apiClient.rerunPipeline(sessionId);
      await loadData();
      alert("Pipeline re-run completed successfully.");
    } catch (err: any) {
      alert("Pipeline re-run error: " + err.message);
    } finally {
      setIsRerunning(false);
    }
  };

  const handleUploadSubmit = async () => {
    if (uploadFiles.length === 0) {
      alert("Please select at least one resume file to upload.");
      return;
    }
    try {
      setIsUploading(true);
      const res = await apiClient.uploadResumes(sessionId, uploadFiles);
      setUploadFiles([]);
      setShowUploadModal(false);
      setIsRerunning(true);
      await apiClient.rerunPipeline(sessionId);
      await loadData();
      alert(`Added and scored ${res.uploaded} resume(s).`);
    } catch (err: any) {
      alert("Upload error: " + err.message);
    } finally {
      setIsUploading(false);
      setIsRerunning(false);
    }
  };

  const handleToggleSelect = (id: string) => {
    if (selectedIds.includes(id)) {
      setSelectedIds(selectedIds.filter((item) => item !== id));
    } else {
      if (selectedIds.length >= 5) {
        alert("You can compare up to 5 candidates at once.");
        return;
      }
      setSelectedIds([...selectedIds, id]);
    }
  };

  const handleSelectAll = () => {
    if (selectedIds.length === filteredCandidates.length) {
      setSelectedIds([]);
    } else {
      setSelectedIds(filteredCandidates.slice(0, 5).map((c) => c.id));
    }
  };

  const handleQuickShortlist = async (candidateId: string, currentStatus: string) => {
    const isShortlisted = (currentStatus || "").toUpperCase() === "SHORTLISTED";
    const nextStatus = isShortlisted ? "IN_REVIEW" : "SHORTLISTED";
    const currentCandidate = candidates.find((c) => c.id === candidateId);
    const existingNotes = (currentCandidate as any)?.reviewer_notes ?? (currentCandidate as any)?.notes;
    try {
      setCandidates((prev) =>
        prev.map((c) => (c.id === candidateId ? { ...c, review_status: nextStatus } : c))
      );
      await apiClient.updateShortlistStatus(
        candidateId,
        {
          review_status: nextStatus,
          reviewer_notes: existingNotes !== undefined ? existingNotes : undefined,
        },
        sessionId
      );
    } catch (err: any) {
      setCandidates((prev) =>
        prev.map((c) => (c.id === candidateId ? { ...c, review_status: currentStatus } : c))
      );
      alert("Failed to update status: " + err.message);
    }
  };

  const exportShortlistCsv = () => {
    const shortlistedList = candidates.filter((c) => (c.review_status || "").toUpperCase() === "SHORTLISTED");
    if (shortlistedList.length === 0) {
      alert("No candidates have been shortlisted yet.");
      return;
    }
    const headers = ["Rank", "Candidate Name", "Email", "Original Filename", "Match Score", "Fit Tier", "Review Status"];
    const rows = shortlistedList.map((c) => [
      c.rank || "",
      `"${(c.name || "").replace(/"/g, '""')}"`,
      `"${(c.email || "").replace(/"/g, '""')}"`,
      `"${(c.original_filename || "").replace(/"/g, '""')}"`,
      c.overall_score !== null ? `${Math.round(c.overall_score)}%` : "Pending",
      c.fit_tier || "",
      c.review_status || "SHORTLISTED",
    ]);
    const csvContent = [headers.join(","), ...rows.map((r) => r.join(","))].join("\n");
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", `shortlist_${session?.title || "candidates"}_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const shortlistedCount = candidates.filter((c) => (c.review_status || "").toUpperCase() === "SHORTLISTED").length;
  const strongCount = candidates.filter((c) => (c.overall_score || 0) >= 80).length;
  const underReviewCount = candidates.filter((c) => c.overall_score === null || (c.overall_score || 0) < 60).length;

  const filteredCandidates = candidates.filter((c) => {
    if (activeTab === "shortlisted" && (c.review_status || "").toUpperCase() !== "SHORTLISTED") return false;
    if (activeTab === "strong" && (c.overall_score || 0) < 80) return false;
    if (activeTab === "under_review" && (c.overall_score !== null && (c.overall_score || 0) >= 60)) return false;

    const candidateName = c.name || c.original_filename || "Candidate";
    const s = (search || "").toLowerCase().trim();
    const matchesSearch =
      !s ||
      candidateName.toLowerCase().includes(s) ||
      (c.email ? c.email.toLowerCase().includes(s) : false) ||
      (c.original_filename ? c.original_filename.toLowerCase().includes(s) : false);

    const rawTier =
      c.fit_tier ||
      (c.overall_score !== null && c.overall_score !== undefined
        ? c.overall_score >= 80
          ? "strong_match"
          : c.overall_score >= 60
          ? "potential_match"
          : "under_review"
        : "under_review");
    const matchesTier =
      tierFilter === "all" || rawTier.toLowerCase().replace(/\s+/g, "_") === tierFilter;

    const rawStatus = (c.review_status || "pending").toLowerCase();
    const matchesStatus = statusFilter === "all" || rawStatus === statusFilter;

    const rawQuality = (c.resume_quality_label || "").toLowerCase();
    const matchesQuality =
      qualityFilter === "all" ||
      (qualityFilter === "good" && rawQuality.includes("good")) ||
      (qualityFilter === "moderate" && rawQuality.includes("moderate")) ||
      (qualityFilter === "poor" && rawQuality.includes("poor"));

    return matchesSearch && matchesTier && matchesStatus && matchesQuality;
  });

  const totalPages = Math.max(1, Math.ceil(filteredCandidates.length / (pageSize === 1000 ? filteredCandidates.length || 1 : pageSize)));
  const paginatedCandidates = pageSize === 1000 ? filteredCandidates : filteredCandidates.slice((page - 1) * pageSize, page * pageSize);

  const sessionTitle =
    (session as any)?.session_name ||
    (session as any)?.job_title ||
    session?.title ||
    session?.name ||
    "Screening Session";

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* ── Breadcrumb & Header ── */}
      <div>
        <div className="flex items-center gap-1.5 text-xs text-stone-400 mb-2">
          <Link href="/screenings" className="hover:text-stone-600 transition-colors">
            Screenings
          </Link>
          <span>/</span>
          <span className="text-stone-600">{sessionTitle}</span>
        </div>

        <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2.5">
              <h1 className="text-xl font-semibold text-charcoal-900">{sessionTitle}</h1>
              {session?.status && <Badge status={session.status}>{session.status}</Badge>}
            </div>
            {session?.description && (
              <p className="text-sm text-stone-500 mt-1 max-w-2xl">{session.description}</p>
            )}
          </div>

          {/* Action Toolbar */}
          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="primary"
              size="sm"
              onClick={() => setShowUploadModal(true)}
              leftIcon={<Upload className="h-3.5 w-3.5" />}
            >
              Upload resumes
            </Button>

            <Button
              variant="secondary"
              size="sm"
              isLoading={isRerunning || isEvaluating}
              onClick={handleRerunFullPipeline}
              leftIcon={<RotateCcw className="h-3.5 w-3.5" />}
            >
              Re-run
            </Button>

            {selectedIds.length >= 2 && (
              <Button
                variant="outline"
                size="sm"
                onClick={() =>
                  router.push(
                    `/screenings/${sessionId}/compare?candidates=${selectedIds.join(",")}`
                  )
                }
              >
                Compare ({selectedIds.length})
              </Button>
            )}

            <Link href={`/screenings/${sessionId}/simulator`}>
              <Button
                variant="outline"
                size="sm"
                leftIcon={<Sliders className="h-3.5 w-3.5 text-stone-400" />}
              >
                Simulator
              </Button>
            </Link>

            <Link href={`/screenings/${sessionId}/analytics`}>
              <Button
                variant="outline"
                size="sm"
                leftIcon={<BarChart3 className="h-3.5 w-3.5 text-stone-400" />}
              >
                Analytics
              </Button>
            </Link>

            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowDeleteModal(true)}
              className="text-stone-400 hover:text-terra-600"
              leftIcon={<Trash2 className="h-3.5 w-3.5" />}
            >
              Delete
            </Button>
          </div>
        </div>
      </div>

      {/* ── Pending Evaluation Banner ── */}
      {candidates.length > 0 && candidates.some((c) => c.overall_score === null) && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <AlertTriangle className="h-4 w-4 text-amber-600 shrink-0" />
            <div>
              <p className="text-sm font-medium text-amber-900">
                Candidates waiting to be scored
              </p>
              <p className="text-xs text-amber-700 mt-0.5">
                Resumes have been uploaded but haven't been evaluated against your criteria yet.
              </p>
            </div>
          </div>
          <Button
            variant="primary"
            size="sm"
            isLoading={isEvaluating}
            onClick={handleRunEvaluation}
            leftIcon={<Play className="h-3.5 w-3.5" />}
          >
            Score candidates
          </Button>
        </div>
      )}

      {/* ── View Tabs & Export ── */}
      <div className="border-b border-stone-300 flex items-center justify-between gap-4">
        <div className="flex items-center gap-6 overflow-x-auto">
          <button
            onClick={() => { setActiveTab("all"); setPage(1); }}
            className={cn(
              "pb-3 text-sm transition-colors border-b-2 flex items-center gap-1.5 -mb-px shrink-0",
              activeTab === "all"
                ? "text-olive-700 border-olive-500 font-medium"
                : "text-stone-500 hover:text-stone-800 border-transparent"
            )}
          >
            All candidates
            <span className="text-xs text-stone-400 font-mono">({total})</span>
          </button>

          <button
            onClick={() => { setActiveTab("shortlisted"); setPage(1); }}
            className={cn(
              "pb-3 text-sm transition-colors border-b-2 flex items-center gap-1.5 -mb-px shrink-0",
              activeTab === "shortlisted"
                ? "text-olive-700 border-olive-500 font-medium"
                : "text-stone-500 hover:text-stone-800 border-transparent"
            )}
          >
            <Star className={cn("h-3.5 w-3.5", activeTab === "shortlisted" && "fill-amber-400 text-amber-400")} />
            Shortlisted
            <span className="text-xs text-stone-400 font-mono">({shortlistedCount})</span>
          </button>

          <button
            onClick={() => { setActiveTab("strong"); setPage(1); }}
            className={cn(
              "pb-3 text-sm transition-colors border-b-2 flex items-center gap-1.5 -mb-px shrink-0",
              activeTab === "strong"
                ? "text-olive-700 border-olive-500 font-medium"
                : "text-stone-500 hover:text-stone-800 border-transparent"
            )}
          >
            Strong matches
            <span className="text-xs text-stone-400 font-mono">({strongCount})</span>
          </button>

          <button
            onClick={() => { setActiveTab("under_review"); setPage(1); }}
            className={cn(
              "pb-3 text-sm transition-colors border-b-2 flex items-center gap-1.5 -mb-px shrink-0",
              activeTab === "under_review"
                ? "text-olive-700 border-olive-500 font-medium"
                : "text-stone-500 hover:text-stone-800 border-transparent"
            )}
          >
            Needs review
            <span className="text-xs text-stone-400 font-mono">({underReviewCount})</span>
          </button>
        </div>

        {shortlistedCount > 0 && (
          <Button
            variant="ghost"
            size="sm"
            onClick={exportShortlistCsv}
            leftIcon={<Download className="h-3.5 w-3.5 text-stone-400" />}
            className="text-stone-500 hover:text-stone-700 shrink-0 mb-2"
          >
            Export shortlist (.csv)
          </Button>
        )}
      </div>

      {/* ── Search & Filter Controls ── */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
        <div className="flex flex-1 items-center gap-2">
          <div className="relative flex-1 sm:max-w-xs">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-stone-400" />
            <input
              type="text"
              placeholder="Search by name or email..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full rounded-lg border border-stone-200 bg-white py-1.5 pl-8 pr-3 text-sm text-stone-800 placeholder-stone-400 focus:border-olive-500 focus:outline-none focus:ring-2 focus:ring-olive-500/20"
            />
          </div>

          <select
            value={tierFilter}
            onChange={(e) => setTierFilter(e.target.value)}
            className="rounded-lg border border-stone-200 bg-white py-1.5 px-2.5 text-xs text-stone-600 focus:border-olive-500 focus:outline-none"
          >
            <option value="all">All tiers</option>
            <option value="strong_match">Strong match</option>
            <option value="potential_match">Potential match</option>
            <option value="under_review">Under review</option>
          </select>

          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="rounded-lg border border-stone-200 bg-white py-1.5 px-2.5 text-xs text-stone-600 focus:border-olive-500 focus:outline-none"
          >
            <option value="all">All statuses</option>
            <option value="shortlisted">Shortlisted</option>
            <option value="under_review">In review</option>
            <option value="pending">Pending</option>
          </select>

          <select
            value={qualityFilter}
            onChange={(e) => setQualityFilter(e.target.value)}
            className="rounded-lg border border-stone-200 bg-white py-1.5 px-2.5 text-xs text-stone-600 focus:border-olive-500 focus:outline-none"
          >
            <option value="all">All resume qualities</option>
            <option value="good">Good quality (75+)</option>
            <option value="moderate">Moderate quality (50–74)</option>
            <option value="poor">Poor quality (&lt;50)</option>
          </select>
        </div>

        <div className="text-xs text-stone-400 flex items-center gap-2 shrink-0">
          <span>
            Showing <strong className="text-stone-700">{filteredCandidates.length}</strong> of{" "}
            <strong className="text-stone-700">{total}</strong>
          </span>
          {selectedIds.length > 0 && (
            <span className="text-olive-700 font-medium">
              ({selectedIds.length} selected for comparison)
            </span>
          )}
        </div>
      </div>

      {/* ── Responsible Interpretation & Quality Distinction Notice ── */}
      <div className="bg-[#FAF9F6] border border-stone-300 rounded-xl p-4 text-xs text-stone-600 flex items-start gap-3 shadow-subtle">
        <div className="mt-0.5 rounded-lg p-1.5 bg-white border border-stone-300 text-olive-700 shrink-0">
          <FileText className="h-4 w-4" />
        </div>
        <div className="flex-1 leading-relaxed">
          <div className="flex flex-wrap items-center gap-x-2">
            <span className="font-semibold text-stone-900">
              Independent Resume Quality Assessment:
            </span>
            <span className="text-stone-600">
              Resume quality reflects how clearly and consistently the submitted resume communicates its information. It is strictly separate from the candidate&apos;s job-match score.
            </span>
          </div>
          <p className="text-stone-500 mt-1">
            <strong className="text-stone-900 font-medium">Resume quality is not candidate quality.</strong> A poorly formatted resume can belong to a highly qualified candidate, and a polished resume does not prove job suitability.
          </p>
        </div>
      </div>

      {/* ── Candidate Table ── */}
      <div className="bg-white border border-stone-300 rounded-2xl overflow-hidden shadow-subtle">
        {loading ? (
          <div className="py-20 text-center text-stone-400">
            <RotateCcw className="h-5 w-5 animate-spin mx-auto mb-2 text-olive-600" />
            <p className="text-xs">Loading candidates...</p>
          </div>
        ) : filteredCandidates.length === 0 ? (
          <div className="p-14 text-center">
            <FileText className="h-8 w-8 text-stone-300 mx-auto mb-3" />
            <p className="text-sm font-semibold text-stone-900">No candidates match your criteria</p>
            <p className="text-xs text-stone-500 mt-1 max-w-xs mx-auto">
              {candidates.length === 0
                ? "Upload resumes to begin evaluating candidates."
                : activeTab === "shortlisted"
                ? "No candidates shortlisted yet. Click the star icon to shortlist a candidate."
                : "Try clearing your search or filter selections."}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-stone-300 bg-[#FAF9F6] text-xs font-semibold text-stone-400 uppercase tracking-wider">
                  <th className="py-3 px-4 w-10">
                    <button
                      onClick={handleSelectAll}
                      className="text-stone-400 hover:text-stone-600"
                    >
                      {selectedIds.length === filteredCandidates.length && filteredCandidates.length > 0 ? (
                        <CheckSquare className="h-4 w-4 text-olive-700" />
                      ) : (
                        <Square className="h-4 w-4" />
                      )}
                    </button>
                  </th>
                  <th className="py-3 px-4 w-14">Rank</th>
                  <th className="py-3 px-4">Candidate</th>
                  <th className="py-3 px-4">Fit tier</th>
                  <th className="py-3 px-4 w-36">Match score</th>
                  <th className="py-3 px-4 w-44">Resume quality</th>
                  <th className="py-3 px-4">Flags</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-stone-200">
                {paginatedCandidates.map((cand, idx) => {
                  const candId = cand.id || cand.candidate_id || `cand-${idx}`;
                  const isSelected = selectedIds.includes(candId);
                  const rank = cand.rank;
                  const isShortlisted = (cand.review_status || "").toUpperCase() === "SHORTLISTED";
                  const hasScore = cand.overall_score !== null && cand.overall_score !== undefined;
                  const score = Math.round(cand.overall_score ?? 0);
                  const candName = cand.name || cand.original_filename || `Candidate #${rank || idx + 1}`;
                  const candTier =
                    cand.fit_tier ||
                    (hasScore
                      ? score >= 80
                        ? "Strong Match"
                        : score >= 60
                        ? "Potential Match"
                        : "Under Review"
                      : "Under Review");

                  return (
                    <tr
                      key={candId}
                      className={cn(
                        "transition-colors group",
                        isSelected
                          ? "bg-sage-100/60"
                          : "hover:bg-stone-50"
                      )}
                    >
                      <td className="py-3 px-4">
                        <button
                          onClick={() => handleToggleSelect(candId)}
                          className="text-stone-400 hover:text-stone-600"
                        >
                          {isSelected ? (
                            <CheckSquare className="h-4 w-4 text-olive-700" />
                          ) : (
                            <Square className="h-4 w-4" />
                          )}
                        </button>
                      </td>

                      <td className="py-3 px-4 font-mono text-xs text-stone-500">
                        {rank ? `#${rank}` : "—"}
                      </td>

                      <td className="py-3 px-4">
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => handleQuickShortlist(candId, cand.review_status)}
                            title={isShortlisted ? "Remove from shortlist" : "Add to shortlist"}
                            className="p-1 rounded transition-colors text-stone-300 hover:text-amber-500"
                          >
                            <Star
                              className={cn(
                                "h-4 w-4",
                                isShortlisted ? "fill-amber-400 text-amber-400" : ""
                              )}
                            />
                          </button>
                          <div>
                            <Link
                              href={`/candidates/${candId}?session=${sessionId}`}
                              className="font-medium text-stone-900 group-hover:text-olive-700 transition-colors block"
                            >
                              {candName}
                            </Link>
                            {cand.email && (
                              <span className="text-xs text-stone-400 block">{cand.email}</span>
                            )}
                          </div>
                        </div>
                      </td>

                      <td className="py-3 px-4">
                        <Badge tier={candTier}>{candTier}</Badge>
                      </td>

                      {/* Match Score Column */}
                      <td className="py-3 px-4">
                        {hasScore ? (
                          <div className="flex items-center gap-2">
                            <span className={cn("font-mono text-xs font-semibold", getScoreColor(score))}>
                              {score}%
                            </span>
                            <div className="w-16">
                              <ProgressBar value={score} size="sm" colorScheme="score" />
                            </div>
                          </div>
                        ) : (
                          <span className="text-xs text-stone-400">Pending</span>
                        )}
                      </td>

                      {/* Resume Quality Column */}
                      <td className="py-3 px-4">
                        {cand.resume_quality_score !== null && cand.resume_quality_score !== undefined ? (
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-xs font-semibold text-stone-700">
                              {Math.round(cand.resume_quality_score)}%
                            </span>
                            <span
                              className={cn(
                                "inline-flex items-center px-1.5 py-0.5 rounded text-2xs font-medium border",
                                (cand.resume_quality_label || "").toLowerCase().includes("good")
                                  ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                                  : (cand.resume_quality_label || "").toLowerCase().includes("moderate")
                                  ? "bg-amber-50 text-amber-800 border-amber-200"
                                  : "bg-rose-50 text-rose-800 border-rose-200"
                              )}
                            >
                              {(cand.resume_quality_label || "").replace(" Quality", "")}
                            </span>
                          </div>
                        ) : (
                          <span className="text-xs text-stone-400 font-mono">—</span>
                        )}
                      </td>

                      <td className="py-3 px-4">
                        <div className="flex flex-col gap-1 items-start">
                          {cand.conflicts_count && cand.conflicts_count > 0 ? (
                            <span className="inline-flex items-center gap-1 text-2xs font-medium text-terracotta-700 bg-terracotta-50 border border-terracotta-200 px-1.5 py-0.5 rounded">
                              <AlertTriangle className="h-3 w-3 text-terracotta-600" />
                              {cand.conflicts_count} flag{cand.conflicts_count > 1 ? "s" : ""}
                            </span>
                          ) : null}
                          {cand.missing_critical_count && cand.missing_critical_count > 0 ? (
                            <span className="inline-flex items-center gap-1 text-2xs font-medium text-stone-700 bg-stone-100 border border-stone-300 px-1.5 py-0.5 rounded">
                              <AlertCircle className="h-3 w-3 text-stone-500" />
                              Missing {cand.missing_critical_count} req
                            </span>
                          ) : !cand.conflicts_count && hasScore ? (
                            <span className="inline-flex items-center gap-1 text-xs text-olive-700 font-medium">
                              <Check className="h-3 w-3" />
                              All met
                            </span>
                          ) : (
                            <span className="text-xs text-stone-300">—</span>
                          )}
                        </div>
                      </td>

                      <td className="py-3 px-4">
                        <Badge status={cand.review_status}>{cand.review_status || "IN_REVIEW"}</Badge>
                      </td>

                      <td className="py-3 px-4 text-right">
                        <div className="flex items-center justify-end gap-1">
                          <Link href={`/candidates/${candId}?session=${sessionId}`}>
                            <Button variant="ghost" size="sm" rightIcon={<Eye className="h-3.5 w-3.5" />}>
                              View
                            </Button>
                          </Link>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* ── Pagination ── */}
        {filteredCandidates.length > 0 && (
          <div className="p-4 border-t border-stone-100 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-stone-500">
            <div className="flex items-center gap-2">
              <span>Show</span>
              <select
                value={pageSize}
                onChange={(e) => {
                  setPageSize(Number(e.target.value));
                  setPage(1);
                }}
                className="rounded border border-stone-200 bg-white py-1 px-2 text-xs text-stone-700 focus:outline-none"
              >
                <option value={10}>10</option>
                <option value={25}>25</option>
                <option value={50}>50</option>
                <option value={100}>100</option>
                <option value={1000}>All ({filteredCandidates.length})</option>
              </select>
              <span>per page</span>
            </div>

            {totalPages > 1 && (
              <div className="flex items-center gap-1">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  leftIcon={<ChevronLeft className="h-3.5 w-3.5" />}
                >
                  Previous
                </Button>
                <span className="font-mono text-stone-600 px-3">
                  {page} of {totalPages}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  rightIcon={<ChevronRight className="h-3.5 w-3.5" />}
                >
                  Next
                </Button>
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── Upload Resumes Modal ── */}
      <Modal
        isOpen={showUploadModal}
        onClose={() => {
          if (!isUploading) {
            setShowUploadModal(false);
            setUploadFiles([]);
          }
        }}
        title="Add Resumes"
        description="Upload additional resumes to this session. They will be parsed and evaluated automatically."
        size="md"
      >
        <div className="space-y-4">
          <div className="border-2 border-dashed border-stone-300 hover:border-olive-500 rounded-xl p-8 text-center transition-colors bg-stone-50">
            <Upload className="h-8 w-8 text-stone-400 mx-auto mb-2" />
            <p className="text-sm font-medium text-stone-700">Select PDF, DOCX, or TXT resumes</p>
            <p className="text-xs text-stone-400 mt-1 mb-3">You can upload multiple files at once</p>
            <input
              type="file"
              multiple
              accept=".pdf,.docx,.txt,.doc"
              onChange={(e) => {
                if (e.target.files) {
                  setUploadFiles(Array.from(e.target.files));
                }
              }}
              className="hidden"
              id="session-resume-upload"
            />
            <label htmlFor="session-resume-upload">
              <span className="inline-flex items-center justify-center font-medium rounded-lg text-xs h-8 px-3 bg-white border border-stone-300 text-stone-700 hover:bg-stone-50 cursor-pointer transition-colors">
                Browse files
              </span>
            </label>
          </div>

          {uploadFiles.length > 0 && (
            <div className="rounded-lg border border-stone-200 p-3 max-h-40 overflow-y-auto space-y-1.5 text-xs">
              <p className="font-medium text-stone-700 mb-2">
                {uploadFiles.length} file{uploadFiles.length > 1 ? "s" : ""} selected
              </p>
              {uploadFiles.map((f, i) => (
                <div key={i} className="flex justify-between text-stone-600">
                  <span className="truncate">{f.name}</span>
                  <span className="text-stone-400 font-mono">{(f.size / 1024).toFixed(0)} KB</span>
                </div>
              ))}
            </div>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setShowUploadModal(false);
                setUploadFiles([]);
              }}
            >
              Cancel
            </Button>
            <Button
              variant="primary"
              size="sm"
              isLoading={isUploading || isRerunning}
              disabled={uploadFiles.length === 0}
              onClick={handleUploadSubmit}
            >
              Upload & evaluate ({uploadFiles.length})
            </Button>
          </div>
        </div>
      </Modal>

      {/* ── Delete Confirmation Modal ── */}
      <Modal
        isOpen={showDeleteModal}
        onClose={() => setShowDeleteModal(false)}
        title="Delete Session"
        description="This action cannot be undone. All candidates, scores, and evaluation data for this session will be removed."
        size="sm"
      >
        <div className="flex justify-end gap-2 mt-4">
          <Button variant="outline" size="sm" onClick={() => setShowDeleteModal(false)}>
            Cancel
          </Button>
          <Button
            variant="danger"
            size="sm"
            isLoading={isDeleting}
            onClick={handleDeleteSession}
          >
            Delete session
          </Button>
        </div>
      </Modal>
    </div>
  );
}
