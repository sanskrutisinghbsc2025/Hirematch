# HireMatch — Model Comparison Laboratory Technical Documentation (Phase 11)

## 1. Executive Overview

The **HireMatch Model Comparison Laboratory** is a specialized evaluation and benchmarking suite designed for machine learning engineers, NLP researchers, and authorized recruitment operations leads. It provides rigorous, controlled technical comparisons across supported pretrained embedding models, cross-encoder rerankers, and keyword baselines on identical job descriptions, candidate resumes, and evaluation criteria.

### Core Governance Principles:
1. **Decision Support & Architecture Selection Only**: The laboratory benchmarks representation geometry, inference latency, throughput, and ranking concordance. Model similarity scores must **never** be presented as candidate quality scores or used to automate hiring decisions.
2. **Strict Demarcation of Metric Categories**:
   - **Reference-Grounded Metrics** (Precision, Recall, F1, NDCG@K, MRR): Computed solely against human-reviewed or synthetic ground-truth datasets.
   - **Descriptive Statistics** (Mean, Median, Standard Deviation, IQR): Computed over unlabeled pools; never referred to as "accuracy".
   - **Runtime Profiling** (Latency ms/item, Throughput items/sec, Peak RAM MB): Hardware-level efficiency measurements.
3. **On-Demand Loading & Resource Reclamation**: Models are loaded on-demand and can be explicitly unloaded from memory to conserve system resources.
4. **Compatibility Guardrails**: Incompatible model architectures (e.g. comparing NER entity extraction spans with dense vector cosine similarity) are flagged and blocked.

---

## 2. Model Registry & Catalog

The centralized [`ModelRegistry`](file:///d:/HireMatch/core/model_lab/registry.py) maintains rich operational metadata for all supported components:

| Model Identifier | Display Name | Paradigm | Task Type | Dims | Max Context | RAM Footprint | Device / Precision | Known Limitations |
|---|---|---|---|---|---|---|---|---|
| `sentence-transformers/all-MiniLM-L6-v2` | MiniLM-L6-v2 | Bi-Encoder | `SEMANTIC_RETRIEVAL` | 384 | 256 | ~120 MB | CPU / float32 | 256 token limit; compressed representations may miss complex negations. |
| `sentence-transformers/all-mpnet-base-v2` | MPNet-Base-v2 | Bi-Encoder | `SEMANTIC_RETRIEVAL` | 768 | 384 | ~450 MB | CPU / float32 | ~3x higher latency and memory footprint than MiniLM. |
| `BAAI/bge-small-en-v1.5` | BGE-Small-EN-v1.5 | Bi-Encoder | `SEMANTIC_RETRIEVAL` | 384 | 512 | ~140 MB | CPU / float32 | Requires consistent query instruction formatting for asymmetric tasks. |
| `intfloat/e5-small-v2` | E5-Small-v2 | Bi-Encoder | `SEMANTIC_RETRIEVAL` | 384 | 512 | ~140 MB | CPU / float32 | Requires explicit `query: ` and `passage: ` prefix distinctions. |
| `cross-encoder/ms-marco-MiniLM-L-6-v2` | MS-Marco Cross-Encoder | Cross-Encoder | `PASSAGE_RERANKING` | N/A | 512 | ~100 MB | CPU / float32 | $O(N \cdot M)$ pairwise inference cost; cannot be pre-indexed via vector cache. |
| `rule-based-keyword` | Rule-Based Keyword Matcher | Exact / Alias | `KEYWORD_MATCHING` | N/A | N/A | <30 MB | CPU / N/A | Strictly bounded by taxonomy alias dictionary; no conceptual generalization. |
| `tfidf-baseline` | TF-IDF N-Gram Baseline | Statistical | `KEYWORD_MATCHING` | N/A | N/A | <20 MB | CPU / float32 | Zero conceptual understanding; misses synonyms and paraphrased experience. |
| `mock-deterministic-embedding` | Mock Deterministic Provider | Hash / Offline | `SEMANTIC_RETRIEVAL` | 64 | 512 | <1 MB | CPU / float32 | Synthetic hashing for deterministic testing; not for production matching. |

---

## 3. Mathematical Metric Definitions

The laboratory implements three classes of evaluation metrics via [`EvaluationMetricsCalculator`](file:///d:/HireMatch/core/model_lab/metrics.py):

### 3.1 Reference-Grounded Metrics

#### Normalized Discounted Cumulative Gain (NDCG@K)
Evaluates graded relevance across top-$K$ ranked items:
$$\text{DCG}@K = \sum_{i=1}^K \frac{2^{r_i} - 1}{\log_2(i + 1)}$$
$$\text{NDCG}@K = \frac{\text{DCG}@K}{\text{IDCG}@K}$$
where $r_i \in \{0, 1, 2\}$ is the ground-truth relevance grade at rank $i$, and $\text{IDCG}@K$ is the ideal DCG obtained by sorting items in descending order of ground-truth relevance.

#### Mean Reciprocal Rank (MRR)
Measures the reciprocal rank of the first relevant document:
$$\text{MRR} = \frac{1}{\text{rank}_1}$$
where $\text{rank}_1$ is the 1-based rank position of the first item with relevance grade $> 0$.

#### Precision@K and Recall@K
$$\text{Precision}@K = \frac{|\text{Relevant Items in Top } K|}{K}$$
$$\text{Recall}@K = \frac{|\text{Relevant Items in Top } K|}{\text{Total Relevant Items}}$$

#### Pairwise Ranking Concordance (Kendall's Tau $\tau$)
Measures the relative ordering agreement between two models across identical candidate evidence:
$$\tau = \frac{P - Q}{\frac{1}{2} n (n - 1)}$$
where $P$ is the number of concordant pairs and $Q$ is the number of discordant pairs.

### 3.2 Descriptive Statistics
- **Mean Score**: $\bar{s} = \frac{1}{N} \sum_{i=1}^N s_i$
- **Standard Deviation**: $\sigma = \sqrt{\frac{1}{N-1} \sum_{i=1}^N (s_i - \bar{s})^2}$
- **Interquartile Range (IQR)**: $\text{IQR} = Q_3 - Q_1$, identifying score compression when $\text{IQR} < 0.12$.
- **Retrieval Coverage**: Percentage of test queries with similarity score $\ge \text{threshold}$.

---

## 4. Human-Reviewed Evaluation Datasets & Rubrics

### 4.1 Documented Ground Truth Evidence Rubric
Reviewers annotate candidate evidence according to four standardized relevance grades:
- **Grade 2 (Highly Relevant)**: Verbatim canonical synonym or direct conceptual fulfillment of the job requirement.
- **Grade 1 (Partially Relevant)**: Adjacent skill, partial exposure, or related framework without direct fulfillment.
- **Grade 0 (Not Relevant)**: Non-equivalent lookalikes (distractors), unrelated work history, or explicitly negated experience.
- **Grade -1 (Uncertain)**: Ambiguous phrasing requiring human recruiter clarification.

### 4.2 Prohibited Evaluation Dimensions
To guarantee ethical, non-discriminatory recruitment AI evaluation:
- **Zero Demographic Traits**: Age, gender, ethnicity, religion, disability, photo, or marital status are strictly prohibited from evaluation criteria.
- **Zero Subjective Personality Claims**: Subjective traits like "cultural fit", "rockstar energy", or "vibes" are rejected during rubric validation.

### 4.3 Immutability & Dataset Freezing
Once a benchmark experiment is executed against an evaluation dataset, [`EvaluationDatasetService.freeze_dataset()`](file:///d:/HireMatch/core/model_lab/dataset_service.py) permanently locks the dataset to guarantee that future benchmark replays evaluate against identical ground truth without silent data drift.

---

## 5. Persistence Schema & Reproducibility

Benchmark runs and versioned datasets are persisted in SQLite:

```sql
CREATE TABLE IF NOT EXISTS evaluation_datasets (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    task TEXT NOT NULL,
    description TEXT,
    rubric_version TEXT NOT NULL,
    created_by TEXT NOT NULL,
    is_frozen INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evaluation_dataset_items (
    id TEXT PRIMARY KEY,
    dataset_id TEXT NOT NULL,
    query_text TEXT NOT NULL,
    passage_text TEXT NOT NULL,
    relevance_grade INTEGER NOT NULL DEFAULT 1,
    category TEXT NOT NULL DEFAULT 'GENERAL',
    reviewer_notes TEXT,
    metadata TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY (dataset_id) REFERENCES evaluation_datasets(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS model_benchmark_runs (
    id TEXT PRIMARY KEY,
    run_name TEXT NOT NULL,
    dataset_id TEXT,
    session_id TEXT,
    config_json TEXT NOT NULL DEFAULT '{}',
    results_json TEXT NOT NULL DEFAULT '{}',
    pairwise_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'PENDING',
    error_log TEXT NOT NULL DEFAULT '[]',
    started_at TEXT NOT NULL,
    completed_at TEXT,
    FOREIGN KEY (dataset_id) REFERENCES evaluation_datasets(id) ON DELETE SET NULL,
    FOREIGN KEY (session_id) REFERENCES screening_sessions(id) ON DELETE SET NULL
);
```
