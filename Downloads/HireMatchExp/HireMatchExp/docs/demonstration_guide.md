# HireMatch: Demonstration Guide & Evaluator Walkthrough

## 1. Executive Summary for Evaluators

HireMatch is an AI-powered, multi-layer resume screening and recruitment decision-support application built in Python and Streamlit.

This guide provides structured demonstration scripts for academic evaluators, technical reviewers, and hiring managers. It includes timing-specific paths (5-minute lightning demo, 10-minute technical evaluation, 20-minute comprehensive walkthrough) and fallback contingency plans.

---

## 2. Preparation Checklist

Before initiating the demonstration:
1. **Pre-flight Diagnostic**:
   ```bash
   python check_system.py
   ```
   *Expected output*: `All system integrity checks passed successfully! (Code 0)`
2. **Launch Application**:
   ```bash
   streamlit run app.py
   ```
3. **Synthetic Demonstration Data**:
   Ensure sample resumes in `synthetic_resumes/` or `tests/fixtures/` are accessible. All demonstration candidates are 100% synthetic (zero PII).

---

## 3. Demonstration Paths

### Path A: 5-Minute Lightning Demo (Executive & High-Level)
*Goal: Showcase the core value proposition of evidence-based screening vs black-box ATS.*

1. **Step 1 (0:00 - 1:00) — Welcome & Problem Framing**:
   * Open `app.py`. Explain the core dilemma: Keyword matchers are brittle; black-box LLMs hallucinate and introduce legal risk. HireMatch solves this via transparent, multi-layer evidence.
2. **Step 2 (1:00 - 2:30) — Ingestion & Criteria**:
   * Navigate to **Criteria & Weights**. Show how a role (e.g., Senior Python Engineer) is decomposed into weighted criteria with normalized contributions.
3. **Step 3 (2:30 - 4:00) — Screening & Evidence Cards**:
   * Navigate to **Candidate Evaluation**. Show the top candidate: expand their **Evidence Card**.
   * Highlight that every score point is backed by a verbatim text citation from the resume, not an opaque number.
4. **Step 4 (4:00 - 5:00) — Responsible AI Invariant**:
   * Point out the status selector: Candidates default to `IN_REVIEW`. The system **never** automatically rejects anyone.

---

### Path B: 10-Minute Technical Evaluation (Faculty / Architecture Review)
*Goal: Prove engineering depth, mathematical integrity, and adversarial resilience.*

1. **Step 1 (0:00 - 2:00) — Architecture & Data Pipeline**:
   * Present the 3-tier clean architecture: UI $\rightarrow$ Orchestrator $\rightarrow$ Multi-Layer Evaluator / Scoring Engine $\rightarrow$ SQLite.
2. **Step 2 (2:00 - 4:30) — Multi-Layer Evaluation Mechanics**:
   * Explain the 3 layers: Layer 1 (Lexical), Layer 2 (Taxonomy/Alias), Layer 3 (Sentence Transformers).
   * Show how an alias like `"K8s"` is recognized via `skills_db.json`, while latent experience phrases are captured via cosine embeddings.
3. **Step 3 (4:30 - 7:00) — Transparent Formula Integrity**:
   * Show `tests/test_final_acceptance.py`:
     $$\text{Overall Score} = \sum w_i \times \text{support}_i$$
   * Demonstrate side-by-side comparison and the in-memory **Sensitivity Sandbox**: adjusting weights updates prospective ranks without mutating stored database records.
4. **Step 4 (7:00 - 8:30) — Adversarial Resilience**:
   * Explain defenses against white-text injection and prompt-injection attacks. Show how negation analysis prevents false positives.
5. **Step 5 (8:30 - 10:00) — Automated Test Suite & Telemetry**:
   * Review `docs/performance_telemetry.json`: 25 full resumes processed end-to-end in 30.82 seconds on CPU.
   * Highlight test coverage across all 20 test modules.

---

### Path C: 20-Minute Deep Dive (Comprehensive Defense / Viva)
*Follows Path B and adds:*
1. **Model Comparison Laboratory (10:00 - 14:00)**:
   * Navigate to **Model Laboratory**.
   * Compare embedding backends (`all-MiniLM-L6-v2` vs `all-mpnet-base-v2`).
   * Review similarity distributions, latency deltas, and memory footprint.
2. **Business Analytics & Funnel (14:00 - 17:00)**:
   * Navigate to **Business Analytics**.
   * Inspect applicant pool funnel, skill gap distributions, and multi-layer agreement metrics.
   * Export session summary reports in XLSX and CSV.
3. **Q&A & Code Inspection (17:00 - 20:00)**:
   * Inspect repository structure, clean architecture boundaries, and SQLite schema.

---

## 4. Live Demonstration Script: Scripted Persona Walkthrough

### Persona: Sarah (Senior Technical Recruiter)
* **Action**: Sarah opens **Screening Session**, selects "Senior Backend Engineer", and enrolls 5 applicants.
* **Talking Point**: *"Notice that when I click 'Run Multi-Layer Screening', the system doesn't make hiring decisions for me. It reads each document, extracts chronological tenure, verifies skill presence across lexical and semantic layers, and computes an auditable score."*
* **Action**: Sarah clicks on candidate *Alice Smith*. She points out the 3 contributions: Technical Skills (20%), Experience (60%), Education (20%).
* **Talking Point**: *"Alice has a verified 7 years of Python experience, matching our 5+ year requirement. Here is the verbatim citation from her resume. If we look at Charlie Brown, an executive chef, he scored 35% overall because his 7-year kitchen tenure matched the general duration rule, but he received exactly 0% on technical skills and education. The recruiter sees this immediately."*
* **Action**: Sarah changes Alice's status to `SHORTLISTED` and enters notes: *"Candidate has strong Python backend background; invited to technical interview."*

---

## 5. Contingency & Fallback Procedures

| Scenario | Immediate Remedy |
| :--- | :--- |
| **No Internet Connection** | Sentence Transformers models are cached locally in the HuggingFace cache (`~/.cache/huggingface/hub/`). The application runs 100% offline on CPU. |
| **Streamlit Port Conflict (Port 8501 in use)** | Run with alternate port: `streamlit run app.py --server.port 8502`. |
| **Corrupted Local SQLite Database** | Run `python -c "from core.storage.database import Database; db = Database('hirematch.db'); db.initialize()"` to cleanly recreate the schema. |
| **Missing Model Weights** | MiniLM-L6-v2 fallback runs automatically or downloads instantly on first run. |
