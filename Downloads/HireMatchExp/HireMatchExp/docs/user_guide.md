# HireMatch: Comprehensive User & Recruiter Guide

## 1. Quick Start & Setup

### 1.1 Prerequisites
* Python 3.11 or higher
* Recommended: Virtual environment (`venv`)

### 1.2 Installation
In the project root directory, install required dependencies:
```bash
pip install -r requirements.txt
```

Verify your environment and dependencies using the built-in system check:
```bash
python check_system.py
```

### 1.3 Launching the Application
Launch HireMatch with Streamlit:
```bash
streamlit run app.py
```
The application will open in your default browser at `http://localhost:8501`.

---

## 2. Navigating the Screening Workflow

HireMatch guides recruiters through an intuitive 7-page workflow:

```
[1. Upload & Extract] ──► [2. Criteria & Weights] ──► [3. Screening Session]
                                                            │
    ┌───────────────────────────────────────────────────────┘
    ▼
[4. Candidate Evaluation] ──► [5. Comparison & Simulation]
    │                                │
    ▼                                ▼
[6. Business Analytics] ───► [7. Model Laboratory]
```

### Page 1: Upload & Extraction (`01_Upload_and_Extraction.py`)
1. **Document Upload**: Drag and drop PDF or DOCX resume files into the file uploader.
2. **Real-Time Validation**: The system validates magic bytes, verifies file structure, and catches corrupted or unreadable uploads immediately.
3. **Structured Preview**: Inspect cleansed extracted text, extracted contact info (sanitized), and automatically recognized sections (`EXPERIENCE`, `SKILLS`, `EDUCATION`).

### Page 2: Criteria & Weights (`02_Criteria_and_Weights.py`)
1. **Define Requisition Requirements**: Enter required skills, minimum tenure thresholds, and credential expectations.
2. **Category Tagging**: Organize criteria by `TECHNICAL_SKILL`, `SOFT_SKILL`, `WORK_EXPERIENCE`, `EDUCATION`, or `CERTIFICATION`.
3. **Weight Allocation**: Adjust numerical sliders (0.1 to 5.0) to reflect the relative importance of each requirement. HireMatch automatically computes normalized weight percentages.

### Page 3: Screening Session (`03_Screening_Session.py`)
1. **Session Setup**: Bind an active job requisition with an uploaded batch of candidates.
2. **Execution Trigger**: Click **Run Multi-Layer Screening** to execute exact, alias, and semantic evaluation pipelines.
3. **Session Leaderboard**: View ranked candidates with real-time status indicators (`IN_REVIEW`, `FLAGGED`).

### Page 4: Candidate Evaluation (`04_Candidate_Evaluation.py`)
1. **Candidate Inspector**: Select an individual applicant to view their composite match score and evaluation breakdown.
2. **Evidence Cards**: Review layer-by-layer matching citations showing exactly which resume sentences support each criterion.
3. **Human Decision Support**: Update candidate status (`SHORTLISTED`, `ON_HOLD`, `NOT_SHORTLISTED`) with recruiter notes. HireMatch records every action in the immutable audit log.

### Page 5: Comparison & Benchmarking (`05_Comparison_and_Benchmarking.py`)
1. **Side-by-Side Comparison**: Select 2 to 5 candidates for direct criterion-by-criterion evidence comparison.
2. **Sensitivity Sandbox**: Test "what-if" weighting scenarios using interactive sliders. Observe rank shifts in real time without altering stored database records.

### Page 6: Business Analytics (`06_Business_Analytics.py`)
1. **Recruiter Funnel**: Track conversion from enrolled candidates to extracted, evaluated, and shortlisted states.
2. **Skill Coverage & Pool Gaps**: Identify common technical competencies and frequent skill gaps across the applicant cohort.
3. **Audit Trail**: Inspect timestamped logs of every evaluation run, status change, and report generation.
4. **Data Exports**: Download complete session results as formatted Excel (`.xlsx`) spreadsheets or CSV files.

### Page 7: Model Laboratory (`07_Model_Laboratory.py`)
1. **Technical Benchmarking**: Compare supported NLP embedding models (`all-MiniLM-L6-v2`, `all-mpnet-base-v2`, BGE, E5) on identical text inputs.
2. **Speed & Memory Metrics**: Inspect latency benchmarks and memory footprint data to inform production deployment decisions.

---

## 3. Score Interpretation Guide

Candidate match scores are presented on a 0% to 100% scale. Because HireMatch evaluates strictly verifiable text alignment, scores should be interpreted as follows:

| Score Range | Interpretation | Recommended Action |
| :---: | :--- | :--- |
| **80% – 100%** | **Strong Evidence Alignment**: Candidate explicitly demonstrates substantial coverage of required skills, experience tenure, and qualifications. | Prioritize for human hiring manager review. |
| **50% – 79%** | **Moderate Alignment**: Demonstrates core qualifications with minor skill or tenure gaps, or expressed skills using non-standard phrasing. | Review evidence citations to identify specific gap areas. |
| **0% – 49%** | **Limited Alignment**: Sparse or missing evidence for the target requisition's criteria. | Human recruiter confirms whether candidate is suitable for alternative roles. |

> [!IMPORTANT]
> **Decision-Support Principle**: A score of 0% or 40% does **not** automatically reject a candidate. In HireMatch, automated rejection is prohibited. Every applicant remains in `IN_REVIEW` until a human reviewer renders a deliberate decision.

---

## 4. Troubleshooting & FAQ

* **Q: A resume uploaded with errors: "Invalid PDF header signature".**
  * *A*: The uploaded file is corrupted or is a non-PDF file renamed with a `.pdf` extension. The file validator protects the pipeline from crashing. Replace with a valid PDF.
* **Q: Why does an experienced candidate have 0% on a technical skill?**
  * *A*: HireMatch requires verifiable text evidence. If the candidate used completely unrecognized proprietary jargon not covered by `skills_db.json` or semantic embeddings, reviewers can inspect the raw text and adjust criteria weights or aliases accordingly.
* **Q: Does adjusting sliders in the Sensitivity Sandbox overwrite previous results?**
  * *A*: No. The Sensitivity Sandbox operates strictly in memory. Stored scores and historical rankings in the SQLite database remain unmutated.
