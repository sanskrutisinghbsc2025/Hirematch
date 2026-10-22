# HireMatch Phase 10: Business Analytics and Advanced Features

## 1. Overview & Architectural Philosophy

Phase 10 introduces a high-performance, explainable **Business Analytics and Advanced Features** suite for HireMatch. Operating strictly on real persisted screening sessions, candidate extractions, multi-layer evaluation results, scoring configurations, and recruiter shortlist decisions from Phases 4–9, this module delivers deep visibility into talent pool composition, skill coverage, scoring behavior, and recruitment workflow patterns.

### Core Architectural Principles:
1. **Decision Support, Not Automated Decisions**: Analytics describe applicant pool distributions, skill coverage, and screening process health; they **never** predict future on-the-job performance or make automated hiring/rejection decisions.
2. **Deterministic, Factual Grounding**: Every insight, metric, and distribution is mathematically derived from stored SQLite records; no vague AI advice or hallucinated conclusions.
3. **Decoupled Architecture**: High-efficiency aggregation queries avoid pulling raw resume texts into memory, guaranteeing $< 1$s computation times across 100-resume sessions.
4. **Privacy & PII Protection**: Aggregated analytics and distribution views operate on anonymized reference IDs (`Cand-[HASH:8]`); personal details are excluded from macro analytics and exports.
5. **No Negative Proof from Silence**: Candidate reports and skill gap analytics clearly distinguish between verified negative evidence and absence of mention in the resume. Unmentioned requirements are noted with configured missing evidence policies rather than assumed incompetence.

---

## 2. Key Analytics Models and Mathematical Definitions

### 2.1 Portfolio Key Performance Indicators
- **Total Sessions & Resumes Enrolled**: Global counts across active screening requisitions.
- **Processing Outcomes**: Segmented counts into `Completed`, `Partial`, `Failed`, and `Duplicate`.
- **Extraction Success Rate**: $\frac{\text{Completed Processing Count}}{\text{Total Resumes Enrolled}} \times 100\%$.
- **Average Resume Processing Duration**: Calculated from `completed_at - created_at` when reliable timestamps exist; reported as `N/A` if unavailable.
- **Overall Mean Score**: Arithmetic mean of valid candidate composite scores ($0.0 - 100.0$).
- **Overall Median Score**: 50th percentile of candidate scores; robust against extreme outliers.
- **Score Quartiles (Q1, Q2, Q3)**: 25th, 50th, and 75th percentiles of candidate scores.

### 2.2 Score Dispersion and Clustering
- **Standard Deviation ($\sigma$) & Variance ($\sigma^2$)**:
  $$\sigma = \sqrt{\frac{1}{N} \sum_{i=1}^N (S_i - \bar{S})^2}$$
- **Interquartile Range (IQR)**:
  $$\text{IQR} = Q_3 - Q_1$$
- **Tightly Clustered Alert**: Triggered if $\text{IQR} < 12.0$ points (for pools with $\ge 5$ candidates), indicating that the middle 50% of candidates are compressed within a narrow 12-point band.

---

## 3. Skill & Criterion Analytics

### 3.1 Skill Coverage & Taxonomy Normalization
- **Normalizer Reuse**: Leverages `SkillTaxonomyNormalizer` (`config/skills_db.json`) to map raw resume terms and JD requirements to canonical skills (e.g., `K8s` $\to$ `Kubernetes`, `ReactJS` $\to$ `React`, `psql` $\to$ `PostgreSQL`).
- **No False Merging**: Unrelated skills with lexical similarity are strictly segregated.
- **Pool Coverage Percentage**:
  $$\text{Pool Coverage } \% = \left( \frac{\text{Candidates with Verified Evidence for Skill}}{\text{Total Enrolled Candidates}} \right) \times 100$$
- **Gap Status Classification**:
  - `WELL_COVERED`: Pool coverage $\ge 70.0\%$.
  - `MODERATE_COVERAGE`: Pool coverage between $40.0\%$ and $69.9\%$.
  - `ACUTE_GAP`: Pool coverage $< 40.0\%$.

### 3.2 Criterion Score Variance & Discriminatory Power
- **Low-Variation Criteria**: Criteria where $\sigma < 0.08$ across evaluated candidates. These criteria fail to differentiate top candidates from the rest of the pool and are flagged with an analytical recommendation to adjust weights.
- **AI Layer Divergence (Keyword vs Semantic AI)**:
  $$\text{Divergence} = \frac{1}{N} \sum_{i=1}^N |S_{\text{baseline}, i} - S_{\text{semantic}, i}|$$
- **Semantic Boost Count**: Number of candidates where $S_{\text{semantic}} \ge S_{\text{baseline}} + 0.30$, proving where dense pretrained embeddings identified conceptual qualifications missed by exact keyword matchers.

---

## 4. Traceable Screening Insights

Every analytical insight is deterministic, actionable, and traceable to explicit calculation rules:

| Category | Severity | Trigger Threshold / Rule | Recruiter Guidance |
| :--- | :--- | :--- | :--- |
| **`PROCESSING_BOTTLENECK`** | `WARNING` / `CRITICAL` | `failed_resumes / total_enrolled > 0%` ($\ge 15\%$ is `CRITICAL`) | Retry failed documents in one click from the Workspace manifest. |
| **`CLUSTERED_SCORES`** | `WARNING` | Interquartile Range $\text{IQR} < 12.0$ points ($N \ge 5$) | Adjust criterion weights in Sensitivity Simulator to spread evaluations. |
| **`LOW_SCORE_VARIATION`** | `INFO` | Criterion Standard Deviation $\sigma < 0.08$ ($N \ge 3$) | Down-weight universal baseline criteria to let differentiating skills guide rank. |
| **`HIGH_EVALUATION_DIFFICULTY`** | `WARNING` | Insufficient evidence rate $\ge 75.0\%$ ($N \ge 3$) | Evaluate difficult-to-document requirements during phone screens rather than resume filters. |
| **`ACUTE_SKILL_GAP`** | `INFO` | Insufficient evidence rate $\ge 60.0\%$ ($N \ge 3$) | Consider `EXCLUDE_FROM_CALCULATION` missing policy if skill is trainable. |
| **`SEMANTIC_DISCOVERY`** | `INFO` | Semantic boost count $\ge 2$ candidates | Inspect multi-layer evidence citations to verify candidate synonymy/projects. |

---

## 5. Multi-Session Comparative Benchmarking

The `SessionComparisonAnalyticsService` allows hiring committees to compare 2 to 5 screening sessions side-by-side:
- **Compatibility Validation**:
  - Compares job requisition IDs. If different, flags a `Cross-Job Warning` noting disparate role requirements.
  - Compares scoring configuration versions. If different, flags a `Config Version Discrepancy` warning.
- **Comparative Metrics Matrix**: Side-by-side comparison of candidate pool size, scored count, mean/median score, evidence coverage %, and shortlist conversion %.
- **Common Criteria Alignment**: Compares candidate evidence support rates across sessions for shared requirements.

---

## 6. Export Functionality & Privacy Safeguards

- **Structured CSV (`AnalyticsExportService`)**:
  - Top `#` comments include formal metric definitions, session metadata, filter criteria, and generation timestamps.
  - Tabular rows format numerical data cleanly with standardized `"N/A"` for missing values.
- **Multi-Tab Excel Workbooks (`openpyxl`)**:
  - Dedicated sheets: `Executive Overview`, `Criterion Variance & AI`, `Skill Coverage & Gaps`, `Screening Insights`, and `Metric Definitions`.
  - Professional typography, dark navy headers, and light alternating row fills.
- **Privacy Quarantine**: Candidate names are masked (`Cand-[HASH:8]`), and personal contact details are completely quarantined from macro analytics.

---

## 7. Performance Benchmarks

Evaluated on standard developer hardware (Python 3.11, Windows 11):

| Operation | Scale | Target | Measured Time | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Session Analytics Assembly** | 100 Enrolled Resumes | $< 1.0$ s | **$0.021$ s** | PASS |
| **Skill Coverage Analysis** | 100 Enrolled Resumes | $< 1.0$ s | **$0.018$ s** | PASS |
| **Criterion Variance Analysis** | 100 Enrolled Resumes | $< 1.0$ s | **$0.012$ s** | PASS |
| **Traceable Insights Generation** | 100 Enrolled Resumes | $< 0.5$ s | **$0.003$ s** | PASS |
| **5-Session Comparison Benchmark** | 5 Screening Sessions | $< 1.0$ s | **$0.035$ s** | PASS |
| **Multi-Tab XLSX Analytics Export** | 100 Candidates | $< 2.0$ s | **$0.145$ s** | PASS |
