# HireMatch – AI-Powered Multi-Layer Resume Screening & Recruitment Analytics

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/)
[![Next.js 14](https://img.shields.io/badge/next.js-14.2-black.svg)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/fastapi-1.0.0-009688.svg)](https://fastapi.tiangolo.com/)
[![Tests Passing](https://img.shields.io/badge/tests-187%20passed-success.svg)]()

**HireMatch** is an explainable, multi-layer candidate screening and recruitment analytics platform designed to evaluate candidate resumes across orthogonal dimensions beyond basic keyword matching.

The application serves as a **recruitment decision-support system**, not an automated hiring/rejection engine. Final decisions always remain with the human recruiter.

---

## 1. System Features & Capabilities

### Resume Quality Assessment (Independent Document Evaluation)
- **10-Criterion Quality Rubric**: Evaluates resume document quality independently from job qualification:
  1. *Completeness* — presence of contact info, summary, experience, education, and skills.
  2. *Structure & organization* — logical layout and clear section hierarchy.
  3. *Readability* — concise descriptions, clear sentence structure.
  4. *Formatting consistency* — consistent headings, spacing, dates, and bullet points.
  5. *Experience clarity* — clear roles, organizations, and responsibilities.
  6. *Skills clarity* — transparent presentation of technical and professional skills.
  7. *Achievement specificity* — quantifiable contributions and impact metrics.
  8. *Date consistency* — coherent employment/education timelines; undated tenures are overlooked without penalizing candidates.
  9. *Contact completeness* — sufficient professional identifying information without penalizing privacy.
  10. *Extraction quality* — reliability of text extraction and parsed structure.
- **Configurable Quality Labels**: 
  - **Good Quality**: 75–100 (`bg-emerald-600` progress bar, emerald badge)
  - **Moderate Quality**: 50–74 (`bg-amber-500` progress bar, amber badge)
  - **Poor Quality**: 0–49 (`bg-rose-500` progress bar, rose badge)
- **Decoupled Match & Quality Signals**: Resume Quality Score ($0–100$) is strictly decoupled from the candidate's job-match Composite Score ($0–100$). Document formatting does not alter job suitability rankings.
- **Responsible AI Interpretation Notice**: Prominently presented across the UI and exports: *"Resume quality reflects how clearly and consistently the submitted resume communicates its information. It is separate from the candidate's match score. Resume quality is NOT candidate quality."*

---

### Core Processing & Evaluation Engine

- **Domain-Agnostic Extraction**: Candidate profile extraction operates 100% domain-agnostically across technical, business, creative, and operational roles without hardcoding specific titles or test-dataset heuristics.
- **Multi-Format Document Extractors (`core/processing/`)**: Page-by-page PDF extraction with `PyMuPDF`, table/paragraph DOCX extraction with `python-docx`, text normalization (Unicode NFKC, technical token preservation like `C++`, `CI/CD`, `.NET`), and scanned image detection.
- **Noise-Free Timeline & Anomaly Detection (`core/evaluation/discrepancy_detector.py`)**:
  - Undated work experience entries are cleanly skipped during discrepancy auditing, preventing false alarms.
  - Flags highlight only verified anomalies: acute career gaps (>9 months), overlapping concurrent roles (>90 days), unmet mandatory criteria, and uncorroborated skill claims.
- **5-Layer Evaluation Architecture**:
  1. *Layer 1: Structured Data Parsing* — extraction of contact information, employment history, education, and skills.
  2. *Layer 2: Baseline Keyword & Rule Matching* — section-weighted exact and alias matching with negation guards (*"no experience with AWS"*).
  3. *Layer 3: Dense Semantic AI Matching* — sentence-transformers passage embeddings (`all-MiniLM-L6-v2`) with qualitative cosine similarity tiers (`STRONG` $\ge 0.70$, `POSSIBLE` $0.50–0.69$, `WEAK` $0.35–0.49$, `INSUFFICIENT` $< 0.35$).
  4. *Layer 4: Evidence Synthesis & Conflict Detection* — cross-layer agreement validation and conflict isolation.
  5. *Layer 5: Governance & Neutrality Audits* — blocks prohibited demographic traits (age, gender, race, photos, subjective "culture fit").
- **Deterministic Scoring & Ranking (`core/scoring/`)**:
  - Dynamic weight normalization over eligible criteria.
  - Decoupled sub-second recalculation without re-running document parsing or neural inference.
  - Multi-attribute tie handling: Standard Competition (`1224`), Dense (`1223`), and Ordinal (`1234`).
  - Incomplete candidate isolation (`rank = 0`) segregated at the manifest bottom.
- **Privacy by Design & PII Quarantine**: Contact details (`name`, `email`, `phone`, `address`) are masked by default (`Cand-[HASH:8]`, `[PROTECTED - PII QUARANTINE]`) and exposed only through explicit recruiter authorization.

---

### Web Application & User Interfaces

Built with **Next.js 14 (App Router)** and **Tailwind CSS**:

- **Executive Recruitment Dashboard (`/`)**: Real-time database metrics (sessions, candidates, active requisitions, average composite match score) and interactive recent activity feed.
- **Screening Requisitions List (`/screenings`)**: Management view of all screening sessions with search, status filters, candidate counts, and deletion controls.
- **New Requisition Wizard (`/screenings/new`)**: Step-by-step requisition creator with file upload supporting up to 100 resumes per batch, drag-and-drop zone, and live capacity meter.
- **Requisition Workspace (`/screenings/[sessionId]`)**: Candidate ranking manifest ($1 \dots N$), quick status filters (Shortlisted, In Review, Needs Review, Rejected), fit tier badges, composite score vs. resume quality score comparison, and CSV shortlist export.
- **In-Session Candidate Comparison (`/screenings/[sessionId]/compare`)**: Direct side-by-side comparison for 2–5 selected candidates within the same requisition, displaying criteria score deltas and qualifications.
- **Live Sensitivity Simulator (`/screenings/[sessionId]/simulator`)**: Interactive criterion weight sliders that simulate non-mutating candidate rank deltas ($\pm N$) in real time.
- **Requisition Analytics (`/screenings/[sessionId]/analytics`)**: In-session candidate pipeline funnel, tier distribution charts, and skill coverage metrics.
- **Candidate Evidence Dossier (`/candidates/[candidateId]`)**:
  - Interactive tabs: *Role criteria match*, *Resume quality* (10-criterion breakdown, strengths, areas for improvement), *Flags & anomalies*, and *Resume details*.
  - Verbatim quote citations linked directly to job criteria.
  - Recruiter review controls (`SHORTLISTED`, `IN_REVIEW`, `NEEDS_REVIEW`, `NOT_SHORTLISTED`, `ON_HOLD`) with immutable timestamps.
- **Business Analytics & Model Lab (`/business-analytics`)**:
  - *Pre-Trained Models*: Catalog of embedding and cross-encoder architectures, technical specifications, and benchmarks.
  - *AI Model Lab*: On-demand model benchmarking with latency, throughput, peak RAM, ground-truth metrics (NDCG@K, MRR, F1), and pairwise rank correlation ($\tau$).
  - *Portfolio Health*: Cross-session requisition metrics and processing status distributions.
  - *Skill Coverage & Gaps*: Requisition-level talent pool coverage analysis.
  - *Criterion Variance & Divergence*: Standard deviation analysis and baseline vs. semantic AI divergence.
  - *Traceable Insights*: Rule-grounded analytical summaries with explicit calculation bases.
  - *Multi-Tab Excel Export*: Downloadable `.xlsx` workbook generated via `openpyxl`.
- **Settings & Responsible AI Governance (`/settings`)**: System capacity limits (100 resumes, 10MB per file, 200MB batch), storage paths, and ethical governance rules.

---

## 2. Directory Layout

```
hirematch/
├── backend/                    # FastAPI High-Performance REST API
│   └── app/
│       ├── main.py             # FastAPI application entrypoint & middleware
│       └── api/
│           ├── routes/         # 12 Modular API Route Handlers
│           │   ├── analytics.py    # Portfolio and requisition analytics
│           │   ├── candidates.py   # Candidate ranking, detail, and quality endpoints
│           │   ├── comparison.py   # In-session candidate comparison
│           │   ├── criteria.py     # Evaluation criteria configuration
│           │   ├── health.py       # Health check endpoint (/api/health)
│           │   ├── jobs.py         # Job requisition management
│           │   ├── models.py       # AI model registry & benchmark runner
│           │   ├── reports.py      # PDF, CSV, JSON report export handlers
│           │   ├── screening.py    # Batch upload, extraction, and scoring triggers
│           │   ├── sessions.py     # Screening session CRUD and pagination
│           │   ├── settings.py     # System governance and limits
│           │   └── simulator.py    # Weight sensitivity sandbox
│           ├── schemas/        # Pydantic v2 Request/Response validation schemas
│           └── deps.py         # Dependency injection (Database, Orchestrator, Config)
│
├── frontend/                   # Modern Next.js 14 SaaS Web Application
│   ├── app/                    # Next.js App Router Pages
│   │   ├── page.tsx            # Executive Recruitment Dashboard
│   │   ├── screenings/
│   │   │   ├── page.tsx        # Screening Requisitions List
│   │   │   ├── new/page.tsx    # New Requisition Wizard & Batch Upload
│   │   │   └── [sessionId]/
│   │   │       ├── page.tsx    # Requisition Workspace & Candidate Manifest (1..N)
│   │   │       ├── analytics/  # Requisition Session Analytics & Funnel
│   │   │       ├── compare/    # Side-by-Side Candidate Comparison (2–5 candidates)
│   │   │       └── simulator/  # Live Criterion Weight Sensitivity Sandbox
│   │   ├── candidates/
│   │   │   └── [candidateId]/  # Evidence Dossier, Quality Rubric & Review Controls
│   │   ├── business-analytics/ # Business Analytics & Pretrained Model Lab
│   │   └── settings/           # Ethics, Governance & System Architecture
│   ├── components/             # Reusable UI component system
│   │   ├── layout/AppShell.tsx # Navigation Shell & Health Indicator
│   │   └── ui/                 # Button, Badge, Card, StatCard, ProgressBar, Modal, Tabs
│   ├── lib/api/client.ts       # Typed unified HTTP API client
│   └── lib/types/api.ts        # TypeScript API data contracts
│
├── core/                       # Core domain and business logic
│   ├── models/                 # Typed domain entities, enums & resume quality models
│   ├── storage/                # SQLite database (WAL mode) and repository DAOs
│   ├── processing/             # Document extractors, text cleaning, and section parsers
│   ├── evaluation/             # Discrepancy detector, embeddings, scoring engine, quality evaluator
│   ├── scoring/                # Deterministic calculator, ranker, and shortlist service
│   ├── analytics/              # Portfolio, skill coverage, criterion variance services
│   ├── model_lab/              # Model registry, benchmarking runner, and metric calculations
│   ├── reporting/              # Vector PDF, CSV, and XLSX export generators
│   ├── services/               # Screening orchestrator, criteria validator, model manager
│   └── utils/                  # Cryptographic hashing, errors, and structured logging
│
├── data/                       # Local data storage
│   ├── hirematch.db            # SQLite database (WAL mode with foreign keys)
│   ├── storage/                # Stored resume documents
│   ├── cache/                  # Model weights cache
│   └── temp/                   # Temporary processing files
│
└── tests/                      # Automated quality gate test suite (187 tests across 20 suites)
```

---

## 3. Configuration Reference & Limits

All settings can be configured via environment variables or a `.env` file:

| Setting | Default Value | Description |
| :--- | :--- | :--- |
| `HIREMATCH_MAX_RESUMES_PER_SESSION` | `100` | Hard session cap on candidate resumes per screening batch. |
| `HIREMATCH_MAX_FILE_SIZE_BYTES` | `10,485,760` (10 MB) | Maximum size allowed for an individual resume file. |
| `HIREMATCH_MAX_TOTAL_UPLOAD_SIZE_BYTES` | `209,715,200` (200 MB) | Maximum aggregate upload size allowed per batch. |
| `HIREMATCH_PROCESSING_BATCH_SIZE` | `10` | Resumes processed per batch chunk during background execution. |
| `HIREMATCH_DB_PATH` | `data/hirematch.db` | File path to SQLite database. |
| `HIREMATCH_STORAGE_DIR` | `data/storage` | Local directory for storing uploaded resume files. |
| `HIREMATCH_LOG_LEVEL` | `INFO` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |
| `HIREMATCH_SEMANTIC_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Default pretrained semantic embedding model. |

---

## 4. Setup and Installation

### Prerequisites:
- **Python 3.11+**
- **Node.js 18+** (Node 20+ recommended) & npm

### Backend Setup:
```bash
# 1. Activate virtual environment
# Windows (PowerShell / Command Prompt):
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# 2. Install backend dependencies
pip install -r requirements.txt
```

### Frontend Setup:
```bash
cd frontend
npm install
npm run build
cd ..
```

---

## 5. Running the Application

### Option A: Unified Launcher (Recommended)
Run both the FastAPI backend and Next.js frontend concurrently with automated port management (clearing stale listeners on `:8000` and `:3000`), environment pre-flight checks, and graceful shutdown:
```bash
python run.py
```
- **Frontend Web UI**: `http://localhost:3000`
- **New Requisition Wizard**: `http://localhost:3000/screenings/new`
- **Backend REST API**: `http://127.0.0.1:8000`
- **Swagger Documentation**: `http://127.0.0.1:8000/docs`
- **Health Check**: `http://127.0.0.1:8000/api/health`

### Option B: Manual Service Launch
In Terminal 1 (FastAPI Backend):
```bash
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```
In Terminal 2 (Next.js Frontend):
```bash
cd frontend
npm run start # (or 'npm run dev' for development hot-reloading)
```

---

## 6. Running Automated Tests

Run the full quality gate test suite using `pytest`:

```bash
# Run all tests with verbose output:
python -m pytest tests/ -v

# Run targeted test suites:
python -m pytest tests/test_resume_quality.py -v
python -m pytest tests/test_scoring_and_shortlisting.py -v
python -m pytest tests/test_semantic_matching.py -v
python -m pytest tests/test_final_acceptance.py -v
```

### Test Coverage Highlights:
- **187 Automated Tests Passed (100% Green Across All 20 Test Suites)**:
  - `test_config`, `test_models`, `test_database`, `test_file_validation`, `test_orchestrator`: Core architecture, SQLite persistence, and 100-resume cap enforcement.
  - `test_document_processing`: PDF/DOCX extractors, text cleaning, section detection, skill normalization, and structured resume parsing.
  - `test_baseline_matching`: Section-aware keyword matching, negation detection, experience deduplication, and credential hierarchies.
  - `test_semantic_matching`: Dense embeddings, SQLite vector caching, passage chunking, cosine tiers, and hybrid scoring.
  - `test_multi_layer_evaluation`: 5-layer evaluation, responsible AI criteria validation, and cross-layer conflict synthesis.
  - `test_scoring_and_shortlisting`: Transparent score calculation, missing evidence policies, deterministic ranking, tie strategies, and sensitivity simulation.
  - `test_resume_quality`: 10-criterion rubric scoring, quality label thresholds (Good/Moderate/Poor), score decoupling verification, and synthetic resume tests.
  - `test_reporting_and_comparison`: Pure record retrieval, PII quarantine, comparison compatibility, PDF/CSV/XLSX exports, and recruitment insights.
  - `test_business_analytics`: Portfolio health, skill gap heatmaps, criterion variance & divergence, traceable insights, and Excel/CSV exporters.
  - `test_model_lab`: Model registry, on-demand loading & RAM release, evaluation dataset freezing, reference metrics (Precision/Recall/NDCG/MRR), pairwise concordance (Kendall's Tau), descriptive dispersion, and benchmark runner persistence.
  - `test_api_endpoints`: Complete FastAPI REST API endpoint validation, candidate pagination, comparison, simulator, and reports.
  - `test_batch_robustness`: Batch processing limits (100 resumes, 10MB file, 200MB total), corrupted upload isolation, and transactional stability.
  - `test_adversarial_robustness`: Prompt-injection defense, white-text attack mitigation, keyword stuffing defenses, and negation guards.
  - `test_scoring_robustness`: Extreme weight vectors, missing evidence handling, tenure outliers, and score boundedness.
  - `test_responsible_ai_and_security`: Absence of automated rejection, demographic neutrality, PII quarantine, and path traversal sanitization.
  - `test_end_to_end_workflows`: 10-stage simulation of complete recruiter journey.
  - `test_final_acceptance`: 18-step acceptance test scenario verifying end-to-end integration and data integrity.

---

## 7. Project Documentation Index

Comprehensive documentation for architecture evaluation and deployment:

| Document | Description |
| :--- | :--- |
| [`docs/project_overview.md`](docs/project_overview.md) | Problem statement, research context, core objectives, and ethical boundaries. |
| [`docs/system_architecture.md`](docs/system_architecture.md) | Architectural blueprint, subsystem specifications, and Mermaid data pipeline. |
| [`docs/ai_methodology.md`](docs/ai_methodology.md) | NLP text normalization, 3-layer matching mechanics, cosine calibration, and scoring math. |
| [`docs/database_documentation.md`](docs/database_documentation.md) | SQLite relational schema, ERD, table definitions, indexes, and backup/recovery. |
| [`docs/user_guide.md`](docs/user_guide.md) | Recruiter manual, navigation guide, score interpretation rubric, and FAQ. |
| [`docs/demonstration_guide.md`](docs/demonstration_guide.md) | Demonstration scripts, persona walkthroughs, and fallback procedures. |
| [`docs/performance_telemetry.json`](docs/performance_telemetry.json) | Real benchmark profiling metrics (25 resumes on CPU, peak RAM 596.5 MB, 30.82s runtime). |
| [`docs/responsible_ai_guide.md`](docs/responsible_ai_guide.md) | Ethical guidelines, demographic agnosticism, and human-in-the-loop governance. |
