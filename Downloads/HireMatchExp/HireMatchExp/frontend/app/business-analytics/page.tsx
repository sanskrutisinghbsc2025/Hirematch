"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  LineChart,
  Cpu,
  BarChart3,
  Layers,
  Sparkles,
  TrendingUp,
  AlertTriangle,
  CheckCircle,
  FileSpreadsheet,
  FileText,
  RotateCcw,
  Play,
  CheckCircle2,
  XCircle,
  Info,
  Sliders,
  Award,
  Zap,
  HardDrive,
  Database,
  ArrowRight,
  ShieldAlert,
  Search,
} from "lucide-react";
import { apiClient } from "@/lib/api/client";
import { PortfolioOverview, ScreeningSession } from "@/lib/types/api";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/Card";
import { StatCard } from "@/components/ui/StatCard";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { formatDate } from "@/lib/utils";

export default function BusinessAnalyticsPage() {
  const [activeTab, setActiveTab] = useState<"pretrained" | "models" | "portfolio" | "skills" | "variance" | "insights">("pretrained");
  const [loading, setLoading] = useState(true);

  // Core Data
  const [overview, setOverview] = useState<PortfolioOverview | null>(null);
  const [sessions, setSessions] = useState<ScreeningSession[]>([]);
  const [models, setModels] = useState<any[]>([]);
  const [benchmarks, setBenchmarks] = useState<any[]>([]);
  const [datasets, setDatasets] = useState<any[]>([]);

  // Pre-Trained Models Tab Filtering & Sorting State
  const [pretrainedFilterType, setPretrainedFilterType] = useState<string>("ALL");
  const [pretrainedSearchQuery, setPretrainedSearchQuery] = useState<string>("");
  const [pretrainedSortBy, setPretrainedSortBy] = useState<"ndcg" | "mrr" | "f1" | "name">("ndcg");

  // Selected Session for Deep-Dive Tabs (Skills & Variance)
  const [selectedSessionId, setSelectedSessionId] = useState<string>("");
  const [sessionAnalytics, setSessionAnalytics] = useState<any | null>(null);
  const [criterionAnalytics, setCriterionAnalytics] = useState<any[]>([]);
  const [skillCoverage, setSkillCoverage] = useState<any[]>([]);
  const [loadingSessionData, setLoadingSessionData] = useState(false);

  // AI Model Scoring & Architecture State
  const [selectedBenchmarkRun, setSelectedBenchmarkRun] = useState<any | null>(null);
  const [runningBenchmark, setRunningBenchmark] = useState(false);
  const [showBenchmarkModal, setShowBenchmarkModal] = useState(false);
  const [benchmarkModels, setBenchmarkModels] = useState<string[]>([
    "sentence-transformers/all-MiniLM-L6-v2",
    "mock-deterministic-embedding",
  ]);
  const [benchmarkDataset, setBenchmarkDataset] = useState<string>("synthetic-benchmark-v1");
  const [modelActionMsg, setModelActionMsg] = useState<string | null>(null);

  // Initial Load
  const fetchCoreData = async () => {
    try {
      setLoading(true);
      const [overRes, sessRes, modelsRes, benchRes, dataRes] = await Promise.all([
        apiClient.getPortfolioOverview().catch(() => null),
        apiClient.getSessions(1, 50).catch(() => ({ items: [], total: 0 })),
        apiClient.getModels().catch(() => []),
        apiClient.getBenchmarks().catch(() => []),
        apiClient.getDatasets().catch(() => []),
      ]);

      setOverview(overRes);
      const sessionList = sessRes?.items || [];
      setSessions(sessionList);
      setModels(Array.isArray(modelsRes) ? modelsRes : []);
      const benchList = Array.isArray(benchRes) ? benchRes : [];
      setBenchmarks(benchList);
      if (benchList.length > 0 && !selectedBenchmarkRun) {
        setSelectedBenchmarkRun(benchList[0]);
      }
      setDatasets(Array.isArray(dataRes) ? dataRes : []);

      if (sessionList.length > 0 && !selectedSessionId) {
        setSelectedSessionId(sessionList[0].id);
      }
    } catch (err: any) {
      console.error("Failed to load business analytics core data:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCoreData();
  }, []);

  // Fetch session-specific deep dive data when selectedSessionId changes
  useEffect(() => {
    if (!selectedSessionId) return;

    let mounted = true;
    const fetchSessionData = async () => {
      try {
        setLoadingSessionData(true);
        const [critRes, skillRes, sessAnalyticsRes] = await Promise.all([
          apiClient.getCriterionAnalytics(selectedSessionId).catch(() => []),
          apiClient.getSkillCoverage(selectedSessionId).catch(() => []),
          apiClient.getSessionAnalytics(selectedSessionId).catch(() => null),
        ]);

        if (mounted) {
          setCriterionAnalytics(Array.isArray(critRes) ? critRes : []);
          setSkillCoverage(Array.isArray(skillRes) ? skillRes : []);
          setSessionAnalytics(sessAnalyticsRes);
        }
      } catch (err) {
        console.error("Failed to load session analytics data:", err);
      } finally {
        if (mounted) setLoadingSessionData(false);
      }
    };

    fetchSessionData();
    return () => {
      mounted = false;
    };
  }, [selectedSessionId]);

  // Run Benchmark Experiment
  const handleExecuteBenchmark = async () => {
    if (benchmarkModels.length < 1) {
      alert("Please select at least one model to benchmark.");
      return;
    }

    try {
      setRunningBenchmark(true);
      const newRun = await apiClient.runBenchmarkExperiment({
        run_name: `Benchmark-${new Date().toISOString().slice(11, 19)}`,
        models: benchmarkModels,
        dataset_id: benchmarkDataset,
      });

      const updated = await apiClient.getBenchmarks();
      setBenchmarks(updated);
      setSelectedBenchmarkRun(newRun);
      setShowBenchmarkModal(false);
      setModelActionMsg(`Benchmark '${newRun.run_name}' completed successfully!`);
      setTimeout(() => setModelActionMsg(null), 4000);
    } catch (err: any) {
      alert("Failed to execute benchmark: " + err.message);
    } finally {
      setRunningBenchmark(false);
    }
  };

  // Model Memory Management
  const handleLoadModel = async (modelId: string) => {
    try {
      setModelActionMsg(`Loading model '${modelId}' into memory...`);
      await apiClient.loadLabModel(modelId);
      const updatedModels = await apiClient.getModels();
      setModels(updatedModels);
      setModelActionMsg(`Model '${modelId}' loaded into memory.`);
      setTimeout(() => setModelActionMsg(null), 3000);
    } catch (err: any) {
      alert("Failed to load model: " + err.message);
      setModelActionMsg(null);
    }
  };

  const handleUnloadModel = async (modelId: string) => {
    try {
      setModelActionMsg(`Unloading model '${modelId}'...`);
      await apiClient.unloadLabModel(modelId);
      const updatedModels = await apiClient.getModels();
      setModels(updatedModels);
      setModelActionMsg(`Model '${modelId}' unloaded.`);
      setTimeout(() => setModelActionMsg(null), 3000);
    } catch (err: any) {
      alert("Failed to unload model: " + err.message);
      setModelActionMsg(null);
    }
  };

  const handleClearCache = async () => {
    try {
      setModelActionMsg("Purging all model memory cache...");
      await apiClient.clearModelCache();
      const updatedModels = await apiClient.getModels();
      setModels(updatedModels);
      setModelActionMsg("All models cleared from memory cache.");
      setTimeout(() => setModelActionMsg(null), 3000);
    } catch (err: any) {
      alert("Failed to clear cache: " + err.message);
      setModelActionMsg(null);
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-2 border-b border-stone-200">
        <div>
          <h1 className="text-xl font-semibold text-charcoal-900">Business Analytics</h1>
          <p className="text-xs text-stone-500 mt-1">
            Cross-requisition trends, model benchmarking, talent pool gaps, and candidate insights.
          </p>
        </div>

        {/* Global Toolbar */}
        <div className="flex flex-wrap items-center gap-2.5">
          <Button
            variant="outline"
            size="sm"
            onClick={() => window.open("http://127.0.0.1:8000/api/analytics/export?format=xlsx", "_blank")}
            leftIcon={<FileSpreadsheet className="h-4 w-4 text-olive-700" />}
          >
            Export Excel (.xlsx)
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={() => window.open("http://127.0.0.1:8000/api/analytics/export?format=csv", "_blank")}
            leftIcon={<FileText className="h-4 w-4 text-olive-700" />}
          >
            Export CSV
          </Button>

          <Button
            variant="primary"
            size="sm"
            onClick={() => setShowBenchmarkModal(true)}
            leftIcon={<Zap className="h-4 w-4 text-amber-300" />}
          >
            Run Model Benchmark
          </Button>
        </div>
      </div>

      {/* Action Notification Toast */}
      {modelActionMsg && (
        <div className="rounded-lg border border-olive-200 bg-olive-50 px-4 py-2.5 text-xs text-stone-700 flex items-center justify-between animate-fadeIn">
          <div className="flex items-center gap-2">
            <Info className="h-4 w-4 text-olive-700 shrink-0" />
            <span>{modelActionMsg}</span>
          </div>
          <button onClick={() => setModelActionMsg(null)} className="text-stone-400 hover:text-stone-700">
            &times;
          </button>
        </div>
      )}

      {/* Primary KPI Ribbon */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Active Requisitions"
          value={overview?.total_sessions ?? sessions.length}
          description="Managed screening campaigns"
          icon={<Layers className="h-4 w-4" />}
          accentColor="blue"
        />
        <StatCard
          title="Total Candidates"
          value={overview?.total_candidates ?? overview?.total_resumes ?? 0}
          description="Parsed, validated & indexed"
          icon={<BarChart3 className="h-4 w-4" />}
          accentColor="emerald"
        />
        <StatCard
          title="Average Match Score"
          value={overview?.avg_composite_score !== undefined ? `${Math.round(overview.avg_composite_score)}%` : "0%"}
          description={
            overview?.strong_matches_count
              ? `${overview.strong_matches_count} strong matches (≥80%)`
              : "Overall candidate qualification"
          }
          icon={<Award className="h-4 w-4" />}
          accentColor="violet"
        />
        <StatCard
          title="Registered AI Models"
          value={models.length || 9}
          description="Dense, reranker & linguistic models"
          icon={<Cpu className="h-4 w-4" />}
          accentColor="amber"
        />
      </div>

      {/* Interactive Tabs Navigation */}
      <div className="flex flex-wrap items-center gap-1.5 border-b border-stone-300 pb-2">
        <button
          onClick={() => setActiveTab("pretrained")}
          className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-xs font-semibold transition-all ${
            activeTab === "pretrained"
              ? "bg-olive-50 text-olive-800 font-medium border border-olive-200"
              : "text-stone-600 hover:text-stone-900 hover:bg-stone-100"
          }`}
        >
          <Award className="h-3.5 w-3.5" />
          Pre-Trained Ground Truth Benchmarks ({models.length})
        </button>

        <button
          onClick={() => setActiveTab("models")}
          className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-xs font-semibold transition-all ${
            activeTab === "models"
              ? "bg-olive-50 text-olive-800 font-medium border border-olive-200"
              : "text-stone-600 hover:text-stone-900 hover:bg-stone-100"
          }`}
        >
          <Cpu className="h-3.5 w-3.5" />
          Model Laboratory ({benchmarks.length})
        </button>

        <button
          onClick={() => setActiveTab("portfolio")}
          className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-xs font-semibold transition-all ${
            activeTab === "portfolio"
              ? "bg-olive-50 text-olive-800 font-medium border border-olive-200"
              : "text-stone-600 hover:text-stone-900 hover:bg-stone-100"
          }`}
        >
          <TrendingUp className="h-3.5 w-3.5" />
          Portfolio Trends
        </button>

        <button
          onClick={() => setActiveTab("skills")}
          className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-xs font-semibold transition-all ${
            activeTab === "skills"
              ? "bg-olive-50 text-olive-800 font-medium border border-olive-200"
              : "text-stone-600 hover:text-stone-900 hover:bg-stone-100"
          }`}
        >
          <Sliders className="h-3.5 w-3.5" />
          Skill Coverage & Gaps
        </button>

        <button
          onClick={() => setActiveTab("variance")}
          className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-xs font-semibold transition-all ${
            activeTab === "variance"
              ? "bg-olive-50 text-olive-800 font-medium border border-olive-200"
              : "text-stone-600 hover:text-stone-900 hover:bg-stone-100"
          }`}
        >
          <Sparkles className="h-3.5 w-3.5" />
          Criteria Variance
        </button>

        <button
          onClick={() => setActiveTab("insights")}
          className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-xs font-semibold transition-all ${
            activeTab === "insights"
              ? "bg-olive-50 text-olive-800 font-medium border border-olive-200"
              : "text-stone-600 hover:text-stone-900 hover:bg-stone-100"
          }`}
        >
          <CheckCircle className="h-3.5 w-3.5" />
          Talent Insights
        </button>
      </div>

      {/* Loading Indicator */}
      {loading && (
        <div className="py-20 text-center text-stone-500">
          <RotateCcw className="h-8 w-8 animate-spin mx-auto mb-3 text-olive-600" />
          Loading advanced business analytics and model telemetry...
        </div>
      )}

      {/* ------------------------------------------------------------- */}
      {/* TAB 0: PRE-TRAINED GROUND TRUTH BENCHMARKS & METRICS */}
      {/* ------------------------------------------------------------- */}
      {!loading && activeTab === "pretrained" && (
        <div className="space-y-6">
          {/* Header Banner & Explanation */}
          <div className="rounded-xl border border-stone-300 bg-white p-5 space-y-4">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div>
                <h2 className="text-base font-semibold text-stone-900 flex items-center gap-2">
                  <Award className="h-4 w-4 text-olive-700" />
                  Pre-Trained Model Ranking & Quality Metrics (Ground Truth)
                </h2>
                <p className="text-xs text-stone-500 mt-1">
                  Baseline information retrieval, ranking quality, and classification accuracy metrics measured against standardized, labeled public evaluation datasets (MTEB, BEIR, MS MARCO, OntoNotes).
                </p>
              </div>

              <div className="flex items-center gap-2 text-xs bg-olive-50 text-olive-800 border border-olive-200 px-3 py-1.5 rounded-lg">
                <Info className="h-4 w-4 text-olive-700 shrink-0" />
                <span>Pre-trained benchmarks independent of local screening pools</span>
              </div>
            </div>

            {/* Metric Definition Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 pt-2 border-t border-stone-100">
              <div className="bg-stone-50/70 border border-stone-200 rounded-lg p-3">
                <div className="text-xs font-bold text-charcoal-900 flex items-center justify-between">
                  <span>NDCG@K</span>
                  <Badge variant="info" size="sm">Ranking Quality</Badge>
                </div>
                <div className="text-[11px] text-stone-600 mt-1">
                  <strong>Normalized Discounted Cumulative Gain:</strong> Evaluates ranking quality of candidate matches. Rewards placing highly qualified matches at the top with logarithmic rank discounting.
                </div>
              </div>

              <div className="bg-stone-50/70 border border-stone-200 rounded-lg p-3">
                <div className="text-xs font-bold text-charcoal-900 flex items-center justify-between">
                  <span>MRR (Mean Reciprocal Rank)</span>
                  <Badge variant="info" size="sm">First Match Position</Badge>
                </div>
                <div className="text-[11px] text-stone-600 mt-1">
                  <strong>Mean Reciprocal Rank:</strong> Measures how early the very first relevant candidate appears in the ranked candidate shortlist (1/Rank). Higher indicates faster relevant discovery.
                </div>
              </div>

              <div className="bg-stone-50/70 border border-stone-200 rounded-lg p-3">
                <div className="text-xs font-bold text-charcoal-900 flex items-center justify-between">
                  <span>Precision@K & Recall@K</span>
                  <Badge variant="info" size="sm">Relevance & Coverage</Badge>
                </div>
                <div className="text-[11px] text-stone-600 mt-1">
                  <strong>Precision@K:</strong> Ratio of relevant items in the top-K shortlist.<br />
                  <strong>Recall@K:</strong> Ratio of all available qualified candidates successfully retrieved.
                </div>
              </div>

              <div className="bg-stone-50/70 border border-stone-200 rounded-lg p-3">
                <div className="text-xs font-bold text-charcoal-900 flex items-center justify-between">
                  <span>F1-Score</span>
                  <Badge variant="info" size="sm">Classification Accuracy</Badge>
                </div>
                <div className="text-[11px] text-stone-600 mt-1">
                  <strong>F1-Score:</strong> Harmonic mean of Precision and Recall. Evaluates binary qualification classification accuracy against human-reviewed ground truth rubrics.
                </div>
              </div>
            </div>
          </div>

          {/* Filter & Search Bar */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-stone-50 border border-stone-200 p-4 rounded-xl">
            <div className="flex flex-wrap items-center gap-2">
              <div className="relative">
                <Search className="h-3.5 w-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-stone-400" />
                <input
                  type="text"
                  placeholder="Search model or benchmark..."
                  value={pretrainedSearchQuery}
                  onChange={(e) => setPretrainedSearchQuery(e.target.value)}
                  className="rounded-lg border border-stone-200 bg-white pl-8 pr-3 py-1.5 text-xs text-stone-800 placeholder-stone-400 focus:border-olive-500 focus:outline-none w-56"
                />
              </div>

              <div className="flex items-center gap-1 bg-white border border-stone-200 rounded-lg p-0.5 text-xs">
                {(["ALL", "EMBEDDING", "RERANKER", "KEYWORD", "NER"] as const).map((t) => (
                  <button
                    key={t}
                    onClick={() => setPretrainedFilterType(t)}
                    className={`px-2.5 py-1 rounded-md font-medium transition-colors ${
                      pretrainedFilterType === t
                        ? "bg-charcoal-900 text-white shadow-xs"
                        : "text-stone-600 hover:text-charcoal-900 hover:bg-stone-100"
                    }`}
                  >
                    {t === "ALL" ? "All Models" : t}
                  </button>
                ))}
              </div>
            </div>

            <div className="flex items-center gap-2 text-xs">
              <span className="text-stone-500 font-medium">Sort by:</span>
              <select
                value={pretrainedSortBy}
                onChange={(e: any) => setPretrainedSortBy(e.target.value)}
                className="rounded-lg border border-stone-200 bg-white px-2.5 py-1.5 text-xs text-stone-800 focus:border-olive-500 focus:outline-none"
              >
                <option value="ndcg">Highest NDCG@10 (Ranking Quality)</option>
                <option value="mrr">Highest MRR (First Hit Speed)</option>
                <option value="f1">Highest F1-Score (Rubric Accuracy)</option>
                <option value="name">Model Name (A-Z)</option>
              </select>
            </div>
          </div>

          {/* Pre-Trained Benchmark Comparison Table */}
          <Card>
            <CardHeader className="pb-3 border-b border-stone-100">
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-sm">Pre-Trained Models Ground Truth Leaderboard</CardTitle>
                  <CardDescription className="text-xs">
                    Standardized information retrieval and ranking metrics published by model creators and MTEB / BEIR benchmarks
                  </CardDescription>
                </div>
                <div className="text-xs text-stone-500 font-mono">
                  Showing {models.filter((m) => {
                    if (pretrainedFilterType !== "ALL" && m.model_type !== pretrainedFilterType) return false;
                    if (pretrainedSearchQuery) {
                      const q = pretrainedSearchQuery.toLowerCase();
                      return (
                        m.display_name?.toLowerCase().includes(q) ||
                        m.model_id?.toLowerCase().includes(q) ||
                        m.pretrained_metrics?.benchmark_source?.toLowerCase().includes(q)
                      );
                    }
                    return true;
                  }).length} of {models.length} registered models
                </div>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-stone-200 bg-stone-50 text-stone-500 font-semibold uppercase tracking-wider">
                      <th className="py-3 px-4">Model & Architecture</th>
                      <th className="py-3 px-4">Benchmark Source</th>
                      <th className="py-3 px-4">NDCG@10</th>
                      <th className="py-3 px-4">MRR</th>
                      <th className="py-3 px-4">Precision@10</th>
                      <th className="py-3 px-4">Recall@10</th>
                      <th className="py-3 px-4">F1-Score</th>
                      <th className="py-3 px-4">Specs</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-stone-100">
                    {models
                      .filter((m) => {
                        if (pretrainedFilterType !== "ALL" && m.model_type !== pretrainedFilterType) return false;
                        if (pretrainedSearchQuery) {
                          const q = pretrainedSearchQuery.toLowerCase();
                          return (
                            m.display_name?.toLowerCase().includes(q) ||
                            m.model_id?.toLowerCase().includes(q) ||
                            m.pretrained_metrics?.benchmark_source?.toLowerCase().includes(q)
                          );
                        }
                        return true;
                      })
                      .sort((a, b) => {
                        const aMet = a.pretrained_metrics;
                        const bMet = b.pretrained_metrics;
                        if (pretrainedSortBy === "ndcg") {
                          return (bMet?.ndcg_at_k ?? -1) - (aMet?.ndcg_at_k ?? -1);
                        }
                        if (pretrainedSortBy === "mrr") {
                          return (bMet?.mrr ?? -1) - (aMet?.mrr ?? -1);
                        }
                        if (pretrainedSortBy === "f1") {
                          return (bMet?.f1_score ?? -1) - (aMet?.f1_score ?? -1);
                        }
                        return (a.display_name || "").localeCompare(b.display_name || "");
                      })
                      .map((m) => {
                        const pm = m.pretrained_metrics;
                        return (
                          <tr key={m.model_id} className="hover:bg-stone-50 transition-colors">
                            {/* Model Name & Type */}
                            <td className="py-3.5 px-4">
                              <div className="font-semibold text-charcoal-900">{m.display_name}</div>
                              <div className="font-mono text-[10px] text-stone-500 mt-0.5">{m.model_id}</div>
                              <span
                                className={`inline-block mt-1 px-1.5 py-0.5 rounded text-[9px] font-semibold uppercase ${
                                  m.model_type === "EMBEDDING"
                                    ? "bg-olive-50 text-olive-800 border border-olive-200"
                                    : m.model_type === "RERANKER"
                                    ? "bg-stone-100 text-stone-700 border border-stone-300"
                                    : m.model_type === "KEYWORD"
                                    ? "bg-sage-50 text-olive-800 border border-sage-200"
                                    : "bg-stone-100 text-stone-700 border border-stone-200"
                                }`}
                              >
                                {m.model_type}
                              </span>
                            </td>

                            {/* Benchmark Source */}
                            <td className="py-3.5 px-4 max-w-xs">
                              <div className="font-medium text-stone-800">{pm?.benchmark_source || "Standard IR Benchmark"}</div>
                              <div className="text-[10px] text-stone-500 line-clamp-2 mt-0.5">
                                {pm?.dataset_description || m.notes}
                              </div>
                            </td>

                            {/* NDCG@10 */}
                            <td className="py-3.5 px-4">
                              {pm?.ndcg_at_k !== undefined && pm?.ndcg_at_k !== null ? (
                                <div className="space-y-1">
                                  <div className="font-mono font-bold text-stone-900">
                                    {(pm.ndcg_at_k * 100).toFixed(1)}%
                                    <span className="text-[10px] font-normal text-stone-400 ml-1">({pm.ndcg_at_k.toFixed(4)})</span>
                                  </div>
                                  <div className="w-20 bg-stone-100 rounded-full h-1.5 overflow-hidden">
                                    <div
                                      className="bg-olive-600 h-1.5 rounded-full"
                                      style={{ width: `${Math.min(100, Math.max(0, pm.ndcg_at_k * 100))}%` }}
                                    />
                                  </div>
                                </div>
                              ) : (
                                <span className="text-stone-400 italic text-[11px]">N/A (Extraction)</span>
                              )}
                            </td>

                            {/* MRR */}
                            <td className="py-3.5 px-4">
                              {pm?.mrr !== undefined && pm?.mrr !== null ? (
                                <div className="font-mono font-bold text-olive-700">
                                  {pm.mrr.toFixed(4)}
                                  <div className="text-[10px] font-normal text-stone-500">
                                    1/rank ~{(1 / (pm.mrr || 1)).toFixed(1)}
                                  </div>
                                </div>
                              ) : (
                                <span className="text-stone-400 italic text-[11px]">N/A</span>
                              )}
                            </td>

                            {/* Precision@10 */}
                            <td className="py-3.5 px-4 font-mono text-stone-700">
                              {pm?.precision_at_k !== undefined && pm?.precision_at_k !== null ? (
                                <span className="font-semibold">{(pm.precision_at_k * 100).toFixed(1)}%</span>
                              ) : (
                                <span className="text-stone-400">—</span>
                              )}
                            </td>

                            {/* Recall@10 */}
                            <td className="py-3.5 px-4 font-mono text-stone-700">
                              {pm?.recall_at_k !== undefined && pm?.recall_at_k !== null ? (
                                <span className="font-semibold">{(pm.recall_at_k * 100).toFixed(1)}%</span>
                              ) : (
                                <span className="text-stone-400">—</span>
                              )}
                            </td>

                            {/* F1-Score */}
                            <td className="py-3.5 px-4">
                              {pm?.f1_score !== undefined && pm?.f1_score !== null ? (
                                <div className="space-y-0.5">
                                  <span
                                    className={`inline-block px-2 py-0.5 rounded font-mono font-bold text-[11px] ${
                                      pm.f1_score >= 0.75
                                        ? "bg-olive-50 text-olive-800 border border-olive-200"
                                        : pm.f1_score >= 0.6
                                        ? "bg-sage-50 text-stone-800 border border-sage-200"
                                        : "bg-stone-100 text-stone-700 border border-stone-300"
                                    }`}
                                  >
                                    {(pm.f1_score * 100).toFixed(1)}%
                                  </span>
                                  <div className="text-[10px] text-stone-400 font-mono">F1={pm.f1_score.toFixed(4)}</div>
                                </div>
                              ) : (
                                <span className="text-stone-400">—</span>
                              )}
                            </td>

                            {/* Architectural Specs */}
                            <td className="py-3.5 px-4 text-[11px] text-stone-600 font-mono">
                              <div>{m.embedding_dimension ? `${m.embedding_dimension}d` : "Cross-Attn"}</div>
                              <div className="text-[10px] text-stone-400">{m.max_sequence_length ? `${m.max_sequence_length} tokens` : "N/A"}</div>
                            </td>
                          </tr>
                        );
                      })}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>

          {/* Detailed Metric Cards Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {models
              .filter((m) => {
                if (pretrainedFilterType !== "ALL" && m.model_type !== pretrainedFilterType) return false;
                if (pretrainedSearchQuery) {
                  const q = pretrainedSearchQuery.toLowerCase();
                  return (
                    m.display_name?.toLowerCase().includes(q) ||
                    m.model_id?.toLowerCase().includes(q) ||
                    m.pretrained_metrics?.benchmark_source?.toLowerCase().includes(q)
                  );
                }
                return true;
              })
              .map((m) => {
                const pm = m.pretrained_metrics;
                return (
                  <Card key={m.model_id} className="border-stone-200 flex flex-col justify-between hover:shadow-xs transition-shadow">
                    <div>
                      <CardHeader className="pb-3 border-b border-stone-100">
                        <div className="flex items-start justify-between gap-2">
                          <CardTitle className="text-sm font-semibold leading-tight text-stone-900">
                            {m.display_name}
                          </CardTitle>
                          <span
                            className={`shrink-0 px-2 py-0.5 rounded text-[10px] font-semibold uppercase ${
                              m.model_type === "EMBEDDING"
                                ? "bg-olive-50 text-olive-800 border border-olive-200"
                                : m.model_type === "RERANKER"
                                ? "bg-stone-100 text-stone-700 border border-stone-300"
                                : m.model_type === "KEYWORD"
                                ? "bg-sage-50 text-olive-800 border border-sage-200"
                                : "bg-stone-100 text-stone-700 border border-stone-200"
                            }`}
                          >
                            {m.model_type}
                          </span>
                        </div>
                        <CardDescription className="text-[11px] font-mono text-stone-500 truncate mt-1">
                          {m.model_id}
                        </CardDescription>
                      </CardHeader>

                      <CardContent className="p-4 space-y-3.5">
                        {/* Dataset Reference */}
                        <div className="bg-stone-50 p-2.5 rounded-lg border border-stone-200 text-xs">
                          <div className="text-[10px] text-stone-500 uppercase font-semibold">Evaluation Reference</div>
                          <div className="font-semibold text-stone-900 mt-0.5">{pm?.benchmark_source || "Pre-Trained Benchmark"}</div>
                          <div className="text-[11px] text-stone-600 mt-0.5 line-clamp-2">{pm?.dataset_description || m.notes}</div>
                        </div>

                        {/* Ground Truth Metric Gauges */}
                        <div className="space-y-2 text-xs">
                          {/* NDCG@10 */}
                          <div>
                            <div className="flex justify-between items-center text-[11px]">
                              <span className="text-stone-600 font-medium">NDCG@10 (Ranking Quality)</span>
                              <span className="font-mono font-bold text-stone-900">
                                {pm?.ndcg_at_k !== undefined && pm?.ndcg_at_k !== null ? `${(pm.ndcg_at_k * 100).toFixed(1)}%` : "N/A"}
                              </span>
                            </div>
                            <div className="w-full bg-stone-100 rounded-full h-1.5 mt-1 overflow-hidden">
                              <div
                                className="bg-olive-600 h-1.5 rounded-full"
                                style={{ width: `${Math.min(100, Math.max(0, (pm?.ndcg_at_k || 0) * 100))}%` }}
                              />
                            </div>
                          </div>

                          {/* MRR */}
                          <div>
                            <div className="flex justify-between items-center text-[11px]">
                              <span className="text-stone-600 font-medium">MRR (Mean Reciprocal Rank)</span>
                              <span className="font-mono font-bold text-olive-700">
                                {pm?.mrr !== undefined && pm?.mrr !== null ? pm.mrr.toFixed(4) : "N/A"}
                              </span>
                            </div>
                            <div className="w-full bg-stone-100 rounded-full h-1.5 mt-1 overflow-hidden">
                              <div
                                className="bg-olive-600 h-1.5 rounded-full"
                                style={{ width: `${Math.min(100, Math.max(0, (pm?.mrr || 0) * 100))}%` }}
                              />
                            </div>
                          </div>

                          {/* Classification F1 & Precision */}
                          <div className="grid grid-cols-3 gap-2 pt-1 border-t border-stone-100 text-center">
                            <div className="bg-white p-1.5 rounded border border-stone-200">
                              <div className="text-[9px] text-stone-500 uppercase font-semibold">Precision@10</div>
                              <div className="font-mono font-bold text-charcoal-900 mt-0.5">
                                {pm?.precision_at_k !== undefined && pm?.precision_at_k !== null ? `${(pm.precision_at_k * 100).toFixed(0)}%` : "—"}
                              </div>
                            </div>
                            <div className="bg-white p-1.5 rounded border border-stone-200">
                              <div className="text-[9px] text-stone-500 uppercase font-semibold">Recall@10</div>
                              <div className="font-mono font-bold text-charcoal-900 mt-0.5">
                                {pm?.recall_at_k !== undefined && pm?.recall_at_k !== null ? `${(pm.recall_at_k * 100).toFixed(0)}%` : "—"}
                              </div>
                            </div>
                            <div className="bg-white p-1.5 rounded border border-stone-200">
                              <div className="text-[9px] text-stone-500 uppercase font-semibold">F1-Score</div>
                              <div className="font-mono font-bold text-olive-700 mt-0.5">
                                {pm?.f1_score !== undefined && pm?.f1_score !== null ? `${(pm.f1_score * 100).toFixed(0)}%` : "—"}
                              </div>
                            </div>
                          </div>
                        </div>

                        {/* Known Limitations */}
                        {m.known_limitations && (
                          <div className="text-[11px] text-stone-500 bg-amber-500/5 border border-amber-500/20 p-2 rounded-lg">
                            <span className="font-semibold text-amber-800">Note: </span>
                            {m.known_limitations}
                          </div>
                        )}
                      </CardContent>
                    </div>

                    <div className="px-4 py-2.5 bg-stone-50 border-t border-stone-100 text-[10px] text-stone-500 flex items-center justify-between">
                      <span>Dim: {m.embedding_dimension ? `${m.embedding_dimension}d` : "None"}</span>
                      <span>Max: {m.max_sequence_length ? `${m.max_sequence_length} tokens` : "N/A"}</span>
                      <span>RAM: ~{m.memory_footprint_mb ? Math.round(m.memory_footprint_mb) : 80}MB</span>
                    </div>
                  </Card>
                );
              })}
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------- */}
      {/* TAB 1: AI MODEL SCORING & ARCHITECTURE RESULTS */}
      {/* ------------------------------------------------------------- */}
      {!loading && activeTab === "models" && (
        <div className="space-y-6">
          {/* Top Banner & Memory Controls */}
          <div className="rounded-xl border border-stone-300 bg-white p-5 flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <h2 className="text-base font-semibold text-stone-900 flex items-center gap-2">
                <Cpu className="h-4 w-4 text-olive-700" />
                AI Model Scoring & Architecture Benchmarking Matrix
              </h2>
              <p className="text-xs text-stone-500 mt-0.5">
                Technical evaluation of candidate embedding, cross-encoder, and keyword models under identical screening workloads.
              </p>
            </div>

            <div className="flex items-center gap-2.5">
              <Button
                variant="outline"
                size="sm"
                onClick={handleClearCache}
                leftIcon={<HardDrive className="h-3.5 w-3.5 text-olive-700" />}
              >
                Purge RAM Cache
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={() => setShowBenchmarkModal(true)}
                leftIcon={<Play className="h-3.5 w-3.5" />}
              >
                Run Controlled Benchmark
              </Button>
            </div>
          </div>

          {/* Model Architectural Specifications Catalog */}
          <Card>
            <CardHeader className="pb-3 border-b border-stone-100">
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-sm">Registered Model Catalog ({models.length} Models)</CardTitle>
                  <CardDescription className="text-xs">
                    Model architectures, embedding dimensions, context windows, and runtime constraints
                  </CardDescription>
                </div>
                <div className="flex items-center gap-2 text-xs text-stone-500">
                  <span className="inline-block h-2 w-2 rounded-full bg-olive-500" />
                  Loaded in Memory: {models.filter((m) => m.is_loaded).length}
                </div>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-stone-200 bg-stone-50 text-stone-500 font-semibold uppercase tracking-wider">
                      <th className="py-3 px-4">Model Name</th>
                      <th className="py-3 px-4">Type</th>
                      <th className="py-3 px-4">Dimension</th>
                      <th className="py-3 px-4">Max Tokens</th>
                      <th className="py-3 px-4">Device</th>
                      <th className="py-3 px-4">Memory State</th>
                      <th className="py-3 px-4 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-stone-100">
                    {models.map((m) => (
                      <tr key={m.model_id} className="hover:bg-stone-50">
                        <td className="py-3 px-4">
                          <div className="font-semibold text-charcoal-900">{m.display_name}</div>
                          <div className="font-mono text-[10px] text-stone-500">{m.model_id}</div>
                        </td>
                        <td className="py-3 px-4">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                              m.model_type === "EMBEDDING"
                                ? "bg-olive-50 text-olive-800 border border-olive-200"
                                : m.model_type === "RERANKER"
                                ? "bg-stone-100 text-stone-700 border border-stone-300"
                                : m.model_type === "KEYWORD"
                                ? "bg-sage-50 text-olive-800 border border-sage-200"
                                : "bg-stone-100 text-stone-700 border border-stone-200"
                            }`}
                          >
                            {m.model_type}
                          </span>
                        </td>
                        <td className="py-3 px-4 font-mono text-stone-600">
                          {m.embedding_dimension ? `${m.embedding_dimension}d` : "—"}
                        </td>
                        <td className="py-3 px-4 font-mono text-stone-600">
                          {m.max_sequence_length ? `${m.max_sequence_length} tokens` : "—"}
                        </td>
                        <td className="py-3 px-4 font-mono uppercase text-stone-600">
                          {m.device} ({m.precision || "fp32"})
                        </td>
                        <td className="py-3 px-4">
                          {m.is_loaded ? (
                            <span className="inline-flex items-center gap-1.5 text-xs text-olive-700">
                              <span className="h-1.5 w-1.5 rounded-full bg-olive-500 animate-pulse" />
                              Active in RAM (~{Math.round(m.memory_footprint_mb || 80)}MB)
                            </span>
                          ) : (
                            <span className="text-stone-400 text-xs">Standby (Zero RAM)</span>
                          )}
                        </td>
                        <td className="py-3 px-4 text-right">
                          {m.is_loaded ? (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleUnloadModel(m.model_id)}
                              className="text-stone-500 hover:text-olive-700"
                            >
                              Unload
                            </Button>
                          ) : (
                            <Button
                              variant="secondary"
                              size="sm"
                              onClick={() => handleLoadModel(m.model_id)}
                            >
                              Load
                            </Button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>

          {/* Model Benchmark Results Matrix */}
          {benchmarks.length > 0 && selectedBenchmarkRun && (
            <div className="space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-stone-50 border border-stone-200 p-4 rounded-xl">
                <div>
                  <h3 className="text-sm font-semibold text-charcoal-900 flex items-center gap-2">
                    <Zap className="h-4 w-4 text-amber-700" />
                    Experiment: {selectedBenchmarkRun.run_name}
                  </h3>
                  <p className="text-xs text-stone-500">
                    Executed on {formatDate(selectedBenchmarkRun.started_at)} • Dataset: {selectedBenchmarkRun.configuration?.dataset_id || "Screening Pool"} • Status:{" "}
                    <span className="font-semibold text-olive-700">{selectedBenchmarkRun.status}</span>
                  </p>
                </div>

                {benchmarks.length > 1 && (
                  <select
                    value={selectedBenchmarkRun.id}
                    onChange={(e) => {
                      const found = benchmarks.find((b) => b.id === e.target.value);
                      if (found) setSelectedBenchmarkRun(found);
                    }}
                    className="rounded-lg border border-stone-200 bg-white px-3 py-1.5 text-xs text-stone-800 focus:border-olive-500 focus:outline-none"
                  >
                    {benchmarks.map((b) => (
                      <option key={b.id} value={b.id}>
                        {b.run_name} ({formatDate(b.started_at)})
                      </option>
                    ))}
                  </select>
                )}
              </div>

              {/* Model Comparative Metrics Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {Object.entries(selectedBenchmarkRun.model_results || {}).map(([modelId, res]: [string, any]) => (
                  <Card key={modelId} className="border-stone-200">
                    <CardHeader className="pb-3 border-b border-stone-200">
                      <div className="flex items-center justify-between">
                        <CardTitle className="text-sm truncate" title={modelId}>
                          {res.model_name || modelId}
                        </CardTitle>
                        <Badge status="completed">{res.model_type || "EMBEDDING"}</Badge>
                      </div>
                      <CardDescription className="text-xs font-mono truncate">{modelId}</CardDescription>
                    </CardHeader>
                    <CardContent className="p-4 space-y-3">
                      {/* Latency & Throughput */}
                      <div className="grid grid-cols-2 gap-2 text-xs">
                        <div className="bg-white p-2 rounded-lg border border-stone-200">
                          <div className="text-[10px] text-stone-500 uppercase font-semibold">Latency</div>
                          <div className="text-sm font-bold text-charcoal-900 mt-0.5">
                            {res.latency_seconds !== undefined ? `${Math.round(res.latency_seconds * 1000)} ms` : "—"}
                          </div>
                        </div>
                        <div className="bg-white p-2 rounded-lg border border-stone-200">
                          <div className="text-[10px] text-stone-500 uppercase font-semibold">Throughput</div>
                          <div className="text-sm font-bold text-olive-700 mt-0.5">
                            {res.throughput_items_per_sec !== undefined ? `${res.throughput_items_per_sec} items/s` : "—"}
                          </div>
                        </div>
                      </div>

                      {/* Memory & Failures */}
                      <div className="grid grid-cols-2 gap-2 text-xs">
                        <div className="bg-white p-2 rounded-lg border border-stone-200">
                          <div className="text-[10px] text-stone-500 uppercase font-semibold">Peak RAM</div>
                          <div className="text-sm font-bold text-charcoal-900 mt-0.5">
                            {res.memory_peak_mb !== undefined ? `${res.memory_peak_mb} MB` : "—"}
                          </div>
                        </div>
                        <div className="bg-white p-2 rounded-lg border border-stone-200">
                          <div className="text-[10px] text-stone-500 uppercase font-semibold">Failures</div>
                          <div className="text-sm font-bold text-charcoal-900 mt-0.5">
                            {res.failure_count || 0}
                          </div>
                        </div>
                      </div>

                      {/* Ground Truth & Ranking Metrics */}
                      {res.ground_truth_metrics && Object.keys(res.ground_truth_metrics).length > 0 && (
                        <div className="space-y-1.5 pt-2 border-t border-stone-200">
                          <div className="text-[10px] text-stone-500 uppercase font-semibold">Ranking & Accuracy</div>
                          <div className="grid grid-cols-3 gap-1 text-[11px] text-stone-600">
                            <div>
                              NDCG@K: <span className="font-semibold text-charcoal-900">{res.ground_truth_metrics.ndcg_at_k ?? "—"}</span>
                            </div>
                            <div>
                              MRR: <span className="font-semibold text-charcoal-900">{res.ground_truth_metrics.mrr ?? "—"}</span>
                            </div>
                            <div>
                              F1-Score: <span className="font-semibold text-charcoal-900">{res.ground_truth_metrics.f1 ?? "—"}</span>
                            </div>
                          </div>
                        </div>
                      )}

                      {/* Descriptive Dispersion */}
                      {res.descriptive_stats && (
                        <div className="space-y-1.5 pt-2 border-t border-stone-200">
                          <div className="text-[10px] text-stone-500 uppercase font-semibold">Score Dispersion</div>
                          <div className="grid grid-cols-3 gap-1 text-[11px] text-stone-600">
                            <div>
                              Mean: <span className="font-semibold text-charcoal-900">{res.descriptive_stats.mean ?? "—"}</span>
                            </div>
                            <div>
                              Median: <span className="font-semibold text-charcoal-900">{res.descriptive_stats.median ?? "—"}</span>
                            </div>
                            <div>
                              Std Dev (σ): <span className="font-semibold text-charcoal-900">{res.descriptive_stats.std_dev ?? "—"}</span>
                            </div>
                          </div>
                        </div>
                      )}
                    </CardContent>
                  </Card>
                ))}
              </div>

              {/* Pairwise Model Agreement Matrix */}
              {selectedBenchmarkRun.pairwise_agreement &&
                Object.keys(selectedBenchmarkRun.pairwise_agreement).length > 0 && (
                  <Card>
                    <CardHeader className="pb-3 border-b border-stone-200">
                      <CardTitle className="text-sm">Pairwise Ranking Concordance (Kendall Tau & Spearman Correlation)</CardTitle>
                      <CardDescription className="text-xs">
                        Quantifies whether candidate models rank applicants in aligned order
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="p-4">
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        {Object.entries(selectedBenchmarkRun.pairwise_agreement).map(([pair, score]: [string, any]) => (
                          <div
                            key={pair}
                            className="flex items-center justify-between p-3 rounded-lg border border-stone-200 bg-stone-50"
                          >
                            <span className="text-xs text-stone-600 font-mono truncate max-w-sm">{pair}</span>
                            <span
                              className={`text-xs font-bold px-2 py-0.5 rounded ${
                                score >= 0.7
                                  ? "bg-olive-50 text-olive-800"
                                  : score >= 0.4
                                  ? "bg-sage-100 text-stone-800"
                                  : "bg-stone-100 text-stone-700"
                              }`}
                            >
                              {typeof score === "number" ? score.toFixed(4) : score}
                            </span>
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                )}
            </div>
          )}
        </div>
      )}

      {/* ------------------------------------------------------------- */}
      {/* TAB 2: Portfolio Trends */}
      {/* ------------------------------------------------------------- */}
      {!loading && activeTab === "portfolio" && (
        <div className="space-y-6">
          {/* Outcomes & Timing Grid */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">Ingestion & Processing Health</CardTitle>
                <CardDescription className="text-xs">Outcome breakdown across all candidate uploads</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2.5">
                <div className="flex items-center justify-between text-xs">
                  <span className="flex items-center gap-2 text-stone-600">
                    <CheckCircle className="h-4 w-4 text-olive-700" /> Completed Processing
                  </span>
                  <span className="font-semibold text-stone-900">{overview?.processing_outcomes?.COMPLETED ?? overview?.evaluated_resumes ?? 0}</span>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="flex items-center gap-2 text-stone-600">
                    <AlertTriangle className="h-4 w-4 text-amber-700" /> Partial / Scanned
                  </span>
                  <span className="font-semibold text-stone-900">{overview?.processing_outcomes?.PARTIAL ?? 0}</span>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="flex items-center gap-2 text-stone-600">
                    <XCircle className="h-4 w-4 text-terracotta-700" /> Failed Extractions
                  </span>
                  <span className="font-semibold text-stone-900">{overview?.processing_outcomes?.FAILED ?? 0}</span>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">Candidate Match Tiers</CardTitle>
                <CardDescription className="text-xs">Evaluation suitability breakdown</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2.5">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-stone-600">Top-Tier Fit (≥80%)</span>
                  <span className="font-semibold text-olive-700">{overview?.strong_matches_count ?? 0} Candidates</span>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-stone-600">Potential Match (60–79%)</span>
                  <span className="font-semibold text-olive-700">{overview?.potential_matches_count ?? 0} Candidates</span>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-stone-600">Under Review (&lt;60%)</span>
                  <span className="font-semibold text-stone-700">
                    {Math.max(0, (overview?.evaluated_resumes ?? 0) - (overview?.strong_matches_count ?? 0) - (overview?.potential_matches_count ?? 0))} Candidates
                  </span>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">NLP Pipeline Throughput</CardTitle>
                <CardDescription className="text-xs">Deterministic sentence-level processing</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2.5">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-stone-600">Default Model</span>
                  <span className="font-mono text-charcoal-900">all-MiniLM-L6-v2</span>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-stone-600">Embedding Vector Cache</span>
                  <span className="font-semibold text-olive-700">Active (SQLite IEEE 754)</span>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-stone-600">Evidence Citation Depth</span>
                  <span className="font-semibold text-charcoal-900">Verbatim Sentence Prov.</span>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Top In-Demand Skills Across Requisitions */}
          {overview?.top_demanded_skills && overview.top_demanded_skills.length > 0 && (
            <Card>
              <CardHeader className="pb-3 border-b border-stone-200">
                <CardTitle className="text-sm">Top Demanded Skills Across Workspace</CardTitle>
                <CardDescription className="text-xs">
                  Most frequently required competency criteria across open job requisitions
                </CardDescription>
              </CardHeader>
              <CardContent className="p-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                  {overview.top_demanded_skills.map((s, idx) => (
                    <div
                      key={idx}
                      className="flex items-center justify-between p-3 rounded-lg border border-stone-200 bg-stone-50"
                    >
                      <span className="text-xs font-medium text-charcoal-900 truncate max-w-xs">{s.skill}</span>
                      <span className="text-xs font-semibold text-olive-800 bg-olive-50 border border-olive-200 px-2 py-0.5 rounded">
                        {s.count} Requisitions
                      </span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Time Series Batches */}
          {overview?.time_series_batches && overview.time_series_batches.length > 0 && (
            <Card>
              <CardHeader className="pb-3 border-b border-stone-200">
                <CardTitle className="text-sm">Weekly Screening Volume Trends</CardTitle>
                <CardDescription className="text-xs">Periodic volume, average score, and shortlist throughput</CardDescription>
              </CardHeader>
              <CardContent className="p-0">
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="border-b border-stone-200 bg-stone-50 text-stone-500 font-semibold uppercase tracking-wider">
                        <th className="py-3 px-4">Period</th>
                        <th className="py-3 px-4">Sessions Created</th>
                        <th className="py-3 px-4">Candidates Evaluated</th>
                        <th className="py-3 px-4">Average Match Score</th>
                        <th className="py-3 px-4 text-right">Shortlisted</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-stone-100">
                      {overview.time_series_batches.map((b, idx) => (
                        <tr key={idx} className="hover:bg-stone-50">
                          <td className="py-3 px-4 font-mono font-semibold text-charcoal-900">{b.period}</td>
                          <td className="py-3 px-4 text-stone-600">{b.session_count}</td>
                          <td className="py-3 px-4 text-stone-600">{b.resume_count}</td>
                          <td className="py-3 px-4 text-olive-700 font-semibold">{Math.round(b.avg_score)}%</td>
                          <td className="py-3 px-4 text-right font-semibold text-olive-700">{b.shortlist_count}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* ------------------------------------------------------------- */}
      {/* TAB 3: Skill Coverage & Gaps */}
      {/* ------------------------------------------------------------- */}
      {!loading && activeTab === "skills" && (
        <div className="space-y-6">
          {/* Requisition Selector Bar */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-stone-50 border border-stone-200 p-4 rounded-xl">
            <div>
              <h2 className="text-sm font-semibold text-charcoal-900">Target Job Requisition</h2>
              <p className="text-xs text-stone-500">Select a screening session to view talent pool skill coverage and acute gaps</p>
            </div>

            <select
              value={selectedSessionId}
              onChange={(e) => setSelectedSessionId(e.target.value)}
              className="rounded-lg border border-stone-200 bg-white px-3 py-1.5 text-xs text-stone-800 focus:border-olive-500 focus:outline-none"
            >
              {sessions.map((s) => (
                <option key={s.id} value={s.id}>
                  {(s as any).session_name || (s as any).job_title || s.title || s.name} ({s.candidate_count ?? 0} candidates)
                </option>
              ))}
            </select>
          </div>

          {loadingSessionData ? (
            <div className="py-12 text-center text-stone-500">
              <RotateCcw className="h-6 w-6 animate-spin mx-auto mb-2 text-olive-600" />
              Analyzing talent pool skill coverage...
            </div>
          ) : skillCoverage.length === 0 ? (
            <div className="rounded-xl border border-dashed border-stone-200 p-12 text-center bg-white/40">
              <Sliders className="h-8 w-8 text-stone-400 mx-auto mb-2" />
              <h3 className="text-sm font-semibold text-charcoal-900">No parsed skill requirements found</h3>
              <p className="text-xs text-stone-500 mt-1 max-w-sm mx-auto">
                Ensure the requisition has completed parsing and candidate resumes are evaluated.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              <Card>
                <CardHeader className="pb-3 border-b border-stone-200">
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle className="text-sm">Job Description Requirements vs Candidate Evidence</CardTitle>
                      <CardDescription className="text-xs">
                        Evidence distribution normalized via SkillTaxonomyNormalizer
                      </CardDescription>
                    </div>
                    <div className="text-xs text-stone-500">
                      Total Skills Tracked: <span className="font-semibold text-charcoal-900">{skillCoverage.length}</span>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="p-0">
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead>
                        <tr className="border-b border-stone-200 bg-stone-50 text-stone-500 font-semibold uppercase tracking-wider">
                          <th className="py-3 px-4">Skill / Criterion</th>
                          <th className="py-3 px-4">Category</th>
                          <th className="py-3 px-4">Requirement</th>
                          <th className="py-3 px-4">Pool Coverage</th>
                          <th className="py-3 px-4">Evidence Citations</th>
                          <th className="py-3 px-4 text-right">Gap Status</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-stone-100">
                        {skillCoverage.map((item, idx) => (
                          <tr key={idx} className="hover:bg-stone-50">
                            <td className="py-3 px-4 font-semibold text-charcoal-900">{item.canonical_name}</td>
                            <td className="py-3 px-4 text-stone-500 uppercase text-[10px]">{item.category}</td>
                            <td className="py-3 px-4">
                              <span
                                className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                                  item.requirement_type === "REQUIRED"
                                    ? "bg-terracotta-50 text-terracotta-700 border border-terracotta-200"
                                    : "bg-stone-100 text-stone-700 border border-stone-200"
                                }`}
                              >
                                {item.requirement_type}
                              </span>
                            </td>
                            <td className="py-3 px-4 w-48">
                              <div className="flex items-center gap-2">
                                <ProgressBar value={item.pool_coverage_percentage} size="sm" />
                                <span className="text-[11px] font-mono text-stone-600 w-10 text-right">
                                  {Math.round(item.pool_coverage_percentage)}%
                                </span>
                              </div>
                            </td>
                            <td className="py-3 px-4 font-mono text-stone-600">
                              {item.candidate_evidence_count} Candidates
                            </td>
                            <td className="py-3 px-4 text-right">
                              <span
                                className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                                  item.gap_status === "ACUTE_GAP"
                                    ? "bg-terracotta-50 text-terracotta-700 border border-terracotta-200"
                                    : item.gap_status === "PARTIAL_GAP"
                                    ? "bg-amber-500/10 text-amber-700 border border-amber-500/20"
                                    : "bg-emerald-500/10 text-olive-700 border border-emerald-500/20"
                                }`}
                              >
                                {item.gap_status}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </CardContent>
              </Card>
            </div>
          )}
        </div>
      )}

      {/* ------------------------------------------------------------- */}
      {/* TAB 4: Criteria Variance */}
      {/* ------------------------------------------------------------- */}
      {!loading && activeTab === "variance" && (
        <div className="space-y-6">
          {/* Requisition Selector Bar */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-stone-50 border border-stone-200 p-4 rounded-xl">
            <div>
              <h2 className="text-sm font-semibold text-charcoal-900">Target Requisition</h2>
              <p className="text-xs text-stone-500">Statistical variance, standard deviation (σ), and semantic discovery deltas</p>
            </div>

            <select
              value={selectedSessionId}
              onChange={(e) => setSelectedSessionId(e.target.value)}
              className="rounded-lg border border-stone-200 bg-white px-3 py-1.5 text-xs text-stone-800 focus:border-olive-500 focus:outline-none"
            >
              {sessions.map((s) => (
                <option key={s.id} value={s.id}>
                  {(s as any).session_name || (s as any).job_title || s.title || s.name} ({s.candidate_count ?? 0} candidates)
                </option>
              ))}
            </select>
          </div>

          {loadingSessionData ? (
            <div className="py-12 text-center text-stone-500">
              <RotateCcw className="h-6 w-6 animate-spin mx-auto mb-2 text-olive-600" />
              Computing standard deviations and AI divergence...
            </div>
          ) : criterionAnalytics.length === 0 ? (
            <div className="rounded-xl border border-dashed border-stone-200 p-12 text-center bg-white/40">
              <Sparkles className="h-8 w-8 text-stone-400 mx-auto mb-2" />
              <h3 className="text-sm font-semibold text-charcoal-900">No criteria evaluations available</h3>
              <p className="text-xs text-stone-500 mt-1 max-w-sm mx-auto">
                Run AI evaluation on this session to compute variance and AI divergence metrics.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              <Card>
                <CardHeader className="pb-3 border-b border-stone-200">
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle className="text-sm">Per-Criterion Variance & Semantic Discovery Delta</CardTitle>
                      <CardDescription className="text-xs">
                        Flags low-variation criteria (σ &lt; 0.08) that fail to differentiate candidate fitness
                      </CardDescription>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="p-0">
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead>
                        <tr className="border-b border-stone-200 bg-stone-50 text-stone-500 font-semibold uppercase tracking-wider">
                          <th className="py-3 px-4">Criterion</th>
                          <th className="py-3 px-4">Weight</th>
                          <th className="py-3 px-4">Mean Points</th>
                          <th className="py-3 px-4">Std Dev (σ)</th>
                          <th className="py-3 px-4">Variance (σ²)</th>
                          <th className="py-3 px-4">AI Divergence</th>
                          <th className="py-3 px-4">Semantic Boosts</th>
                          <th className="py-3 px-4 text-right">Variation Status</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-stone-100">
                        {criterionAnalytics.map((c) => (
                          <tr key={c.criterion_id} className="hover:bg-stone-50">
                            <td className="py-3 px-4">
                              <div className="font-semibold text-charcoal-900">{c.criterion_name}</div>
                              <div className="text-[10px] text-stone-500">{c.category} • {c.criterion_type}</div>
                            </td>
                            <td className="py-3 px-4 font-mono text-stone-600">
                              {(c.configured_weight * 100).toFixed(0)}%
                            </td>
                            <td className="py-3 px-4 font-mono font-semibold text-charcoal-900">
                              {c.mean_normalized_points?.toFixed(1) ?? "—"} pts
                            </td>
                            <td className="py-3 px-4 font-mono text-stone-700">
                              {c.std_dev?.toFixed(4) ?? "—"}
                            </td>
                            <td className="py-3 px-4 font-mono text-stone-500">
                              {c.variance?.toFixed(4) ?? "—"}
                            </td>
                            <td className="py-3 px-4 font-mono text-stone-700 font-semibold">
                              {c.keyword_vs_semantic_divergence ? `±${c.keyword_vs_semantic_divergence.toFixed(1)} pts` : "—"}
                            </td>
                            <td className="py-3 px-4 font-mono text-olive-700">
                              {c.semantic_boost_count || 0} candidates
                            </td>
                            <td className="py-3 px-4 text-right">
                              {c.is_low_variation ? (
                                <span className="inline-flex items-center gap-1 bg-amber-500/10 text-amber-700 border border-amber-500/20 px-2 py-0.5 rounded text-[10px] font-semibold">
                                  <AlertTriangle className="h-3 w-3" />
                                  Low Variation (σ &lt; 0.08)
                                </span>
                              ) : (
                                <span className="inline-flex items-center gap-1 bg-emerald-500/10 text-olive-700 border border-emerald-500/20 px-2 py-0.5 rounded text-[10px] font-semibold">
                                  <CheckCircle2 className="h-3 w-3" />
                                  Differentiating Fit
                                </span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </CardContent>
              </Card>
            </div>
          )}
        </div>
      )}

      {/* ------------------------------------------------------------- */}
      {/* TAB 5: DATA-GROUNDED TRACEABLE INSIGHTS */}
      {/* ------------------------------------------------------------- */}
      {!loading && activeTab === "insights" && (
        <div className="space-y-6">
          <div className="rounded-xl border border-stone-200 bg-white p-5">
            <h2 className="text-base font-semibold text-charcoal-900 flex items-center gap-2">
              <CheckCircle className="h-4 w-4 text-olive-700" />
              Mathematical & Traceable Insights Audit
            </h2>
            <p className="text-xs text-stone-500 mt-1">
              Deterministic, rule-based recruitment insights with explicit mathematical formulas and calculation basis audits.
              Eliminates generic or ungrounded AI recommendations.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Card>
              <CardHeader className="pb-3 border-b border-stone-200">
                <CardTitle className="text-sm flex items-center gap-2">
                  <Sliders className="h-4 w-4 text-olive-700" />
                  Talent Gap Rule Grounding
                </CardTitle>
              </CardHeader>
              <CardContent className="p-4 space-y-3 text-xs">
                <div className="p-3 rounded-lg bg-white border border-stone-200 font-mono text-[11px] text-blue-300">
                  Acute Gap ⟺ (Candidate Coverage &lt; 30%) ∧ (Criterion Type = REQUIRED)
                </div>
                <p className="text-stone-600 leading-relaxed">
                  When a mandatory qualification has fewer than 30% supporting citations across the candidate pool, the engine
                  flags an acute talent shortage and recommends candidate pool expansion or sourcing calibration.
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-3 border-b border-stone-200">
                <CardTitle className="text-sm flex items-center gap-2">
                  <Sparkles className="h-4 w-4 text-amber-700" />
                  AI Divergence & Latent Discovery Rule
                </CardTitle>
              </CardHeader>
              <CardContent className="p-4 space-y-3 text-xs">
                <div className="p-3 rounded-lg bg-white border border-stone-200 font-mono text-[11px] text-amber-300">
                  Semantic Boost ⟺ (Dense Similarity ≥ Exact Keyword + 0.30)
                </div>
                <p className="text-stone-600 leading-relaxed">
                  Measures candidates whose conceptual experience was recognized by dense SentenceTransformer embeddings despite
                  missing verbatim keyword tokens, preventing false-negative rejections.
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-3 border-b border-stone-200">
                <CardTitle className="text-sm flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4 text-terracotta-700" />
                  Low-Variation Filter Flag
                </CardTitle>
              </CardHeader>
              <CardContent className="p-4 space-y-3 text-xs">
                <div className="p-3 rounded-lg bg-white border border-stone-200 font-mono text-[11px] text-rose-300">
                  Low-Variation Criterion ⟺ σ(Criterion Points) &lt; 0.08
                </div>
                <p className="text-stone-600 leading-relaxed">
                  Flags criteria that do not effectively separate top candidates from bottom candidates due to near-universal
                  compliance or uniform omission.
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-3 border-b border-stone-200">
                <CardTitle className="text-sm flex items-center gap-2">
                  <ShieldAlert className="h-4 w-4 text-olive-700" />
                  Responsible AI Guardrail Rule
                </CardTitle>
              </CardHeader>
              <CardContent className="p-4 space-y-3 text-xs">
                <div className="p-3 rounded-lg bg-white border border-stone-200 font-mono text-[11px] text-emerald-300">
                  Demographic & Subjective Trait Filter ⟹ Automatic Rejection (0.0 Weight)
                </div>
                <p className="text-stone-600 leading-relaxed">
                  Strictly validates evaluation criteria against protected demographics (age, gender, ethnicity, marital status)
                  and subjective traits ("rockstar", "vibes"), ensuring only verifiable competency criteria are scored.
                </p>
              </CardContent>
            </Card>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------- */}
      {/* RUN BENCHMARK MODAL */}
      {/* ------------------------------------------------------------- */}
      {showBenchmarkModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-stone-50 backdrop-blur-sm p-4">
          <div className="w-full max-w-xl rounded-xl border border-stone-200 bg-white p-6 shadow-2xl space-y-4 animate-scaleUp">
            <div className="flex items-center justify-between border-b border-stone-200 pb-3">
              <h3 className="text-base font-bold text-charcoal-900 flex items-center gap-2">
                <Zap className="h-5 w-5 text-amber-700" />
                Configure Controlled Model Benchmark
              </h3>
              <button onClick={() => setShowBenchmarkModal(false)} className="text-stone-400 hover:text-stone-700 text-lg">
                &times;
              </button>
            </div>

            <div className="space-y-4 text-xs">
              <div>
                <label className="block font-medium text-stone-600 mb-1.5">
                  Select Models to Benchmark (2 to 4 recommended):
                </label>
                <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
                  {models.map((m) => {
                    const isSelected = benchmarkModels.includes(m.model_id);
                    return (
                      <label
                        key={m.model_id}
                        className={`flex items-center justify-between p-2.5 rounded-lg border cursor-pointer transition-colors ${
                          isSelected
                            ? "border-olive-500 bg-olive-50 text-olive-900"
                            : "border-stone-200 bg-white text-stone-600 hover:text-stone-900 hover:border-stone-300"
                        }`}
                      >
                        <div className="flex items-center gap-2.5">
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => {
                              if (isSelected) {
                                setBenchmarkModels(benchmarkModels.filter((id) => id !== m.model_id));
                              } else {
                                setBenchmarkModels([...benchmarkModels, m.model_id]);
                              }
                            }}
                            className="rounded border-stone-300 bg-white text-olive-600 focus:ring-0"
                          />
                          <span className="font-semibold text-xs">{m.display_name}</span>
                        </div>
                        <span className="font-mono text-[10px] text-stone-400">{m.model_type}</span>
                      </label>
                    );
                  })}
                </div>
              </div>

              <div>
                <label className="block font-medium text-stone-600 mb-1.5">
                  Evaluation Dataset / Source:
                </label>
                <select
                  value={benchmarkDataset}
                  onChange={(e) => setBenchmarkDataset(e.target.value)}
                  className="w-full rounded-lg border border-stone-200 bg-white py-2 px-3 text-xs text-stone-800 focus:border-olive-500 focus:outline-none"
                >
                  {datasets.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name} ({d.item_count} benchmark items)
                    </option>
                  ))}
                  {datasets.length === 0 && (
                    <option value="synthetic-benchmark-v1">
                      Synthetic Criteria & Experience Benchmark (24 items)
                    </option>
                  )}
                </select>
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-stone-200">
              <Button variant="ghost" size="sm" onClick={() => setShowBenchmarkModal(false)}>
                Cancel
              </Button>
              <Button
                variant="primary"
                size="sm"
                isLoading={runningBenchmark}
                onClick={handleExecuteBenchmark}
                leftIcon={<Play className="h-4 w-4" />}
              >
                Execute Benchmark ({benchmarkModels.length} Models)
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
