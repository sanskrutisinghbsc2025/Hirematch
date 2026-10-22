"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  ArrowLeft,
  BarChart3,
  FileDown,
  RotateCcw,
  Users,
  CheckCircle,
  AlertCircle,
} from "lucide-react";
import { apiClient } from "@/lib/api/client";
import { SessionAnalytics } from "@/lib/types/api";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/Card";
import { StatCard } from "@/components/ui/StatCard";
import { Button } from "@/components/ui/Button";
import { ProgressBar } from "@/components/ui/ProgressBar";

export default function SessionAnalyticsPage() {
  const params = useParams();
  const sessionId = params.sessionId as string;

  const [analytics, setAnalytics] = useState<SessionAnalytics | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchAnalytics = async () => {
      try {
        setLoading(true);
        const data = await apiClient.getSessionAnalytics(sessionId);
        setAnalytics(data);
      } catch (err: any) {
        console.error("Failed to load session analytics", err);
      } finally {
        setLoading(false);
      }
    };

    if (sessionId) fetchAnalytics();
  }, [sessionId]);

  const handleExport = () => {
    window.open(`/api/analytics/export?session_id=${sessionId}&format=json`, "_blank");
  };

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

        <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
          <div>
            <h1 className="text-xl font-semibold text-charcoal-900">Session analytics</h1>
            <p className="text-sm text-stone-500 mt-0.5">
              Score distributions, qualification rates, and candidate pipeline metrics.
            </p>
          </div>

          <Button
            variant="outline"
            size="sm"
            onClick={handleExport}
            leftIcon={<FileDown className="h-3.5 w-3.5 text-stone-400" />}
          >
            Export JSON
          </Button>
        </div>
      </div>

      {loading ? (
        <div className="py-20 text-center text-stone-400">
          <RotateCcw className="h-5 w-5 animate-spin mx-auto mb-2 text-olive-600" />
          <p className="text-sm">Calculating session metrics...</p>
        </div>
      ) : !analytics ? (
        <div className="p-12 text-center text-stone-400 text-sm">
          No analytics data available for this session yet.
        </div>
      ) : (
        <div className="space-y-6">
          {/* ── Top Metric Cards ── */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard
              title="Total Candidates"
              value={analytics.total_candidates}
              description="Evaluated in this session"
              icon={<Users className="h-4 w-4" />}
            />
            <StatCard
              title="Average Score"
              value={`${Math.round(analytics.average_score ?? 0)}%`}
              description="Mean composite score"
              icon={<BarChart3 className="h-4 w-4" />}
            />
            <StatCard
              title="Strong Matches"
              value={analytics.strong_matches ?? 0}
              description="Score ≥ 80%"
              icon={<CheckCircle className="h-4 w-4" />}
            />
            <StatCard
              title="Needs Review"
              value={analytics.under_review ?? 0}
              description="Score < 60%"
              icon={<AlertCircle className="h-4 w-4" />}
            />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            {/* ── Fit Tier Funnel ── */}
            <Card>
              <CardHeader className="pb-3 border-b border-stone-200">
                <CardTitle className="text-sm">Qualification breakdown</CardTitle>
                <CardDescription>Candidate distribution across suitability tiers</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4 pt-4">
                <div className="space-y-1.5">
                  <div className="flex justify-between text-xs">
                    <span className="font-medium text-olive-700">Strong match</span>
                    <span className="font-mono text-stone-600">
                      {analytics.strong_matches ?? 0} (
                      {analytics.total_candidates > 0
                        ? Math.round(
                            ((analytics.strong_matches ?? 0) / analytics.total_candidates) * 100
                          )
                        : 0}
                      %)
                    </span>
                  </div>
                  <ProgressBar
                    value={
                      analytics.total_candidates > 0
                        ? ((analytics.strong_matches ?? 0) / analytics.total_candidates) * 100
                        : 0
                    }
                    size="md"
                    colorScheme="emerald"
                  />
                </div>

                <div className="space-y-1.5">
                  <div className="flex justify-between text-xs">
                    <span className="font-medium text-olive-700">Potential match</span>
                    <span className="font-mono text-stone-600">
                      {analytics.potential_matches ?? 0} (
                      {analytics.total_candidates > 0
                        ? Math.round(
                            ((analytics.potential_matches ?? 0) / analytics.total_candidates) * 100
                          )
                        : 0}
                      %)
                    </span>
                  </div>
                  <ProgressBar
                    value={
                      analytics.total_candidates > 0
                        ? ((analytics.potential_matches ?? 0) / analytics.total_candidates) * 100
                        : 0
                    }
                    size="md"
                    colorScheme="blue"
                  />
                </div>

                <div className="space-y-1.5">
                  <div className="flex justify-between text-xs">
                    <span className="font-medium text-amber-700">Under review</span>
                    <span className="font-mono text-stone-600">
                      {analytics.under_review ?? 0} (
                      {analytics.total_candidates > 0
                        ? Math.round(
                            ((analytics.under_review ?? 0) / analytics.total_candidates) * 100
                          )
                        : 0}
                      %)
                    </span>
                  </div>
                  <ProgressBar
                    value={
                      analytics.total_candidates > 0
                        ? ((analytics.under_review ?? 0) / analytics.total_candidates) * 100
                        : 0
                    }
                    size="md"
                    colorScheme="amber"
                  />
                </div>
              </CardContent>
            </Card>

            {/* ── Score Distribution Breakdown ── */}
            <Card>
              <CardHeader className="pb-3 border-b border-stone-100">
                <CardTitle className="text-sm">Score distribution</CardTitle>
                <CardDescription>Histogram of composite scores across all candidates</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 pt-4">
                {analytics.score_histogram && analytics.score_histogram.length > 0 ? (
                  analytics.score_histogram.map((item) => {
                    const pct =
                      analytics.total_candidates > 0
                        ? (item.count / analytics.total_candidates) * 100
                        : 0;
                    return (
                      <div key={item.range} className="space-y-1">
                        <div className="flex justify-between text-xs">
                          <span className="font-mono text-stone-600">{item.range}%</span>
                          <span className="font-mono text-stone-400">
                            {item.count} ({Math.round(pct)}%)
                          </span>
                        </div>
                        <ProgressBar value={pct} size="sm" colorScheme="blue" />
                      </div>
                    );
                  })
                ) : (
                  <p className="text-xs text-stone-400 text-center py-4">
                    Score distribution data not available.
                  </p>
                )}
              </CardContent>
            </Card>
          </div>

          {/* ── Recruitment Funnel Section ── */}
          {analytics.funnel_metrics && analytics.funnel_metrics.length > 0 && (
            <Card>
              <CardHeader className="pb-3 border-b border-stone-100">
                <CardTitle className="text-sm">Pipeline progression</CardTitle>
                <CardDescription>
                  Conversion and drop-off through each candidate stage
                </CardDescription>
              </CardHeader>
              <CardContent className="pt-4">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  {analytics.funnel_metrics.map((stage, idx) => (
                    <div
                      key={idx}
                      className="rounded-lg border border-stone-200 p-4 space-y-2 bg-stone-50"
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-stone-600 uppercase tracking-wide">
                          Stage {idx + 1}: {stage.stage_name}
                        </span>
                        <span className="text-sm font-semibold font-mono text-charcoal-900">
                          {stage.count}
                        </span>
                      </div>
                      <div className="text-xs text-stone-500 flex justify-between">
                        <span>Conversion:</span>
                        <span className="font-semibold text-olive-700">
                          {Math.round(stage.conversion_rate * 100)}%
                        </span>
                      </div>
                      {stage.dropoff_rate > 0 && (
                        <div className="text-xs text-stone-500 flex justify-between">
                          <span>Drop-off:</span>
                          <span className="font-semibold text-terracotta-700">
                            {Math.round(stage.dropoff_rate * 100)}%
                          </span>
                        </div>
                      )}
                      <ProgressBar
                        value={stage.conversion_rate * 100}
                        size="sm"
                        colorScheme={idx === 2 ? "emerald" : "blue"}
                      />
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* ── Skill Coverage & Gap Analysis ── */}
          {analytics.skill_coverage && analytics.skill_coverage.length > 0 && (
            <Card>
              <CardHeader className="pb-3 border-b border-stone-200">
                <CardTitle className="text-sm">Skill coverage</CardTitle>
                <CardDescription>
                  Applicant pool coverage across requirements and criteria
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 pt-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {analytics.skill_coverage.map((skill, idx) => {
                    const isAcute = skill.gap_status === "ACUTE_GAP";
                    return (
                      <div
                        key={idx}
                        className="rounded-lg border border-stone-200 p-3 space-y-1.5"
                      >
                        <div className="flex items-center justify-between text-xs">
                          <span className="font-semibold text-stone-900">
                            {skill.canonical_name}
                          </span>
                          <span
                            className={`px-2 py-0.5 rounded text-2xs font-medium border ${
                              isAcute
                                ? "bg-terracotta-50 text-terracotta-700 border-terracotta-200"
                                : "bg-olive-50 text-olive-800 border-olive-200"
                            }`}
                          >
                            {isAcute ? "Low coverage" : "Good coverage"}
                          </span>
                        </div>
                        <div className="flex justify-between text-2xs text-stone-400">
                          <span>{Math.round(skill.pool_coverage_percentage)}% of pool</span>
                          <span>{skill.candidate_evidence_count} matched</span>
                        </div>
                        <ProgressBar
                          value={skill.pool_coverage_percentage}
                          size="sm"
                          colorScheme={isAcute ? "amber" : "emerald"}
                        />
                      </div>
                    );
                  })}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
