# HireMatch – System Architecture & Module Guide (Phase 1)

## 1. System Overview

**HireMatch** is an explainable, multi-layer candidate screening and recruitment analytics platform. It replaces opaque "AI black-box" scoring with transparent, evidence-linked criteria evaluation.

In Phase 1, we establish a robust, modular, and scalable software architecture designed for:
- Batch ingestion of **up to 100 resumes per screening session**.
- Strict validation, cryptographic duplicate detection (SHA-256), and failure isolation.
- Fast, local persistence via SQLite with WAL mode and foreign key constraints.
- Clear abstract interfaces for NLP models, extraction, multi-layer evaluation, and analytics.

---

## 2. Architectural Blueprint

```
HireMatch/
├── app.py                      # Main Streamlit dashboard application
├── config.py                   # Centralized, strongly-typed configuration
├── requirements.txt            # Dependency specifications
├── .env.example                # Environment variable template
├── .gitignore                  # Git ignore rules
│
├── core/                       # Core business logic (UI independent)
│   ├── models/                 # Validated domain entities & enums
│   │   ├── enums.py            # Status, criteria, and model type enums
│   │   ├── job.py              # Job model with parsed requirements
│   │   ├── candidate.py        # Candidate resume model & hash
│   │   ├── session.py          # ScreeningSession with 100-resume limit
│   │   ├── skills.py           # ExtractedSkill with evidence citation
│   │   ├── experience.py       # WorkExperience model
│   │   ├── education.py        # EducationRecord model
│   │   ├── evaluation.py       # EvaluationCriterion, Evidence, Score
│   │   └── model_config.py     # NLP model configuration metadata
│   │
│   ├── storage/                # Persistence & Data Access Layer
│   │   ├── database.py         # SQLite connection manager & DDL schema
│   │   └── repositories.py     # Job, Session, Candidate, Score DAOs
│   │
│   ├── processing/             # Document Ingestion & Parsing
│   │   ├── extractor.py        # PyMuPDF and DOCX text extractors
│   │   └── jd_parser.py        # Baseline Job Description parser
│   │
│   ├── evaluation/             # Evaluation Layer Interfaces
│   │   └── interfaces.py       # Contracts for Quality Gate, Skills, Semantic Match
│   │
│   ├── analytics/              # Analytics & Benchmarks Interfaces
│   │   └── interfaces.py       # Contracts for Coverage, Reports, Benchmarks
│   │
│   ├── services/               # Orchestration & Validation Services
│   │   ├── file_validator.py   # Extension, size, and header checks
│   │   ├── model_manager.py    # NLP model catalog & memory cache
│   │   └── session_orchestrator.py # Session lifecycle & 100-resume enforcement
│   │
│   └── utils/                  # Shared Helpers
│       ├── errors.py           # Custom exception hierarchy
│       ├── hashing.py          # SHA-256 cryptographic duplicate detection
│       └── logger.py           # Structured application logger
│
├── components/                 # Streamlit UI Components
│   └── header.py               # Reusable header and system health cards
│
├── docs/                       # Technical Documentation
│   └── architecture.md         # This document
│
└── tests/                      # Automated Test Suite (29 unit tests)
    ├── test_config.py          # Configuration loading & validation tests
    ├── test_models.py          # Domain model validation tests
    ├── test_database.py        # SQLite schema & repository CRUD tests
    ├── test_file_validation.py  # File format, size, & header signature tests
    └── test_orchestrator.py    # 100-resume cap, duplicates, & failure isolation tests
```

---

## 3. Data Storage & Schema Design

HireMatch utilizes an embedded SQLite database (`data/hirematch.db`) with Write-Ahead Logging (`PRAGMA journal_mode = WAL`) and foreign key constraints enabled.

### Database Tables:
1. `jobs`: Stores job postings, descriptions, and structured requirement JSONs.
2. `screening_sessions`: Manages screening runs, job associations, status, candidate counts, and progress metadata.
3. `candidates`: Stores unique candidate files by SHA-256 hash, extracted text, and storage paths.
4. `session_candidates`: Junction table linking candidates to sessions, maintaining session-specific states (`PENDING`, `EXTRACTING`, `COMPLETED`, `FAILED`, `DUPLICATE`).
5. `extracted_skills`: Normalized candidate skills with verbatim evidence citations.
6. `work_experience`: Extracted roles, employers, dates, and descriptions.
7. `education_records`: Academic qualifications and institutions.
8. `evaluation_criteria`: Configurable job criteria with assigned weights.
9. `evaluation_evidence`: Verbatim candidate evidence mapped to evaluation criteria.
10. `candidate_scores`: Calculated scores, breakdowns, and explanations.

### Large Text Separation:
Raw resume files are stored on disk in `data/storage/{hash[:2]}/{hash}_{filename}` rather than bloating database rows, keeping database queries fast and lightweight.

---

## 4. Key Orchestration Mechanisms

### A. The 100-Resume Session Limit
- Enforced at both the domain model (`ScreeningSession.max_resume_count = 100`) and the service layer (`ScreeningOrchestrator.add_resumes_to_session`).
- If an upload attempts to exceed 100 resumes (either all at once or incrementally), a `SessionLimitExceededError` is raised with a clear user explanation.

### B. Duplicate Resume Detection
- Every uploaded document is hashed using SHA-256 (`compute_file_hash`).
- If an identical resume is uploaded multiple times in the same session, it is flagged as `DUPLICATE` without creating redundant processing work.

### C. Failure Isolation
- A corrupted file or invalid format does **not** fail the entire session.
- The invalid file is recorded with status `FAILED` and an error diagnostic, while all valid resumes in the batch continue processing normally.

### D. Idempotent Batch Processing
- Resumes are processed in configurable chunks (`processing_batch_size = 10`).
- Processing queries only `PENDING` items, allowing safe retries and resume ingestion without duplicate effort.
