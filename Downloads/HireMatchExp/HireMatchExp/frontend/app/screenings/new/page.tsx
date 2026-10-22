"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  FileText,
  Sliders,
  UploadCloud,
  CheckCircle2,
  ArrowRight,
  ArrowLeft,
  Plus,
  Trash2,
  AlertCircle,
  FileCheck,
  Play,
  Loader2,
  Sparkles,
  FileSearch,
  Check,
} from "lucide-react";
import { apiClient } from "@/lib/api/client";
import { CriterionInput } from "@/lib/types/api";
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { cn } from "@/lib/utils";

const STEPS = [
  { id: 1, title: "Role details", icon: FileText },
  { id: 2, title: "Evaluation criteria", icon: Sliders },
  { id: 3, title: "Upload resumes", icon: UploadCloud },
  { id: 4, title: "Score", icon: Play },
];

export default function NewScreeningPage() {
  const router = useRouter();
  const [currentStep, setCurrentStep] = useState(1);

  // Workflow Mode: Create New vs Update Existing
  const [existingSessions, setExistingSessions] = useState<any[]>([]);
  const [creationMode, setCreationMode] = useState<"new" | "existing">("new");
  const [selectedExistingId, setSelectedExistingId] = useState<string>("");

  useEffect(() => {
    apiClient.getSessions(1, 50).then((res) => {
      const items = res.items || [];
      setExistingSessions(items);
      if (items.length > 0) {
        setSelectedExistingId(items[0].id);
      }
    }).catch(() => {});
  }, []);

  // Step 1: Job Description
  const [title, setTitle] = useState("");
  const [department, setDepartment] = useState("Engineering");
  const [seniority, setSeniority] = useState("Senior");
  const [jdText, setJdText] = useState("");
  const [isExtractingJd, setIsExtractingJd] = useState(false);

  // Step 2: Criteria
  const [criteria, setCriteria] = useState<CriterionInput[]>([
    {
      name: "Python & Backend Systems",
      description: "Production experience with Python, FastAPI, or distributed systems",
      criterion_type: "skill",
      weight: 0.35,
      is_required: true,
      min_score: 50,
    },
    {
      name: "NLP & Machine Learning",
      description: "Hands-on experience with NLP models, embeddings, or transformer architectures",
      criterion_type: "skill",
      weight: 0.35,
      is_required: false,
      min_score: 40,
    },
    {
      name: "Years of Experience",
      description: "At least 3-5 years in full-stack or backend engineering",
      criterion_type: "experience",
      weight: 0.30,
      is_required: true,
      min_score: 60,
    },
  ]);

  // Session & Job IDs created on backend
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);

  // Step 3: Files
  const [files, setFiles] = useState<File[]>([]);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);

  // Step 4: Processing & Evaluation
  const [isProcessing, setIsProcessing] = useState(false);
  const [processStatus, setProcessStatus] = useState<string>("Ready to initialize pipeline");
  const [processProgress, setProcessProgress] = useState(0);

  // Step 1 -> Extract JD Criteria
  const handleAutoExtractJd = async () => {
    if (!jdText.trim()) return;
    try {
      setIsExtractingJd(true);
      const res = await apiClient.parseJobDescription({ text: jdText });
      if (res.title && !title) setTitle(res.title);
      const rawCriteria = res.auto_criteria || res.extracted_criteria || [];
      if (rawCriteria.length > 0) {
        setCriteria(
          rawCriteria.map((c: any) => ({
            name: c.criterion_name || c.name || "Required Skill",
            description: c.description || "",
            criterion_type: c.criterion_type ? c.criterion_type.toLowerCase() : "skill",
            weight: Number((1 / rawCriteria.length).toFixed(2)),
            is_required: c.criterion_type === "REQUIRED" || c.is_required === true,
            min_score: c.min_score ?? 50,
          }))
        );
      }
    } catch (err: any) {
      alert("JD parsing note: " + (err.message || "Using current criteria"));
    } finally {
      setIsExtractingJd(false);
    }
  };

  // Add / Remove Criterion
  const handleAddCriterion = () => {
    setCriteria([
      ...criteria,
      {
        name: `Criterion ${criteria.length + 1}`,
        description: "Evaluation description",
        criterion_type: "skill",
        weight: 0.2,
        is_required: false,
        min_score: 50,
      },
    ]);
  };

  const handleRemoveCriterion = (index: number) => {
    setCriteria(criteria.filter((_, i) => i !== index));
  };

  const handleCriterionChange = (index: number, field: keyof CriterionInput, val: any) => {
    const updated = [...criteria];
    updated[index] = { ...updated[index], [field]: val };
    setCriteria(updated);
  };

  const normalizeWeights = () => {
    const sum = criteria.reduce((acc, c) => acc + (c.weight || 0), 0);
    if (sum <= 0) return;
    setCriteria(
      criteria.map((c) => ({
        ...c,
        weight: Number(((c.weight || 0) / sum).toFixed(2)),
      }))
    );
  };

  // Step 1 Submit: Create Requisition Session & Job
  const handleProceedFromStep1 = async () => {
    if (creationMode === "existing" && selectedExistingId) {
      router.push(`/screenings/${selectedExistingId}`);
      return;
    }
    if (!title.trim()) {
      alert("Please provide a requisition title");
      return;
    }
    try {
      if (!sessionId) {
        const jobDesc = jdText.trim() ? jdText.trim() : `Requisition for ${title}`;
        const job = await apiClient.createJob({
          title,
          description: jobDesc,
          department,
          seniority_level: seniority,
        });
        setJobId(job.id);

        const sess = await apiClient.createSession({
          job_id: job.id,
          session_name: title,
          title,
          description: jobDesc,
          department,
        });
        setSessionId(sess.id);
      }
      setCurrentStep(2);
    } catch (err: any) {
      alert("Error initializing session: " + err.message);
    }
  };

  // Step 2 Submit: Save criteria
  const handleProceedFromStep2 = async () => {
    if (criteria.length === 0) {
      alert("Please add at least one evaluation criterion");
      return;
    }
    try {
      if (sessionId) {
        await apiClient.saveSessionCriteria(sessionId, { criteria });
      }
      setCurrentStep(3);
    } catch (err: any) {
      console.warn("Criteria sync note:", err.message);
      setCurrentStep(3);
    }
  };

  // Step 3: Handle File Ingestion
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files) return;
    const selected = Array.from(e.target.files);
    if (files.length + selected.length > 100) {
      setUploadError("Maximum 100 resumes allowed per screening batch (platform limit).");
      return;
    }
    setUploadError(null);
    setFiles((prev) => [...prev, ...selected]);
  };

  const handleProceedFromStep3 = async () => {
    if (files.length === 0) {
      alert("Please upload at least one resume file (.pdf, .docx, or .txt)");
      return;
    }
    if (files.length > 100) {
      setUploadError("Resume cap exceeded: Please select 100 or fewer resumes.");
      return;
    }
    try {
      setIsUploading(true);
      if (sessionId) {
        await apiClient.uploadResumes(sessionId, files);
      }
      setCurrentStep(4);
    } catch (err: any) {
      setUploadError("Upload failed: " + err.message);
    } finally {
      setIsUploading(false);
    }
  };

  // Step 4: Run Extraction and Evaluation
  const handleExecuteEvaluation = async () => {
    if (!sessionId) return;
    try {
      setIsProcessing(true);
      setProcessProgress(20);
      setProcessStatus("Extracting candidate text, skills & experience...");

      await apiClient.processSessionResumes(sessionId);
      setProcessProgress(60);
      setProcessStatus("Evaluating candidates across criteria with sentence embeddings...");

      await apiClient.evaluateSession(sessionId);
      setProcessProgress(100);
      setProcessStatus("Screening completed successfully! Redirecting to workspace...");

      setTimeout(() => {
        router.push(`/screenings/${sessionId}`);
      }, 1200);
    } catch (err: any) {
      setProcessStatus("Error during evaluation: " + err.message);
      setIsProcessing(false);
    }
  };

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      {/* ── Stepper Header ── */}
      <div className="bg-white border border-[#E8E3DA] rounded-2xl p-4 sm:p-5 shadow-subtle">
        <div className="flex items-center justify-between">
          {STEPS.map((s, idx) => {
            const isDone = currentStep > s.id;
            const isCurrent = currentStep === s.id;
            return (
              <div key={s.id} className="flex items-center flex-1 last:flex-none">
                <div className="flex items-center gap-2.5">
                  {/* Step bubble */}
                  <div
                    className={cn(
                      "flex h-8 w-8 items-center justify-center rounded-xl text-xs font-semibold transition-all shrink-0",
                      isDone
                        ? "bg-olive-600 text-white shadow-sm"
                        : isCurrent
                        ? "bg-olive-500 text-white ring-2 ring-olive-200 shadow-sm"
                        : "bg-stone-100 text-stone-400"
                    )}
                  >
                    {isDone ? <Check className="h-4 w-4" /> : s.id}
                  </div>
                  {/* Step label */}
                  <span
                    className={cn(
                      "text-xs sm:text-sm font-medium hidden sm:inline",
                      isCurrent
                        ? "text-olive-700 font-semibold"
                        : isDone
                        ? "text-charcoal-900"
                        : "text-stone-400"
                    )}
                  >
                    {s.title}
                  </span>
                </div>
                {/* Connector line */}
                {idx < STEPS.length - 1 && (
                  <div
                    className={cn(
                      "mx-4 h-0.5 flex-1 transition-all",
                      isDone ? "bg-olive-400" : "bg-stone-200"
                    )}
                  />
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* ── STEP 1: Role Details ── */}
      {currentStep === 1 && (
        <Card>
          <CardHeader>
            <CardTitle>Role details</CardTitle>
            <CardDescription>
              Describe the position. You can paste a job description and we'll suggest evaluation criteria for you.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            {/* Workflow mode selector */}
            {existingSessions.length > 0 && (
              <div className="rounded-lg border border-stone-200 bg-stone-50 p-4 space-y-3">
                <p className="text-xs font-medium text-stone-500 uppercase tracking-wide">Workflow</p>
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setCreationMode("new")}
                    className={cn(
                      "px-4 py-1.5 rounded-full text-sm font-medium transition-all",
                      creationMode === "new"
                        ? "bg-olive-500 text-white"
                        : "bg-stone-100 text-stone-600 hover:bg-stone-200"
                    )}
                  >
                    Create new
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setCreationMode("existing");
                      if (!selectedExistingId && existingSessions.length > 0) {
                        setSelectedExistingId(existingSessions[0].id);
                      }
                    }}
                    className={cn(
                      "px-4 py-1.5 rounded-full text-sm font-medium transition-all",
                      creationMode === "existing"
                        ? "bg-olive-500 text-white"
                        : "bg-stone-100 text-stone-600 hover:bg-stone-200"
                    )}
                  >
                    Continue existing ({existingSessions.length})
                  </button>
                </div>

                {creationMode === "existing" && (
                  <div className="pt-3 border-t border-stone-200 space-y-3">
                    <p className="text-xs text-stone-500">
                      Select an existing screening to upload more resumes or re-run scoring without creating a new session.
                    </p>
                    <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
                      <select
                        value={selectedExistingId}
                        onChange={(e) => setSelectedExistingId(e.target.value)}
                        className="flex-1 rounded-lg border border-stone-200 bg-white px-3.5 py-2 text-sm text-stone-800 focus:border-olive-500 focus:outline-none"
                      >
                        {existingSessions.map((s) => (
                          <option key={s.id} value={s.id}>
                            {s.session_name || s.job_title || s.title || "Screening"} ({s.candidate_count ?? s.resume_count ?? 0} resumes) — {s.status}
                          </option>
                        ))}
                      </select>
                      <Button
                        type="button"
                        variant="primary"
                        size="sm"
                        disabled={!selectedExistingId}
                        onClick={() => router.push(`/screenings/${selectedExistingId}`)}
                        rightIcon={<ArrowRight className="h-3.5 w-3.5" />}
                      >
                        Open workspace
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Role title + Level */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="sm:col-span-2">
                <label className="block text-sm font-medium text-stone-700 mb-1.5">
                  Position title
                </label>
                <input
                  type="text"
                  placeholder="e.g. Senior Machine Learning Engineer"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="w-full rounded-lg border border-stone-200 bg-white px-3.5 py-2 text-sm text-stone-800 placeholder-stone-400 focus:border-olive-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-stone-700 mb-1.5">
                  Level
                </label>
                <select
                  value={seniority}
                  onChange={(e) => setSeniority(e.target.value)}
                  className="w-full rounded-lg border border-stone-200 bg-white px-3.5 py-2 text-sm text-stone-800 focus:border-olive-500 focus:outline-none"
                >
                  <option value="Junior">Junior (0–2 yrs)</option>
                  <option value="Mid">Mid-Level (2–5 yrs)</option>
                  <option value="Senior">Senior (5+ yrs)</option>
                  <option value="Lead">Staff / Principal / Lead</option>
                </select>
              </div>
            </div>

            {/* JD textarea */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <div>
                  <label className="block text-sm font-medium text-stone-700">
                    Job description <span className="text-stone-400 font-normal">(optional)</span>
                  </label>
                  <p className="text-xs text-stone-400 mt-0.5">Paste the job posting to auto-suggest criteria</p>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  isLoading={isExtractingJd}
                  onClick={handleAutoExtractJd}
                  leftIcon={<Sparkles className="h-3.5 w-3.5 text-olive-600" />}
                  className="text-xs text-olive-700 hover:text-olive-800 hover:bg-olive-50"
                >
                  Suggest criteria
                </Button>
              </div>
              <textarea
                rows={6}
                placeholder="Paste the job posting here..."
                value={jdText}
                onChange={(e) => setJdText(e.target.value)}
                className="w-full rounded-lg border border-stone-200 bg-white p-3.5 text-sm text-stone-800 placeholder-stone-400 focus:border-olive-500 focus:outline-none leading-relaxed resize-none"
              />
            </div>
          </CardContent>
          <CardFooter className="justify-end">
            <Button
              variant="primary"
              size="md"
              onClick={handleProceedFromStep1}
              rightIcon={<ArrowRight className="h-4 w-4" />}
            >
              Continue
            </Button>
          </CardFooter>
        </Card>
      )}

      {/* ── STEP 2: Evaluation Criteria ── */}
      {currentStep === 2 && (
        <Card>
          <CardHeader className="flex flex-row items-start justify-between gap-4">
            <div>
              <CardTitle>Evaluation criteria</CardTitle>
              <CardDescription>
                Set the requirements you'll score candidates against. Weights determine how much each criterion counts toward the final score.
              </CardDescription>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <Button variant="outline" size="sm" onClick={normalizeWeights}>
                Balance weights
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={handleAddCriterion}
                leftIcon={<Plus className="h-3.5 w-3.5" />}
              >
                Add criterion
              </Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            {criteria.map((c, index) => (
              <div
                key={index}
                className="rounded-lg border border-stone-200 bg-stone-100 p-4 space-y-3"
              >
                {/* Name + type + delete */}
                <div className="flex items-center justify-between gap-3">
                  <input
                    type="text"
                    value={c.name}
                    onChange={(e) => handleCriterionChange(index, "name", e.target.value)}
                    placeholder="Criterion name..."
                    className="flex-1 rounded-md border border-stone-200 bg-white px-3 py-1.5 text-sm font-medium text-stone-800 focus:border-olive-500 focus:outline-none"
                  />
                  <select
                    value={c.criterion_type}
                    onChange={(e) => handleCriterionChange(index, "criterion_type", e.target.value)}
                    className="rounded-md border border-stone-200 bg-white px-3 py-1.5 text-xs text-stone-700 focus:border-olive-500 focus:outline-none"
                  >
                    <option value="skill">Skill</option>
                    <option value="experience">Experience</option>
                    <option value="education">Education</option>
                    <option value="custom">Custom</option>
                  </select>
                  <button
                    onClick={() => handleRemoveCriterion(index)}
                    className="p-1.5 text-stone-300 hover:text-terracotta-600 transition-colors"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>

                {/* Description */}
                <input
                  type="text"
                  value={c.description || ""}
                  onChange={(e) => handleCriterionChange(index, "description", e.target.value)}
                  placeholder="What should evaluators look for?"
                  className="w-full rounded-md border border-stone-200 bg-white px-3 py-1.5 text-xs text-stone-600 placeholder-stone-400 focus:border-olive-500 focus:outline-none"
                />

                {/* Sliders + checkbox */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-1 items-center">
                  {/* Importance */}
                  <div>
                    <div className="flex justify-between text-xs text-stone-500 mb-1">
                      <span>Importance</span>
                      <span className="font-semibold text-stone-700">{c.weight}</span>
                    </div>
                    <input
                      type="range"
                      min={0.05}
                      max={1.0}
                      step={0.05}
                      value={c.weight}
                      onChange={(e) =>
                        handleCriterionChange(index, "weight", parseFloat(e.target.value))
                      }
                      className="w-full accent-olive-500"
                    />
                  </div>

                  {/* Minimum score */}
                  <div>
                    <div className="flex justify-between text-xs text-stone-500 mb-1">
                      <span>Minimum score</span>
                      <span className="font-semibold text-stone-700">{c.min_score ?? 50}%</span>
                    </div>
                    <input
                      type="range"
                      min={10}
                      max={90}
                      step={5}
                      value={c.min_score ?? 50}
                      onChange={(e) =>
                        handleCriterionChange(index, "min_score", parseInt(e.target.value))
                      }
                      className="w-full accent-olive-500"
                    />
                  </div>

                  {/* Must meet minimum */}
                  <div className="flex items-center gap-2 sm:justify-end">
                    <label className="flex items-center gap-2 text-xs text-stone-600 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={c.is_required}
                        onChange={(e) =>
                          handleCriterionChange(index, "is_required", e.target.checked)
                        }
                        className="rounded border-stone-300 text-olive-600 focus:ring-olive-500/20 focus:ring-0"
                      />
                      <span>Must meet minimum</span>
                    </label>
                  </div>
                </div>
              </div>
            ))}
          </CardContent>
          <CardFooter className="justify-between">
            <Button
              variant="outline"
              size="md"
              onClick={() => setCurrentStep(1)}
              leftIcon={<ArrowLeft className="h-4 w-4" />}
            >
              Back
            </Button>
            <Button
              variant="primary"
              size="md"
              onClick={handleProceedFromStep2}
              rightIcon={<ArrowRight className="h-4 w-4" />}
            >
              Continue
            </Button>
          </CardFooter>
        </Card>
      )}

      {/* ── STEP 3: Resume Upload ── */}
      {currentStep === 3 && (
        <Card>
          <CardHeader>
            <CardTitle>Upload resumes</CardTitle>
            <CardDescription>
              Upload PDF, DOCX, or TXT files. You can add up to 100 resumes per session.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {uploadError && (
              <div className="rounded-lg border border-terracotta-200 bg-terracotta-50 p-3 text-sm text-terracotta-700 flex items-center gap-2">
                <AlertCircle className="h-4 w-4 shrink-0" />
                <span>{uploadError}</span>
              </div>
            )}

            {/* Drop zone */}
            <div className="relative border-2 border-dashed border-stone-300 hover:border-olive-500 bg-[#FAF9F6] hover:bg-[#F2EFE9] rounded-2xl p-10 text-center transition-all group">
              <input
                type="file"
                multiple
                accept=".pdf,.docx,.txt"
                onChange={handleFileChange}
                className="absolute inset-0 opacity-0 cursor-pointer w-full h-full z-10"
              />
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-white border border-stone-300 text-stone-400 group-hover:text-olive-700 group-hover:scale-105 transition-all mx-auto mb-3 shadow-subtle">
                <UploadCloud className="h-6 w-6" />
              </div>
              <h3 className="text-sm font-semibold text-stone-900">
                Drop resume files here, or click to browse
              </h3>
              <p className="text-xs text-stone-500 mt-1">
                Supports PDF, DOCX, and TXT — up to 100 files per screening batch
              </p>
            </div>

            {/* File list & Live Capacity Meter */}
            {files.length > 0 && (
              <div className="rounded-xl border border-stone-300 bg-white p-4 shadow-subtle space-y-3">
                <div className="flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-stone-900">
                      {files.length} file{files.length !== 1 ? "s" : ""} selected
                    </span>
                    <span className="text-stone-400 font-mono text-[11px]">
                      ({(files.length / 100 * 100).toFixed(0)}% batch capacity)
                    </span>
                  </div>
                  <button
                    onClick={() => setFiles([])}
                    className="text-stone-400 hover:text-terracotta-600 transition-colors text-xs font-medium"
                  >
                    Clear all
                  </button>
                </div>

                {/* Batch capacity progress bar */}
                <div className="h-1.5 w-full bg-stone-100 rounded-full overflow-hidden">
                  <div
                    className={cn(
                      "h-full rounded-full transition-all duration-300",
                      files.length > 90 ? "bg-stone-500" : "bg-olive-600"
                    )}
                    style={{ width: `${Math.min(files.length, 100)}%` }}
                  />
                </div>

                <div className="max-h-48 overflow-y-auto space-y-1.5 pr-1">
                  {files.map((file, idx) => (
                    <div
                      key={idx}
                      className="flex items-center justify-between text-xs p-2 rounded-lg border border-stone-200 bg-[#FAF9F6]"
                    >
                      <div className="flex items-center gap-2 truncate">
                        <CheckCircle2 className="h-3.5 w-3.5 text-olive-600 shrink-0" />
                        <span className="text-stone-900 truncate font-medium">{file.name}</span>
                      </div>
                      <span className="text-stone-400 shrink-0 ml-2 font-mono text-[11px]">
                        {(file.size / 1024).toFixed(1)} KB
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
          <CardFooter className="justify-between">
            <Button
              variant="outline"
              size="md"
              onClick={() => setCurrentStep(2)}
              leftIcon={<ArrowLeft className="h-4 w-4" />}
            >
              Back
            </Button>
            <Button
              variant="primary"
              size="md"
              isLoading={isUploading}
              disabled={files.length === 0}
              onClick={handleProceedFromStep3}
              rightIcon={<ArrowRight className="h-4 w-4" />}
            >
              Upload {files.length > 0 ? `${files.length} file${files.length !== 1 ? "s" : ""}` : ""} and continue
            </Button>
          </CardFooter>
        </Card>
      )}

      {/* ── STEP 4: Run Evaluation ── */}
      {currentStep === 4 && (
        <Card>
          <CardHeader>
            <CardTitle>Ready to score</CardTitle>
            <CardDescription>
              We'll analyse each resume against your criteria and produce ranked scores with supporting evidence.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6 py-6">
            <div className="rounded-lg border border-stone-200 bg-stone-50 p-8 text-center space-y-4">
              {/* Icon */}
              <div className="flex justify-center">
                <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-stone-100">
                  {isProcessing ? (
                    <Loader2 className="h-8 w-8 text-olive-600 animate-spin" />
                  ) : (
                    <FileSearch className="h-8 w-8 text-stone-400" />
                  )}
                </div>
              </div>

              {/* Status text */}
              <div>
                <h3 className="text-base font-semibold text-stone-800">
                  {isProcessing ? "Scoring in progress…" : "Start scoring when you're ready."}
                </h3>
                <p className="text-sm text-stone-500 mt-1 max-w-md mx-auto">
                  {processStatus}
                </p>
              </div>

              {/* Progress bar */}
              {isProcessing && (
                <div className="max-w-md mx-auto w-full">
                  <ProgressBar value={processProgress} size="md" colorScheme="score" />
                </div>
              )}

              {/* Start button */}
              {!isProcessing && (
                <div className="flex justify-center pt-2">
                  <Button
                    variant="primary"
                    size="lg"
                    onClick={handleExecuteEvaluation}
                    leftIcon={<Play className="h-4 w-4" />}
                  >
                    Start evaluation
                  </Button>
                </div>
              )}
            </div>
          </CardContent>
          <CardFooter className="justify-between">
            <Button
              variant="outline"
              size="md"
              disabled={isProcessing}
              onClick={() => setCurrentStep(3)}
              leftIcon={<ArrowLeft className="h-4 w-4" />}
            >
              Back
            </Button>
          </CardFooter>
        </Card>
      )}
    </div>
  );
}
