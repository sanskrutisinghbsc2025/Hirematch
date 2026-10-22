# HireMatch Phase 8: Configurable Scoring Engine and Intelligent Shortlisting

## 1. Overview & Architectural Philosophy

Phase 8 introduces a deterministic, transparent, and configurable scoring and ranking layer that operates on top of Phase 7's multi-layer candidate evaluation records (`CandidateEvaluationRecord`). 

### Core Architectural Principles:
1. **Decoupled Evaluation from Scoring**: Scoring and ranking recalculations never re-run extraction, baseline NLP, or semantic embedding inference. They execute instantaneously ($< 1$ ms per candidate) in-memory over evaluated criterion results.
2. **Deterministic & Reversible**: Every candidate score is derived through an explicit mathematical formula where each criterion's contribution in points is fully traceable. No hidden weights, black-box adjustments, or non-deterministic rankings.
3. **Recruiter-in-the-Loop Decision Integrity**: **HireMatch never makes automated hiring or rejection decisions.** Shortlisting is an explicit recruiter action (`NEEDS_REVIEW`, `IN_REVIEW`, `SHORTLISTED`, `NOT_SHORTLISTED`, `ON_HOLD`).
4. **Responsible AI Exclusions**: Demographic factors, institutions, protected characteristics, and subjective buzzwords ("rockstar", "ninja", "culture fit", "vibes") are strictly excluded from criteria and scoring formulas.
5. **No Negative Proof from Silence**: A resume's silence on a topic is not evidence of candidate incompetence. Configurable missing evidence policies govern how unmentioned skills are weighted or flagged.

---

## 2. Mathematical Scoring Model

### 2.1 Formula & Normalization
For a candidate evaluated against a set of enabled scoring criteria $C$, where each criterion $i$ has configured weight $w_i > 0$ and evaluated support value $s_i \in [0.0, 1.0]$:

$$\text{Eligible} = \{ i \in C \mid i \text{ is enabled and not excluded by missing evidence policy} \}$$

$$\text{Normalized Weight } \hat{w}_i = \frac{w_i}{\sum_{j \in \text{Eligible}} w_j}$$

$$\text{Criterion Contribution (pts)} = \hat{w}_i \times s_i \times 100$$

$$\text{Overall Score} = \sum_{i \in \text{Eligible}} \left( \hat{w}_i \times s_i \times 100 \right) \in [0.0, 100.0]$$

If $\sum_{j \in \text{Eligible}} w_j = 0.0$ or all criteria are disabled/unscorable, the candidate receives:
$$\text{Overall Score} = \text{None}$$
$$\text{Completeness} = \text{INSUFFICIENT\_DATA}$$
HireMatch never invents default numerical scores when data is missing.

### 2.2 Missing Evidence Policies
Recruiters configure how missing or unmentioned criteria are scored:
- **`ZERO_CREDIT` (Default)**: The criterion remains in the denominator ($\sum w$). The candidate receives $s_i = 0.0$ and $0.0$ contribution points.
- **`EXCLUDE_FROM_CALCULATION`**: The criterion is removed from $\text{Eligible}$. The denominator is reduced to the sum of remaining criteria weights, preventing candidates from being penalized for unmentioned non-essential skills.
- **`FLAG_FOR_REVIEW`**: Awarded $0.0$ credit, the candidate's score completeness is marked `PARTIAL`, and a warning is attached for human recruiter attention.

### 2.3 Conflicting Evidence Handling
When cross-layer evaluation detects contradictory signals (e.g., keyword negation vs semantic match):
- Credit awarded: **$0.0$ points**.
- Conflicting signals are **never averaged** to avoid masking discrepancies.
- A high-priority warning is attached to the candidate's scoring record.

### 2.4 Evidence Coverage Percentage
Independent of the weighted score, HireMatch calculates an objective evidence coverage metric:
$$\text{Evidence Coverage } \% = \left( \frac{\text{Count of Evaluated Criteria with SUPPORTED or PARTIAL}}{\text{Total Enabled Criteria}} \right) \times 100$$

---

## 3. Deterministic Ranking & Tie Handling

Candidates are ranked deterministically using a multi-attribute lexicographical sort key:
1. **Primary**: Overall score descending ($\text{overall\_score} \downarrow$).
2. **Secondary**: Evidence coverage % descending ($\text{evidence\_coverage} \downarrow$).
3. **Tertiary**: Required criteria fully supported count descending ($\text{supported\_count} \downarrow$).
4. **Tie-Breaker**: Candidate ID ascending ($\text{candidate\_id} \uparrow$) for stable, deterministic ordering.

### 3.1 Floating-Point Tie Detection
Scores are compared using an epsilon threshold:
$$| \text{score}_A - \text{score}_B | < 10^{-4} \ (0.0001)$$
When two candidates share an identical score within $\epsilon$, secondary and tertiary attributes are checked. If all match, the candidates are marked `is_tied = True`.

### 3.2 Configurable Tie Handling Strategies
- **`STANDARD_COMPETITION` (Default "1224")**: Tied candidates receive the same rank. The subsequent candidate receives rank equal to preceding rank + number of tied peers.
- **`DENSE` ("1223")**: Tied candidates receive the same rank. The subsequent candidate receives rank + 1 with no gaps.
- **`ORDINAL` ("1234")**: Ties are strictly broken using secondary, tertiary, and candidate ID tie-breakers, guaranteeing unique integer ranks.

### 3.3 Isolation of Incomplete Candidates
Candidates with `overall_score is None` or `ScoreCompleteness.INSUFFICIENT_DATA`:
- Assigned `rank = 0`.
- Tagged with `is_tied = False`.
- Grouped in an "Incomplete / Needs Evaluation" section at the end of the ranking manifest, preventing them from corrupting valid candidate comparisons.

---

## 4. Recruiter Shortlist & Review Workflow

### 4.1 Shortlist States
Recruiters transition candidates between explicit review states:
1. `NEEDS_REVIEW`: Candidate flagged for manual verification or incomplete evidence.
2. `IN_REVIEW`: Recruiter or hiring manager is currently examining the profile.
3. `SHORTLISTED`: Candidate selected for interview stages.
4. `NOT_SHORTLISTED`: Candidate not advancing for this requisition.
5. `ON_HOLD`: Consideration deferred for future openings or pipeline stages.

### 4.2 Audit Trail & Reviewer Notes
Every state change persists:
- Session ID & Candidate ID.
- Reviewer note detailing human justification.
- ISO 8601 update timestamp.
- Seamless removal/restoration from shortlist queues without affecting evaluation data.

---

## 5. Ranking Sensitivity Simulator

The sensitivity simulator allows recruiters to explore "what-if" weighting scenarios in real time:
- Adjust criteria weights via in-memory simulation sliders.
- Instant recalculation of candidate ranks.
- Visual display of rank movement ($\pm N$ positions) and identifying key "movers".
- Option to save the adjusted weighting scheme as a new versioned configuration (e.g., `v1.1`) without mutating existing snapshots.

---

## 6. Worked Example

### Job Criteria:
- **Python**: Weight 0.5 (Required, `ZERO_CREDIT`)
- **Cloud (AWS/GCP)**: Weight 0.3 (Required, `ZERO_CREDIT`)
- **Docker**: Weight 0.2 (Preferred, `EXCLUDE_FROM_CALCULATION`)

### Candidate Evidence:
- **Python**: Fully supported ($s = 1.0$)
- **Cloud**: Partially supported ($s = 0.5$)
- **Docker**: Not mentioned (Policy excludes from calculation)

### Calculation:
1. **Eligible Weights**: Python (0.5) + Cloud (0.3) = 0.8 total eligible weight. Docker is excluded.
2. **Normalized Weights**:
   - Python: $0.5 / 0.8 = 0.625$
   - Cloud: $0.3 / 0.8 = 0.375$
3. **Itemized Contributions**:
   - Python: $0.625 \times 1.0 \times 100 = 62.50$ pts
   - Cloud: $0.375 \times 0.5 \times 100 = 18.75$ pts
   - Docker: $0.00$ pts (Excluded from denominator)
4. **Overall Score**: $62.50 + 18.75 = \mathbf{81.25} / 100.0$
5. **Evidence Coverage**: 2 positive matches / 3 enabled criteria = $\mathbf{66.7\%}$
6. **Required Summary**: 1 supported, 1 partial, 0 not found.
