# Phase 7: Multi-Layer Candidate Evaluation Engine

## Overview

The **Multi-Layer Candidate Evaluation Engine** combines structured resume information (Phase 4), explainable keyword and rule matching (Phase 5), dense pretrained semantic AI embeddings (Phase 6), and job-related evaluation criteria into a comprehensive, verifiable candidate evaluation system.

Rather than relying on black-box scoring or monolithic averaging, HireMatch evaluates candidates across five distinct, auditable layers. Every score is linked to verbatim resume passages, confidence scores, and source section provenance.

---

## The 5-Layer Evaluation Architecture

```
+-------------------------------------------------------------------------------+
|  LAYER 1: Structured Information Extraction                                   |
|  (Contact, Work History, Education, Certifications, Skills, Projects, Text)  |
+-------------------------------------------------------------------------------+
                                        |
+-------------------------------------------------------------------------------+
|  LAYER 2: Baseline Rule & NLP Matching                                        |
|  (Exact keywords, synonyms, taxonomy lookup, regex patterns, negation check)  |
+-------------------------------------------------------------------------------+
                                        |
+-------------------------------------------------------------------------------+
|  LAYER 3: Semantic AI Dense Matching                                         |
|  (Bi-encoder embeddings, cosine similarity, multi-tier thresholding)          |
+-------------------------------------------------------------------------------+
                                        |
+-------------------------------------------------------------------------------+
|  LAYER 4: Multi-Layer Evidence Synthesis & Conflict Detection                  |
|  (Citation deduplication, conservative tenure/degree checks, disagreement     |
|   classification e.g. KEYWORD_NEGATED_IN_CONTEXT)                             |
+-------------------------------------------------------------------------------+
                                        |
+-------------------------------------------------------------------------------+
|  LAYER 5: Aggregation & Responsible Auditing                                  |
|  (Overall Score, Independent Evidence Coverage %, Immutable Versioned Record) |
+-------------------------------------------------------------------------------+
```

### Layer 1: Structured Information Extraction
Utilizes the structured resume representation produced by Phase 4:
- Work experience with dates, job titles, and employers.
- Education degrees, majors, and institutions.
- Certifications with names, dates, and issuing bodies.
- Extracted skills mapped against canonical skills taxonomy.

### Layer 2: Baseline Keyword & NLP Matching
Executes explainable keyword matching from Phase 5:
- Exact string and alias matching against candidate resume text.
- Context window inspection (-40 to +60 chars) around matches.
- Negation detection (`no experience with`, `lacks knowledge of`, `not familiar with`).
- Frequency counts, section weights, and recency tracking.

### Layer 3: Semantic AI Matching
Executes contextual embedding evaluation from Phase 6:
- Encodes job criteria and candidate resume passages using pretrained bi-encoders (`sentence-transformers/all-MiniLM-L6-v2` or fallback provider).
- Computes cosine similarity between requirement embeddings and passage chunks.
- Maps similarity to tiered confidence: High ($\ge 0.70$), Moderate ($0.50 - 0.70$), Weak ($0.35 - 0.50$), None ($< 0.35$).

### Layer 4: Evidence Synthesis & Disagreement Detection
Synthesizes findings from Layers 1, 2, and 3:
1. **Passage Deduplication**: When baseline keyword matches and semantic matches reference the same or overlapping text, passages are merged into a single citation, retaining the longest verbatim excerpt and tagging provenance (`matched_by: ["baseline", "semantic"]`).
2. **Conflict Resolution**:
   - **`KEYWORD_NEGATED_IN_CONTEXT`**: When baseline detects explicit negation (`is_negative_context == True`) while semantic AI yields moderate or high similarity ($\ge 0.50$), the system **does not average them**. Instead, it flags `MatchStatus.CONFLICTING_EVIDENCE`, awards zero credit, logs `conflict_notes`, and queues the candidate for recruiter review.
   - **`SEMANTIC_WITHOUT_KEYWORD`**: Flags strong conceptual alignment where exact terminology was absent.
   - **`KEYWORD_WITHOUT_SEMANTIC`**: Identifies isolated keywords that may lack meaningful project context.
3. **Conservative Experience Evaluation**:
   - Merges non-overlapping tenure intervals to avoid double-counting concurrent roles.
   - Missing or ambiguous dates are classified as `INSUFFICIENT_EVIDENCE` without applying punitive negative scoring.
4. **Conservative Education & Certification Evaluation**:
   - Enforces an academic hierarchy: `HIGH_SCHOOL < ASSOCIATE < BACHELOR < MASTER < DOCTORATE`. Candidates with higher degrees satisfy lower-tier requirements.
   - Unmentioned degrees or certifications are classified as `NOT_FOUND` / `INSUFFICIENT_EVIDENCE`, adhering to the principle that missing data is never negative proof.

### Layer 5: Candidate Aggregation & Responsible Auditing
- **`overall_score`**: Weighted composite score across evaluated criteria.
- **`evidence_coverage`**: Independent percentage measuring how many criteria possess verified evidence citations in the resume. A candidate with a high score on one criterion cannot mask low overall coverage.
- **`CandidateEvaluationRecord`**: Immutable, auditable JSON evaluation snapshot stored with foreign keys to `candidate_id`, `screening_session_id`, and `config_id`. Past evaluations are preserved across recalculations.

---

## Responsible AI Safeguards

1. **Strict Demographics Exclusion**: Criteria relating to age, race, ethnicity, gender, sexual orientation, religion, disability, marital status, nationality, or photographs are strictly rejected by `ResponsibleAICriteriaValidator`.
2. **Subjective Personality Traits Excluded**: Jargon and non-job-related attributes ("rockstar", "ninja", "cultural fit", "energetic", "guru") are blocked.
3. **Missing Data is Not Negative Proof**: If a resume does not explicitly state a requirement, it is marked as `INSUFFICIENT_EVIDENCE` or `NOT_FOUND` rather than penalizing the candidate.
4. **Recruiter in Control**: The system produces transparent recommendations and flags conflicts for human review. Final hiring choices always remain with human decision-makers.

---

## Configuration & Versioning

Evaluations are driven by `EvaluationConfiguration` records:
- `weights`: Configurable weights across Technical Skills, Experience, Education, Certifications, and Soft/Domain Skills.
- `thresholds`: Strong match ($\ge 0.75$), Moderate match ($\ge 0.50$), Weak match ($\ge 0.35$).
- `deduplication_char_overlap`: Minimum character overlap for deduplication (default: 40).
- `semantic_weight` vs `keyword_weight`: Tunable balance (default: 0.60 semantic, 0.40 keyword).
- Versioning: Incremental versions are tracked and stored in `evaluation_configurations`. Any re-run creates a new version or uses an existing immutable configuration ID.
