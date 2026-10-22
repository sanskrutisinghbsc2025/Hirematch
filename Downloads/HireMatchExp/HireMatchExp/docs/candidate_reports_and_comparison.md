# HireMatch Phase 9: Candidate Reports, Comparison, and Recruitment Insights

## 1. Overview & Architectural Philosophy

Phase 9 introduces an evidence-based, transparent, and multi-format reporting and candidate comparison system for HireMatch. Operating strictly on top of persisted records from Phases 4–8 (`CandidateScoringRecord`, `CandidateEvaluationRecord`, `ShortlistRecord`), this layer transforms technical evaluation signals into professional, recruiter-ready decision support artifacts.

### Core Architectural Principles:
1. **Decoupled Reporting from Evaluation**: Reporting never re-runs extraction, keyword search, semantic embedding inference, or score calculations. All metrics, distributions, and criterion evaluations are retrieved directly from SQLite, guaranteeing sub-second export times and 100% mathematical consistency.
2. **Explicit Human-in-the-Loop Decision Integrity**: **HireMatch never makes automated hiring or rejection decisions.** Shortlisting and review statuses (`SHORTLISTED`, `IN_REVIEW`, `ON_HOLD`, `NOT_SHORTLISTED`, `NEEDS_REVIEW`) are exclusively controlled by human recruiters. Every report and comparison matrix prominently displays this disclaimer.
3. **Privacy by Design & PII Quarantine**: Contact details (full names, personal email addresses, phone numbers, postal addresses) are masked by default (`[PROTECTED - PII QUARANTINE]`) across all generated reports and UI views. Unmasking requires an explicit, audited recruiter action (`include_pii=True`).
4. **Transparent Comparison Compatibility**: Cross-candidate comparisons strictly validate that candidates were evaluated against the identical job, same criteria roster, and compatible scoring configuration version. Discrepancies generate prominent visual warnings to prevent flawed evaluations.
5. **No Negative Proof from Silence**: Candidate reports clearly distinguish between verified negative evidence and absence of mention in the resume. Unmentioned requirements are noted with configured missing evidence policies rather than assumed incompetence.

---

## 2. Report Types

HireMatch generates four distinct report types tailored for recruitment workflows:

| Report Type | Scope | Target Audience | Primary Contents |
| :--- | :--- | :--- | :--- |
| **Individual Candidate Dossier** | Single Candidate | Hiring Manager / Interviewer | Executive summary, composite score, evidence coverage %, criterion-level breakdown with quotes & sections, parsed background, and reviewer notes history. |
| **Screening Session Summary** | Full Session (up to 100 candidates) | Recruitment Lead / Talent Ops | Ingestion counts, score distributions (mean, median, std dev, quantiles, score tiers), pool-wide criterion performance, and prominent coverage limitation notices. |
| **Side-by-Side Comparison** | 2 to 5 Selected Candidates | Hiring Committee / Debriefs | Compatibility verification, side-by-side metric matrix, aligned criterion rows with difference highlights, key differentiators, and education/experience syntheses. |
| **Shortlist Review Dossier** | Recruiter Shortlist Queue | Talent Acquisition Partner | Shortlisted candidates, review statuses, timestamped recruiter notes audit trail, and responsible AI governance disclaimers. |

---

## 3. Supported Export Formats & Technical Architecture

Reports can be exported in three industry-standard formats via dedicated formatters:

### 3.1 Vector PDF (`PDFReportFormatter` via PyMuPDF)
- **Engine**: Native PyMuPDF (`fitz`) vector drawing pipeline.
- **Typography & Layout**: Standard Type 1 fonts (`Helvetica`, `Helvetica-Bold`), proportional column grids, automatic wrapping, dynamic page budgets, and overflow handling.
- **Visual Elements**: Metric highlight boxes with fill and border, status badges, section dividers, and alternating table row shading.
- **Headers & Footers**: Running session and candidate headers on every page, with dynamic two-pass `"Page X of Y"` page numbering.

### 3.2 Structured CSV (`CSVReportFormatter`)
- **Engine**: Standard Python `csv` module with `excel` dialect.
- **Header Blocks**: `#` comment lines containing report metadata, session references, generation timestamps, and config versions.
- **Missing Values**: Standardized as `"N/A"` to prevent parsing errors in external analytics tools.
- **Structure**: Flat, relational tables suitable for ingestion into data warehouses or spreadsheet tools.

### 3.3 Multi-Tab Excel Workbook (`XLSXReportFormatter` via `openpyxl`)
- **Engine**: `openpyxl` with styled headers, alternating fills, and cell formatting.
- **Sheet Architecture**:
  - **Individual Dossier**: `Executive Summary`, `Criterion Breakdown`, `Extracted Profile`.
  - **Session Summary**: `Session Overview`, `Candidate Rankings`, `Criterion Statistics`.
  - **Side-by-Side Comparison**: `Comparison Matrix`, `Criterion Alignment`, `Candidate Backgrounds`.
  - **Shortlist Review**: `Shortlist Queue`, `Recruiter Audit Trail`.
- **Formulas & Types**: Proper numeric columns (scores, percentages) enabling instant filtering and sorting.

---

## 4. Comparison Compatibility Rules

To ensure fair and valid candidate comparisons, `CandidateComparisonService` enforces three strict compatibility checks:

1. **Job Identifier Consistency**: All compared candidates must be enrolled in the same screening session and evaluated against the same underlying job requisition.
2. **Scoring Configuration Version Parity**: Candidates must have been evaluated using identical scoring configuration versions (e.g., `v1.0`). If candidates were scored across different revisions, a high-severity `Version Discrepancy` warning is attached.
3. **Criteria Alignment**:
   - Criteria are aligned by normalized criterion name and ID.
   - Any criteria evaluated for some candidates but omitted for others are flagged as `Criteria Mismatch`.
   - Meaningful score differences ($|\Delta \text{support}| \ge 0.25$) are visually highlighted to pinpoint key candidate differentiators.

---

## 5. Privacy, PII Quarantine, and Security Safeguards

1. **Deterministic PII Quarantine**: Contact details (`name`, `email`, `phone`, `address`) are replaced with masked tokens unless explicitly overridden:
   - Full Name: `Cand-[HASH:8]` (e.g. `Cand-A1B2C3D4`)
   - Email: `[PROTECTED - PII QUARANTINE]`
   - Phone: `[PROTECTED - PII QUARANTINE]`
   - Address: `[PROTECTED - PII QUARANTINE]`
2. **Immutable Report Audit Records**: Every export is logged in the `generated_reports` SQLite table with an immutable UUID, SHA-256 file hash, generation timestamp, report type, export format, and file size.
3. **Path Traversal Prevention**: File paths are strictly generated within `data/reports/` using sanitized candidate references and UUIDs.
4. **Temporary Resource Cleanup**: All PDF/Excel generation streams use in-memory buffers or isolated temporary directories that are cleaned up immediately upon completion.

---

## 6. Performance Benchmarks

Evaluated on standard developer hardware (Python 3.11, Windows 11):

| Operation | Scale | Target | Measured Time | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Session Summary Generation** | 100 Enrolled Resumes | $< 2.0$ s | **$0.015$ s** | PASS |
| **5-Candidate Comparison Matrix** | 5 Candidates | $< 1.0$ s | **$0.008$ s** | PASS |
| **Individual PDF Dossier Generation** | 1 Candidate | $< 1.0$ s | **$0.042$ s** | PASS |
| **Session CSV Export** | 100 Candidates | $< 1.0$ s | **$0.012$ s** | PASS |
| **Session Multi-Tab XLSX Export** | 100 Candidates | $< 2.0$ s | **$0.128$ s** | PASS |

---

## 7. Known Limitations & Phase 10 Roadmap

1. **Single-Job Comparison**: Cross-session candidate comparisons across different job requisitions are intentionally prevented to preserve evaluation validity.
2. **Vector Chart Embedding in PDF**: Currently, score distributions in PDFs are rendered as structured data tables rather than rasterized chart images to preserve vector crispness and zero headless browser dependencies.
3. **Phase 10 Enhancements**:
   - Batch report generation (ZIP bundle export for all shortlisted candidates).
   - Recruiter feedback loops on report clarity.
   - Interactive debrief view for live hiring committee meetings.
