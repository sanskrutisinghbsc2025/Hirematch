"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  ArrowLeft,
  Sliders,
  Play,
  Save,
  TrendingUp,
  TrendingDown,
  Minus,
  CheckCircle2,
} from "lucide-react";
import { apiClient } from "@/lib/api/client";
import { SimulationResult, CriterionInput } from "@/lib/types/api";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";

export default function SensitivitySimulatorPage() {
  const params = useParams();
  const sessionId = params.sessionId as string;

  const [criteria, setCriteria] = useState<CriterionInput[]>([]);
  const [weights, setWeights] = useState<Record<string, number>>({});
  const [threshold, setThreshold] = useState<number>(60);
  const [simulation, setSimulation] = useState<SimulationResult | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadSessionCriteria = async () => {
      try {
        setLoading(true);
        const data = await apiClient.getSessionCriteria(sessionId);
        const criteriaList: CriterionInput[] = Array.isArray(data)
          ? data
          : data?.criteria || [];
        setCriteria(criteriaList);

        const initialWeights: Record<string, number> = {};
        criteriaList.forEach((c: any) => {
          const key = c.id || c.criterion_name || c.name;
          if (key) {
            initialWeights[key] = typeof c.weight === "number" ? c.weight : 0.2;
          }
        });
        setWeights(initialWeights);
      } catch (err: any) {
        console.error("Failed to load criteria:", err);
      } finally {
        setLoading(false);
      }
    };

    if (sessionId) loadSessionCriteria();
  }, [sessionId]);

  const handleWeightChange = (key: string, val: number) => {
    setWeights((prev) => ({ ...prev, [key]: val }));
  };

  const handleNormalize = () => {
    const sum = Object.values(weights).reduce((a, b) => a + b, 0);
    if (sum <= 0) return;
    const normalized: Record<string, number> = {};
    for (const [k, v] of Object.entries(weights)) {
      normalized[k] = Number((v / sum).toFixed(2));
    }
    setWeights(normalized);
  };

  const handleRunSimulation = async () => {
    try {
      setIsRunning(true);
      const res = await apiClient.runSimulation({
        session_id: sessionId,
        simulated_weights: weights,
        weight_adjustments: weights,
        threshold_adjustments: { min_score: threshold },
      });
      setSimulation(res);
    } catch (err: any) {
      alert("Simulation failed: " + err.message);
    } finally {
      setIsRunning(false);
    }
  };

  const handleSaveConfig = async () => {
    try {
      setIsSaving(true);
      await apiClient.saveSimulationConfig({
        session_id: sessionId,
        weights,
        simulated_weights: weights,
        thresholds: { min_score: threshold },
      });
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err: any) {
      alert("Failed to save configuration: " + err.message);
    } finally {
      setIsSaving(false);
    }
  };

  const rankShifts = simulation?.rank_shifts || simulation?.simulated_candidates || [];

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
            <h1 className="text-xl font-semibold text-charcoal-900">
              Ranking sensitivity simulator
            </h1>
            <p className="text-sm text-stone-500 mt-0.5">
              Simulate how adjusting weights and score thresholds affects candidate rankings.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={handleNormalize} disabled={criteria.length === 0}>
              Balance weights
            </Button>
            <Button
              variant="primary"
              size="sm"
              isLoading={isRunning}
              onClick={handleRunSimulation}
              leftIcon={<Play className="h-3.5 w-3.5" />}
            >
              Simulate
            </Button>
            <Button
              variant="secondary"
              size="sm"
              isLoading={isSaving}
              onClick={handleSaveConfig}
              leftIcon={<Save className="h-3.5 w-3.5" />}
            >
              Save weights
            </Button>
          </div>
        </div>
      </div>

      {saveSuccess && (
        <div className="rounded-lg border border-olive-200 bg-olive-50 p-3 text-xs text-olive-700 flex items-center gap-2">
          <CheckCircle2 className="h-4 w-4 text-olive-600" />
          <span>Configuration saved successfully.</span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* ── Controls Column ── */}
        <Card className="lg:col-span-1">
          <CardHeader className="pb-3 border-b border-stone-100">
            <CardTitle className="text-sm">Criteria weights</CardTitle>
            <CardDescription>
              Adjust the relative importance of each criterion
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 pt-4">
            {loading ? (
              <p className="py-6 text-center text-xs text-stone-400">Loading criteria...</p>
            ) : criteria.length === 0 ? (
              <p className="text-xs text-stone-400">No criteria defined for this session.</p>
            ) : (
              criteria.map((c: any, idx: number) => {
                const critName = c.criterion_name || c.name || `Criterion #${idx + 1}`;
                const critId = c.id || critName;
                const weightVal = weights[critId] ?? weights[critName] ?? (typeof c.weight === "number" ? c.weight : 0.2);
                return (
                  <div key={critId} className="space-y-1">
                    <div className="flex justify-between text-xs">
                      <span className="font-medium text-stone-700 truncate max-w-[180px]" title={critName}>
                        {critName}
                      </span>
                      <span className="font-mono text-stone-500">
                        {typeof weightVal === "number" ? weightVal.toFixed(2) : weightVal}
                      </span>
                    </div>
                    <input
                      type="range"
                      min={0.05}
                      max={1.0}
                      step={0.05}
                      value={weightVal}
                      onChange={(e) =>
                        handleWeightChange(critId, parseFloat(e.target.value))
                      }
                      className="w-full accent-olive-500"
                    />
                  </div>
                );
              })
            )}

            <div className="pt-3 border-t border-stone-100 space-y-1.5">
              <div className="flex justify-between text-xs">
                <span className="font-medium text-stone-700">Minimum score cutoff</span>
                <span className="font-mono text-olive-700">{threshold}%</span>
              </div>
              <input
                type="range"
                min={30}
                max={90}
                step={5}
                value={threshold}
                onChange={(e) => setThreshold(parseInt(e.target.value))}
                className="w-full accent-olive-600"
              />
            </div>
          </CardContent>
        </Card>

        {/* ── Results Column ── */}
        <div className="lg:col-span-2 bg-white border border-[#E8E3DA] rounded-2xl overflow-hidden shadow-subtle">
          <div className="px-6 py-4 border-b border-[#E8E3DA] flex items-center justify-between bg-white">
            <div>
              <h3 className="text-sm font-semibold text-charcoal-900">Simulated rank changes</h3>
              <p className="text-xs text-stone-400 mt-0.5">
                Comparison between current rankings and simulated outcome
              </p>
            </div>
            {simulation && simulation.volatility_percentage !== undefined && (
              <span className="text-[11px] font-mono font-medium text-stone-600 bg-stone-100 border border-stone-200 px-2 py-0.5 rounded">
                Volatility: {simulation.volatility_percentage}%
              </span>
            )}
          </div>
          <CardContent className="p-0">
            {!simulation ? (
              <div className="p-12 text-center text-stone-400">
                <Sliders className="h-7 w-7 text-stone-300 mx-auto mb-2" />
                <p className="text-sm font-medium text-stone-600">No active simulation</p>
                <p className="text-xs text-stone-400 mt-1 max-w-xs mx-auto">
                  Adjust sliders on the left and click "Simulate" to see how candidates' ranks change.
                </p>
              </div>
            ) : rankShifts.length === 0 ? (
              <div className="p-12 text-center text-stone-400">
                <p className="text-sm font-medium text-stone-600">No candidates available</p>
                <p className="text-xs text-stone-400 mt-1 max-w-xs mx-auto">
                  Evaluate candidates in this session first to simulate rank shifts.
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-[#E8E3DA] bg-[#FAF8F5] text-stone-400 font-semibold uppercase tracking-wider">
                      <th className="py-3 px-4">Candidate</th>
                      <th className="py-3 px-4 text-center">Original</th>
                      <th className="py-3 px-4 text-center">Simulated</th>
                      <th className="py-3 px-4 text-center">Change</th>
                      <th className="py-3 px-4 text-right">Score</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-stone-100">
                    {rankShifts.map((shift: any, idx: number) => {
                      const delta = shift.rank_delta ?? 0;
                      const candName = shift.candidate_name || shift.name || shift.filename || `Candidate #${idx + 1}`;
                      const scoreVal = shift.simulated_score ?? shift.original_score ?? 0;
                      return (
                        <tr key={shift.candidate_id || idx} className="hover:bg-stone-50 transition-colors">
                          <td className="py-3 px-4 font-medium text-charcoal-900">
                            {candName}
                          </td>
                          <td className="py-3 px-4 text-center font-mono text-stone-400">
                            #{shift.original_rank}
                          </td>
                          <td className="py-3 px-4 text-center font-mono font-semibold text-stone-900">
                            #{shift.simulated_rank}
                          </td>
                          <td className="py-3 px-4 text-center">
                            {delta > 0 ? (
                              <span className="inline-flex items-center gap-0.5 font-mono font-medium text-olive-700">
                                <TrendingUp className="h-3 w-3" />
                                +{delta}
                              </span>
                            ) : delta < 0 ? (
                              <span className="inline-flex items-center gap-0.5 font-mono font-medium text-terracotta-700">
                                <TrendingDown className="h-3 w-3" />
                                {delta}
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-0.5 font-mono text-stone-400">
                                <Minus className="h-3 w-3" />0
                              </span>
                            )}
                          </td>
                          <td className="py-3 px-4 text-right font-mono font-semibold text-stone-900">
                            {Math.round(scoreVal)}%
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </div>
      </div>
    </div>
  );
}
