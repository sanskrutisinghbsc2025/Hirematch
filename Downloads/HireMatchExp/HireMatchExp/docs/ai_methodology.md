# HireMatch: AI Methodology & Mathematical Scoring Foundations

## 1. Natural Language Preprocessing Pipeline

HireMatch implements a deterministic multi-stage document parsing and text preparation pipeline:

1. **Extraction & Canonical Cleansing**:
   * Text is extracted with positional layout awareness from PDF/DOCX buffers.
   * Unicode artifacts, ligatures (e.g., "ﬁ", "ﬂ"), and carriage returns are normalized.
   * Redundant whitespace is collapsed while preserving paragraph boundaries for section detection.

2. **Structural Section Segmentation**:
   * Analyzes structural headings to partition the resume into labeled zones: `SUMMARY`, `SKILLS`, `EXPERIENCE`, `EDUCATION`, `PROJECTS`, and `CERTIFICATIONS`.
   * Ensures section-scoped queries (e.g., verifying a skill appears in active experience rather than solely in a hobby section).

3. **Temporal Experience Calculation**:
   * Detects date ranges (e.g., `Jan 2021 – Present`, `2018 - 2020`) using pattern recognizers.
   * Calculates chronological duration in months, accounting for ongoing roles and discounting overlaps to avoid tenure inflation.

---

## 2. Multi-Layer Evidence Alignment

Rather than relying on a single fallible score, HireMatch decomposes criterion matching across three distinct analytical layers:

```
                      [ Criterion Specification ]
                                  │
          ┌───────────────────────┼───────────────────────┐
          ▼                       ▼                       ▼
  [ Layer 1: Lexical ]    [ Layer 2: Alias ]      [ Layer 3: Semantic ]
   Exact Token Match       Taxonomy Mapping         Vector Cosine Sim
          │                       │                       │
          └───────────────────────┼───────────────────────┘
                                  ▼
                     [ Multi-Layer Evaluator ]
                     - Contextual Validation
                     - Negation Screening
                     - Threshold Calibration
                                  │
                                  ▼
                   [ Criterion Support: 0.0 - 1.0 ]
                   [ Extracted Evidence Citation  ]
```

### Layer 1: Exact Lexical Matching
* Scans target resume sections for exact token occurrences.
* Produces boolean detection with high precision ($P \approx 1.0$) but low recall for synonyms or varying phrasing.

### Layer 2: Skill Taxonomy & Alias Mapping
* Evaluates terms against a structured skill database (`skills_db.json`) containing over 160 curated aliases and hierarchical categories.
* Normalizes expressions such as:
  * `"K8s"` $\rightarrow$ `"Kubernetes"`
  * `"Amazon Web Services"` $\rightarrow$ `"AWS"`
  * `"React.js"` $\rightarrow$ `"React"`

### Layer 3: Dense Semantic Vector Matching
* Utilizes pretrained sentence transformer models (defaulting to `sentence-transformers/all-MiniLM-L6-v2`, with selectable options including `all-mpnet-base-v2`, BGE, and E5).
* Sentences from candidate experience narratives are encoded into dense unit-norm embedding vectors:
  $$\mathbf{u} = \frac{f(\text{criterion})}{\|f(\text{criterion})\|_2}, \quad \mathbf{v}_j = \frac{f(\text{sentence}_j)}{\|f(\text{sentence}_j)\|_2}$$
* Computes cosine similarity across candidate sentence vectors:
  $$\text{sim}(\mathbf{u}, \mathbf{v}_j) = \mathbf{u} \cdot \mathbf{v}_j = \sum_{k=1}^d u_k v_{j,k}$$

### Calibration & Contextual Discounting
* **Threshold Floor ($\tau = 0.50$)**: Cosine similarities below $\tau$ are clamped to zero to suppress random semantic noise.
* **Support Score Calibration**:
  $$\text{support}_i = \min\left(1.0, \frac{\max_j(\text{sim}_j) - \tau}{1.0 - \tau}\right)$$
* **Negation & Scope Discounting**:
  Sentences exhibiting negation cues (e.g., *"unfamiliar with Docker"*, *"did not implement Kubernetes"*) trigger context filters that zero out support and flag the candidate for human review (`ScoreStatus.FLAGGED`).

---

## 3. Mathematical Scoring Engine

Every candidate score in HireMatch is fully deterministic, transparent, and auditable.

### Criteria Weight Normalization
Recruiters configure criteria $C_1, C_2, \dots, C_n$ with user-defined raw weights $W_i \ge 0$. The system computes normalized weights:
$$w_i = \frac{W_i}{\sum_{k=1}^n W_k}, \quad \text{such that} \quad \sum_{i=1}^n w_i = 1.0$$

### Composite Score Calculation
For each candidate $A$, the overall match score is the weighted sum of individual criterion support levels:
$$\text{OverallScore}(A) = 100 \times \sum_{i=1}^n \left( w_i \times \text{support}_i(A) \right)$$

### Normalized Contribution Breakdown
To provide total transparency in recruiter dashboards and candidate reports, the score contribution of each criterion is explicitly presented:
$$\text{Contribution}_i = 100 \times \left( w_i \times \text{support}_i \right)$$
$$\text{OverallScore} = \sum_{i=1}^n \text{Contribution}_i$$

---

## 4. Sensitivity Simulation Sandbox

To allow recruiters to understand how weighting choices impact candidate ranking, HireMatch provides an in-memory **Sensitivity Simulation Engine**:

1. Takes current candidate evaluation support vectors $\mathbf{s}(A) = [\text{support}_1, \dots, \text{support}_n]$.
2. Computes prospective overall scores under proposed weights $\mathbf{w}'$:
   $$\text{Score}'(A) = 100 \times \sum_{i=1}^n w'_i \times s_i(A)$$
3. Computes rank volatility ($\Delta \text{Rank} = \text{Rank}_{\text{orig}} - \text{Rank}_{\text{sim}}$).
4. **Data Integrity Guarantee**: Simulations execute strictly in memory. Stored screening records, historical rankings, and audit logs in SQLite are never modified by simulation operations.
