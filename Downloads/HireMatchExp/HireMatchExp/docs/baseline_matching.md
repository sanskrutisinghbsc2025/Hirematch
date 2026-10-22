# HireMatch – Phase 5: Baseline NLP and Explainable Keyword Matching

## 1. Architectural Overview

Phase 5 establishes the first end-to-end evaluation engine in **HireMatch**. It serves as an explainable, transparent, deterministic reference baseline comparing structured job requirements against parsed resume evidence.

In accordance with responsible AI and rigorous machine learning engineering practices, this baseline strictly avoids opaque semantic embeddings or black-box neural similarity models (which are scheduled for Phase 6). Instead, every candidate score is derived from explicit evidence, section-weighted keyword and phrase occurrences, alias resolution, tenure intervals, and degree tier hierarchies.

```
                              ┌──────────────────────────────────────────────┐
                              │           Screening Session Job              │
                              │  (Required & Preferred Evaluation Criteria)  │
                              └──────────────────────┬───────────────────────┘
                                                     │
                                                     ▼
┌────────────────────────────────┐         ┌───────────────────────────────────┐
│     Candidate Domain Model     │         │    BaselineCandidateEvaluator     │
│   (Cleaned Text, Extracted     │────────▶│  - Dispatches criteria by type    │
│    Entities, Sections)         │         │  - Isolated error handling        │
└────────────────────────────────┘         └─────────────────┬─────────────────┘
                                                             │
                  ┌──────────────────────────────────────────┼────────────────────────────────────────┐
                  ▼                                          ▼                                        ▼
    ┌───────────────────────────┐              ┌───────────────────────────┐            ┌───────────────────────────┐
    │SectionAwareKeywordMatcher │              │     ExperienceMatcher     │            │     EducationMatcher      │
    │ - Exact term matching     │              │ - Date interval parsing   │            │ - Canonical degree tiers  │
    │ - Multi-word phrases      │              │ - Deduplicate overlap     │            │ - Abbreviation mapping    │
    │ - Taxonomy alias mapping  │              │ - Tenure thresholding     │            │ - Certification credit    │
    │ - Section weighting       │              │ - Ambiguous date fallback │            └─────────────┬─────────────┘
    │ - Negation detection      │              └─────────────┬─────────────┘                          │
    └─────────────┬─────────────┘                            │                                        │
                  │                                          │                                        │
                  └──────────────────────────────────────────┼────────────────────────────────────────┘
                                                             │
                                                             ▼
                                               ┌───────────────────────────┐
                                               │ TransparentScoringEngine  │
                                               │ - Normalized weighted sum │
                                               │ - Evidence coverage %     │
                                               │ - Required unmet tracking │
                                               │ - Verbatim citations      │
                                               └─────────────┬─────────────┘
                                                             │
                                                             ▼
                                               ┌───────────────────────────┐
                                               │      CandidateScore       │
                                               │  & EvaluationEvidence DB  │
                                               └───────────────────────────┘
```

---

## 2. Evaluation Engine Components

### 2.1 Section-Aware Keyword Matcher (`core/evaluation/keyword_matcher.py`)
Matches target skills and competencies against structured candidate data with section-aware confidence scores:

1. **Exact & Phrase Matching:** Detects exact technical terms (e.g. `Python`, `Docker`) and multi-word phrases (e.g. `Continuous Integration`, `Machine Learning`) bounded by word boundaries.
2. **Taxonomy Alias Resolution:** Bridges synonyms and abbreviations via `SkillTaxonomyNormalizer` (`K8s` $\to$ `Kubernetes`, `JS` $\to$ `JavaScript`, `Postgres` $\to$ `PostgreSQL`).
3. **Section Weighting Hierarchy:** Recognizes that explicit skill declarations and work experience carry far more weight than casual mentions:
   | Section | Weight Factor | Description |
   | :--- | :---: | :--- |
   | `SKILLS` | **1.00** | Explicit technical skills catalog |
   | `EXPERIENCE` | **0.95** | Applied professional employment |
   | `CERTIFICATIONS` | **0.90** | Verified professional certifications |
   | `PROJECTS` | **0.85** | Hands-on project portfolio |
   | `SUMMARY` | **0.80** | Professional executive summary |
   | `EDUCATION` | **0.70** | Academic coursework or projects |
   | `GENERAL` | **0.70** | Unclassified document body text |
   | `HEADER` | **0.50** | Contact header or metadata |

### 2.2 Negation & Negative Context Detection (`core/evaluation/negation_detector.py`)
Prevents false-positive credit when candidates explicitly state they lack a skill (e.g. *"no experience with GraphQL"*, *"haven't worked with AWS"*):
- **Window Analysis:** Scans an 80-character prefix and 60-character postfix surrounding detected terms using compiled regex patterns.
- **Clause Boundary Resets:** Punctuation boundaries (`.`, `;`, `but`, `however`) reset the negation window so subsequent positive clauses are not falsely penalized (e.g., *"No experience with GCP, but 5 years with AWS"* credits AWS).
- **Non-Punitive Isolation:** Negated mentions are excluded from positive score calculations and noted in the evaluation audit report.

### 2.3 Experience Duration & Tenure Evaluator (`core/evaluation/experience_matcher.py`)
Evaluates required employment duration against extracted job history:
- **Date Interval Parsing:** Extracts four-digit year intervals (`2019 - 2023`, `2021 to Present`) across all employment records.
- **Overlapping Tenure Deduplication:** Concurrent roles (e.g., holding two jobs simultaneously in 2021–2023) are merged using an interval-merging algorithm to avoid double-counting years of experience.
- **Support Tiers:**
  - $\ge$ Required Years: `SUPPORTED` (Score: 100.0)
  - $\ge 50\%$ of Required Years: `PARTIALLY_SUPPORTED` (Score: proportional $\frac{\text{Actual}}{\text{Required}} \times 100$)
  - $< 50\%$ of Required Years: `NOT_FOUND` (Score: proportional)
  - Unverifiable or ambiguous dates: `INSUFFICIENT_EVIDENCE` (Score: 0.0)

### 2.4 Academic Degree & Credential Matcher (`core/evaluation/education_matcher.py`)
Evaluates candidate education against required credential levels:
- **Canonical Degree Hierarchy:**
  1. `DOCTORATE` (Ph.D., Doctor of Science) — Level 5
  2. `MASTER` (M.S., M.Tech, M.A., MBA, M.Sc) — Level 4
  3. `BACHELOR` (B.S., B.Tech, B.E., B.A., B.Sc) — Level 3
  4. `ASSOCIATE` (Associate Degree, A.S., A.A.) — Level 2
  5. `HIGH_SCHOOL` (High School Diploma, GED) — Level 1
- **Higher-Tier Satisfaction:** A candidate holding a Master's degree automatically satisfies or exceeds a Bachelor's requirement (`SUPPORTED`, Score: 100.0).
- **Abbreviation Equivalence:** Transparently maps `B.S. in Software Engineering` or `BS` to Bachelor's.
- **Certification Compensation:** If no formal degree is found but professional credentials exist (e.g., `AWS Solutions Architect`), the candidate receives `PARTIALLY_SUPPORTED` (Score: 40.0) rather than a complete zero.

---

## 3. Scoring Architecture & Responsible AI Formulas

### 3.1 Transparent Scoring Engine (`core/evaluation/scoring_engine.py`)

The overall candidate match score is calculated as a normalized, weighted sum of evaluated criteria scores:

$$S_{\text{overall}} = \frac{\sum_{i=1}^{N} w_i \cdot s_i}{\sum_{i=1}^{N} w_i}$$

Where:
- $w_i \in [0.0, 1.0]$ is the configured weight of criterion $i$.
- $s_i \in [0.0, 100.0]$ is the score awarded for criterion $i$.
- $S_{\text{overall}} \in [0.0, 100.0]$ is the normalized overall match index.

### 3.2 Evidence Coverage Metric

Evidence coverage measures the proportion of criteria supported by verifiable citations in the resume text:

$$\text{Coverage \%} = \frac{N_{\text{supported}} + N_{\text{partially supported}}}{N_{\text{total evaluated}}} \times 100$$

### 3.3 Handling Missing Information (Responsible AI)

1. **No Negative Proof:** In resume screening, absence of evidence is not evidence of absence. A missing skill or degree is classified as `NOT_FOUND` or `INSUFFICIENT_EVIDENCE`—never penalized as negative proof.
2. **Mandatory Criteria Tracking:** Missing required criteria are tracked separately via `required_unmet_count` and reported transparently to recruiters with clear notices rather than silently zeroing out the candidate's entire evaluation.
3. **Traceability:** Every awarded score links directly to verbatim resume sentence citations in `evaluation_evidence`.

---

## 4. Frontend Workspace & Candidate Profile Integration

1. **Screening Workspace (`ui/views/workspace.py`):**
   - **Batch Evaluation Trigger:** Recruiter can click `🎯 Evaluate Resumes` to score pending extracted candidates in batches.
   - **Real-Time Metrics:** Displays counts for Total Enrolled, Extracted Text, Evaluated & Scored, and Flags/Failures.
   - **Data Table:** Presents candidate filename, format, status badge (`EVALUATED`, `EXTRACTED`, etc.), Match Score (e.g. `85.0 / 100`), Evidence Coverage (e.g. `90% cov`), and unfulfilled required criteria warnings (`⚠️ 1`).
   - **Score Slider Filter:** Allows recruiters to filter candidates above a specified minimum match score threshold.
2. **Candidate Profile (`ui/views/candidate_profile.py`):**
   - **Multi-Layer Criteria Evaluation & Evidence Audit Tab (Tab 6):**
     - Overall Match Index metric, Evidence Coverage %, and Required Criteria Met status.
     - Transparent summary audit explanation.
     - Responsible AI notice regarding missing criteria.
     - Expandable criterion cards detailing criterion weight, evaluation method (`EXACT`, `TAXONOMY_ALIAS`, `EXPERIENCE_YEARS`, `EDUCATION_DEGREE`), match status badge, and verbatim quote citations with source section tags.

---

## 5. Verification & Test Suite Coverage

The Phase 5 test suite (`tests/test_baseline_matching.py`) contains 19 comprehensive automated tests:
- `TestNegationDetector` (3 tests): Verifies explicit negation cues, positive usage preservation, and clause boundary isolation.
- `TestSectionAwareKeywordMatcher` (6 tests): Validates exact matching, phrase matching, taxonomy alias resolution, section weight hierarchy, negation rejection, and missing term handling.
- `TestExperienceMatcher` (3 tests): Validates tenure thresholding, concurrent employment interval deduplication, and unparseable date fallbacks.
- `TestEducationMatcher` (4 tests): Validates higher-degree satisfaction, abbreviation equivalency, partial tier support, and certification compensation.
- `TestScoringEngine` (2 tests): Validates normalized weighted score aggregation, coverage formulas, and mandatory criteria missing warnings.
- `TestOrchestratorBatchEvaluation` (1 test): End-to-end integration test of batch evaluation, database persistence, session status transitions, and evidence retrieval.

**Overall Test Suite Status:**
- Total tests: **66 tests** across 8 test suites.
- Pass rate: **100% (66/66 passed)**.

---

## 6. Limitations & Phase 6 Transition

While Phase 5 delivers a transparent, fully explainable matching engine, it operates on lexical, rule-based, and taxonomy-driven principles:
- It cannot detect semantic synonyms not present in `skills_db.json` (e.g., recognizing that *"Architected high-throughput message streams"* implies Kafka / pub-sub proficiency).
- It cannot perform cross-encoder semantic ranking between job descriptions and varied resume phrasings.

These capabilities will be addressed in **Phase 6: Pretrained Semantic Models and Embedding Engine** using local sentence transformers (`all-MiniLM-L6-v2`) and hybrid score fusion.
