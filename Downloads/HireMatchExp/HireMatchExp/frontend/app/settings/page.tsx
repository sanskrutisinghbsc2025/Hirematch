"use client";

import React, { useEffect, useState } from "react";
import { CheckCircle2 } from "lucide-react";
import { apiClient } from "@/lib/api/client";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/Card";

export default function SettingsPage() {
  const [settings, setSettings] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchSettings = async () => {
      try {
        setLoading(true);
        const data = await apiClient.getSettings();
        setSettings(data);
      } catch (err: any) {
        console.error("Failed to load settings:", err);
      } finally {
        setLoading(false);
      }
    };

    fetchSettings();
  }, []);

  const policies = [
    {
      label: "Human review required",
      detail:
        "All screening scores are recommendations only. Hiring decisions must be made by a human reviewer.",
    },
    {
      label: "Traceable scores",
      detail:
        "Every score is backed by specific resume sentences you can inspect and verify.",
    },
    {
      label: "Batch limits",
      detail:
        "Sessions are capped at 100 resumes to ensure consistent, reliable comparisons.",
    },
    {
      label: "Transparent flags",
      detail:
        "Timeline gaps and missing requirements are surfaced for your review, not hidden.",
    },
  ];

  const configItems = [
    { label: "Backend API", value: "FastAPI (Python 3.10+)" },
    { label: "Frontend", value: "Next.js 14 (App Router) + React + Tailwind" },
    { label: "Database", value: "SQLite (hirematch.db)" },
    { label: "Resume cap per session", value: "100 resumes" },
    { label: "Supported formats", value: ".pdf, .docx, .txt" },
    { label: "Embedding model", value: "sentence-transformers/all-MiniLM-L6-v2" },
  ];

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Header */}
      <div>
        <h1 className="text-xl font-semibold text-charcoal-900">Settings</h1>
        <p className="text-sm text-stone-500 mt-0.5">
          Platform configuration, responsible AI policies, and system information.
        </p>
      </div>

      {/* Responsible AI */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base text-charcoal-900">
            Responsible AI
          </CardTitle>
          <CardDescription>
            Core policies applied to every screening and scoring workflow.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-5">
            {policies.map((policy) => (
              <div key={policy.label} className="flex gap-3">
                <CheckCircle2 className="h-4 w-4 text-olive-600 mt-0.5 shrink-0" />
                <div>
                  <p className="text-sm font-semibold text-stone-800">
                    {policy.label}
                  </p>
                  <p className="text-sm text-stone-500 mt-0.5 leading-relaxed">
                    {policy.detail}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* System Configuration */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base text-charcoal-900">
            System Configuration
          </CardTitle>
          <CardDescription>
            Runtime environment and platform specifications.
          </CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          <dl className="divide-y divide-stone-100 text-sm">
            {configItems.map((item) => (
              <div
                key={item.label}
                className="px-6 py-3 flex items-center justify-between gap-4"
              >
                <dt className="text-stone-500 font-medium shrink-0">
                  {item.label}
                </dt>
                <dd className="font-mono text-stone-700 text-right">
                  {item.value}
                </dd>
              </div>
            ))}
          </dl>
        </CardContent>
      </Card>
    </div>
  );
}
