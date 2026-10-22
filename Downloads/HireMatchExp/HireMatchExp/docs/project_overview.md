# HireMatch: Project Overview & Academic Problem Statement

## 1. Academic & Industry Context

Modern recruitment workflows are overwhelmed by high application volumes. In response, modern organizations have widely adopted automated Applicant Tracking Systems (ATS). However, the vast majority of commercial screening tools operate as either:

1. **Brittle Keyword Matchers**: Naively scanning for verbatim lexical tokens (e.g., regex pattern matching for "Python" or "AWS"), which penalizes qualified candidates who use differing terminology and invites adversarial manipulation through "keyword stuffing" or hidden white-text injection.
2. **Opaque Black-Box Predictive Models**: Employing end-to-end deep learning or generative AI models to output uncalibrated, unexplainable "match scores" or autonomous hire/reject recommendations. Such systems obscure the reasoning behind evaluations, encode historical hiring biases, and present severe legal, compliance, and ethical liabilities under modern AI regulatory frameworks (e.g., the EU AI Act High-Risk AI System classifications, EEOC guidance, and NYC Local Law 144).

**HireMatch** was engineered to address this dilemma. It bridges the gap between brittle keyword filters and unaccountable deep-learning black boxes by introducing a **multi-layer, evidence-based, decision-support architecture**.

---

## 2. Core Objectives

HireMatch is structured around four primary engineering objectives:

* **Objective 1: Transparent Multi-Layer Evaluation**: Break evaluation down into granular, auditable layers—Exact Lexical Matching, Normalized Alias Matching, and Semantic Embedding Retrieval—providing verifiable text citations for every scoring contribution.
* **Objective 2: Strict Mathematical Accountability**: Every composite candidate score must be an exact, deterministic weighted sum of explicit criterion contributions ($\text{Score} = \sum w_i \times s_i$). No hidden heuristics or arbitrary adjustments are permitted.
* **Objective 3: Robustness & Adversarial Resilience**: Defend against adversarial resume manipulation (e.g., zero-font white-text injection, repetitive token flooding, repeated JD pasting) through prompt-injection guards, heuristic anomaly detection, and semantic-lexical agreement checks.
* **Objective 4: Responsible AI & Human-in-the-Loop Decision Support**: Guarantee that the software operates solely as an analytical aid. The system defaults candidate statuses to `NEEDS_REVIEW` or `IN_REVIEW`, never automatically rejects applicants, and provides interactive sensitivity simulation without mutating stored historical records.

---

## 3. Ethical Boundaries & Non-Goals

To maintain rigorous scientific and ethical standards, HireMatch explicitly defines what it is **not**:

| Boundary / Non-Goal | HireMatch Guarantee |
| :--- | :--- |
| **No Autonomous Hiring/Rejection** | The system does not possess the authority to reject candidates or extend offers. Status transitions are strictly human-governed. |
| **No Predictive Performance Claims** | HireMatch measures textual evidence alignment between an uploaded resume and an explicit job specification. It does **not** claim to predict on-the-job performance, IQ, culture fit, or career trajectory. |
| **Zero PII in Evaluation Benchmarks** | Benchmark datasets, regression suites, and demonstration assets utilize synthetic, anonymized resumes containing no personally identifiable information (PII). |
| **Protected Demographic Agnosticism** | Evaluators operate solely upon skills, verified experience durations, and degree credentials. Demographic attributes (gender, race, age, nationality) are ignored and protected by input sanitizers. |

---

## 4. System Scope

HireMatch spans the complete end-to-end screening and recruitment lifecycle:

```
[Resume Upload & Validation] 
       │
       ▼
[Text Extraction & Cleaning] 
       │
       ▼
[Section & Entity Extraction] 
       │
       ▼
[Job Description Criteria Modeling] 
       │
       ▼
[Multi-Layer Evidence Alignment] 
   ├─ Exact Lexical Layer
   ├─ Alias & Skill Hierarchy Layer
   └─ Dense Semantic Vector Layer
       │
       ▼
[Transparent Scoring & Ranking] 
       │
       ▼
[Human Recruiter Review & Sensitivity Sandbox] 
       │
       ▼
[Multi-Format Export & Analytics Visualizations]
```

---

## 5. Technology Stack Summary

* **Language & Runtime**: Python 3.11+
* **User Interface**: Streamlit with custom CSS Design System (clean typography, status badges, metric cards)
* **Document Extraction**: PyMuPDF (`fitz`), `python-docx`
* **Embedding & NLP Models**: HuggingFace Sentence Transformers (`sentence-transformers/all-MiniLM-L6-v2`, `all-mpnet-base-v2`, BGE, E5), PyTorch
* **Vector Mathematics**: NumPy, SciPy (Cosine Similarity with support calibration)
* **Database & Persistence**: SQLite3 with foreign key enforcement and atomic transactions
* **Data Export & Reporting**: OpenPyXL (Excel XLSX), Python CSV, ReportLab (PDF)
* **Testing & Quality Assurance**: Standard library `unittest`, parameterized suites, property-based tests
