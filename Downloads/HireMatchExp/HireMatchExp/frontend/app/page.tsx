"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  Users,
  Layers,
  Award,
  Cpu,
  ArrowRight,
  PlusCircle,
  Loader2,
  FileText,
  CheckCircle,
  BarChart2,
  SlidersHorizontal,
  Sparkles,
} from "lucide-react";
import { apiClient } from "@/lib/api/client";
import { ScreeningSession, PortfolioOverview } from "@/lib/types/api";
import { StatCard } from "@/components/ui/StatCard";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { formatDate, cn } from "@/lib/utils";
import { MotionHeroBanner } from "@/components/motion/MotionHeroBanner";
import { PipelineVisualizer } from "@/components/motion/PipelineVisualizer";
import { LiveScoreDistribution } from "@/components/analytics/LiveScoreDistribution";
import { DecoupledQualityMatrix } from "@/components/analytics/DecoupledQualityMatrix";
import { PlatformWalkthroughModal } from "@/components/motion/PlatformWalkthroughModal";

export default function DashboardPage() {
  const [sessions, setSessions] = useState<ScreeningSession[]>([]);
  const [overview, setOverview] = useState<PortfolioOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showWalkthrough, setShowWalkthrough] = useState(false);

  useEffect(() => {
    let mounted = true;

    const fetchDashboard = async (isInitial = false) => {
      try {
        if (isInitial) setLoading(true);
        const [sessRes, overRes] = await Promise.all([
          apiClient.getSessions(1, 10),
          apiClient.getPortfolioOverview().catch(() => null),
        ]);
        if (mounted) {
          setSessions(sessRes.items);
          if (overRes) setOverview(overRes);
        }
      } catch (err: any) {
        if (mounted && isInitial) setError(err.message || "Failed to load dashboard data");
      } finally {
        if (mounted && isInitial) setLoading(false);
      }
    };

    // Initial load
    fetchDashboard(true);

    // Auto-refresh every 5 seconds for real-time updates
    const interval = setInterval(() => {
      fetchDashboard(false);
    }, 5000);

    // Refresh immediately when tab gains focus
    const onFocus = () => fetchDashboard(false);
    window.addEventListener("focus", onFocus);
    document.addEventListener("visibilitychange", onFocus);

    return () => {
      mounted = false;
      clearInterval(interval);
      window.removeEventListener("focus", onFocus);
      document.removeEventListener("visibilitychange", onFocus);
    };
  }, []);

  const totalCandidates =
    overview?.total_candidates ??
    overview?.total_resumes ??
    sessions.reduce((acc, s) => acc + (s.candidate_count ?? 0), 0);

  const avgScore =
    overview?.avg_composite_score !== undefined && overview?.avg_composite_score !== null
      ? Math.round(overview.avg_composite_score)
      : 0;

  const strongCount = overview?.strong_matches_count ?? 0;

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      {/* Application Title Header with Live Cursor-Based Background Graphics */}
      <MotionHeroBanner
        title="HireMatch"
        subtitle="Clear, unbiased resume screening. You stay in full control of every hiring decision."
        onOpenDemo={() => setShowWalkthrough(true)}
      />

      {/* KPI Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Active Sessions"
          value={overview?.total_sessions ?? sessions.length}
          description="Total screening sessions managed"
          icon={<Layers className="h-4 w-4" />}
        />
        <StatCard
          title="Candidates Reviewed"
          value={totalCandidates}
          description="Resumes parsed and evaluated"
          icon={<Users className="h-4 w-4" />}
        />
        <StatCard
          title="Average Match Score"
          value={`${avgScore}%`}
          description={
            strongCount > 0
              ? `${strongCount} strong matches (≥80%)`
              : "Across active requisition cohorts"
          }
          icon={<Award className="h-4 w-4" />}
        />
        <StatCard
          title="Analysis Model"
          value="MiniLM-L6-v2"
          description="Sentence transformer embeddings"
          icon={<Cpu className="h-4 w-4" />}
        />
      </div>

      {/* Real-time Interactive Graphics (Score Distribution & Decoupled Quality Matrix) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <LiveScoreDistribution
          totalCandidates={totalCandidates}
          avgScore={avgScore}
          strongMatchesCount={strongCount}
          sessionCount={overview?.total_sessions ?? sessions.length}
        />

        <DecoupledQualityMatrix totalCandidates={totalCandidates} />
      </div>

      {/* Recent Screening Requisitions Manifest */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle>Recent Screening Sessions</CardTitle>
            <CardDescription>
              Your latest screening requisitions, candidate pools, and completion status.
            </CardDescription>
          </div>
          <Link href="/screenings">
            <Button variant="ghost" size="sm" rightIcon={<ArrowRight className="h-3.5 w-3.5" />}>
              View all sessions
            </Button>
          </Link>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="py-12 flex flex-col items-center gap-2 text-stone-400">
              <Loader2 className="h-5 w-5 animate-spin" />
              <span className="text-xs">Loading sessions…</span>
            </div>
          ) : error ? (
            <div className="py-10 text-center">
              <p className="text-sm text-stone-500">{error}</p>
            </div>
          ) : sessions.length === 0 ? (
            <div className="rounded-xl border border-dashed border-stone-300 py-14 text-center bg-stone-50/60">
              <FileText className="h-8 w-8 text-stone-300 mx-auto mb-3" />
              <h3 className="text-sm font-medium text-stone-900">
                No screening sessions yet
              </h3>
              <p className="text-xs text-stone-500 mt-1 max-w-xs mx-auto">
                Create your first screening session to start uploading resumes and evaluating candidates.
              </p>
              <div className="mt-5">
                <Link href="/screenings/new">
                  <Button
                    variant="primary"
                    size="sm"
                    leftIcon={<PlusCircle className="h-4 w-4" />}
                  >
                    Create a screening
                  </Button>
                </Link>
              </div>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-stone-300">
                    <th className="py-3 px-4 text-[11px] font-semibold text-stone-400 uppercase tracking-wider">
                      Requisition / Role
                    </th>
                    <th className="py-3 px-4 text-[11px] font-semibold text-stone-400 uppercase tracking-wider">
                      Status
                    </th>
                    <th className="py-3 px-4 text-[11px] font-semibold text-stone-400 uppercase tracking-wider">
                      Candidates
                    </th>
                    <th className="py-3 px-4 text-[11px] font-semibold text-stone-400 uppercase tracking-wider">
                      Created
                    </th>
                    <th className="py-3 px-4 text-right text-[11px] font-semibold text-stone-400 uppercase tracking-wider">
                      Action
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-200">
                  {sessions.map((sess) => (
                    <tr
                      key={sess.id}
                      className="hover:bg-[#FAF9F6] transition-colors group"
                    >
                      <td className="py-3.5 px-4">
                        <Link
                          href={`/screenings/${sess.id}`}
                          className="text-sm font-medium text-stone-900 group-hover:text-olive-700 transition-colors"
                        >
                          {(sess as any).session_name ||
                            (sess as any).job_title ||
                            sess.title ||
                            sess.name ||
                            "Screening Session"}
                        </Link>
                        {sess.department && (
                          <div className="text-xs text-stone-400 font-normal mt-0.5">
                            {sess.department}
                          </div>
                        )}
                      </td>
                      <td className="py-3.5 px-4">
                        <Badge status={sess.status}>{sess.status}</Badge>
                      </td>
                      <td className="py-3.5 px-4 text-sm text-stone-600 font-mono tabular-nums">
                        {sess.candidate_count ?? sess.resume_count ?? 0}
                      </td>
                      <td className="py-3.5 px-4 text-xs text-stone-400">
                        {formatDate(sess.created_at)}
                      </td>
                      <td className="py-3.5 px-4 text-right">
                        <Link href={`/screenings/${sess.id}`}>
                          <Button
                            variant="ghost"
                            size="sm"
                            rightIcon={<ArrowRight className="h-3 w-3" />}
                          >
                            Open
                          </Button>
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Feature Highlights with Warm Ivory Borders */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        <div className="rounded-xl border border-stone-300 bg-white p-5 space-y-2 shadow-subtle hover:border-stone-400 transition-all">
          <div className="flex items-center gap-2">
            <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-olive-50 border border-olive-200 text-olive-700">
              <CheckCircle className="h-3.5 w-3.5" />
            </span>
            <h3 className="text-sm font-semibold text-stone-900">Evidence-Backed Scoring</h3>
          </div>
          <p className="text-xs text-stone-500 leading-relaxed">
            Each score links to specific sentences from the applicant&apos;s resume, allowing recruiters to inspect the verbatim citation directly.
          </p>
        </div>

        <div className="rounded-xl border border-stone-300 bg-white p-5 space-y-2 shadow-subtle hover:border-stone-400 transition-all">
          <div className="flex items-center gap-2">
            <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-sage-100 border border-olive-200 text-olive-800">
              <FileText className="h-3.5 w-3.5" />
            </span>
            <h3 className="text-sm font-semibold text-stone-900">Transparent Criteria</h3>
          </div>
          <p className="text-xs text-stone-500 leading-relaxed">
            Clear section breakdown showing exact requirements, aliases, and semantic similarity tiers without opaque black-box scoring.
          </p>
        </div>

        <div className="rounded-xl border border-stone-300 bg-white p-5 space-y-2 shadow-subtle hover:border-stone-400 transition-all">
          <div className="flex items-center gap-2">
            <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-stone-100 border border-stone-300 text-stone-600">
              <SlidersHorizontal className="h-3.5 w-3.5" />
            </span>
            <h3 className="text-sm font-semibold text-stone-900">Sensitivity Controls</h3>
          </div>
          <p className="text-xs text-stone-500 leading-relaxed">
            Adjust requirement weights and score thresholds in real time to simulate how candidate rankings shift without re-running models.
          </p>
        </div>
      </div>

      {/* Interactive Platform Tour / Demo Modal */}
      <PlatformWalkthroughModal
        isOpen={showWalkthrough}
        onClose={() => setShowWalkthrough(false)}
      />
    </div>
  );
}
