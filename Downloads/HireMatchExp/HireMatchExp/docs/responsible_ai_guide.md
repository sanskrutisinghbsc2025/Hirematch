# HireMatch - Responsible AI & Decision-Support Guide

## 1. Core Ethical Principles
HireMatch is built on the strict principle that **recruitment artificial intelligence must serve solely as an explainable decision-support tool for human reviewers**.

```
+-------------------------------------------------------------+
|                      HUMAN RECRUITER                        |
|  (Retains full decision authority; reviews evidence & notes)|
+-------------------------------------------------------------+
                              ▲
                              │ Explanations & Evidence
                              │ (Verbatim citations, weights)
+-------------------------------------------------------------+
|                        HIREMATCH                            |
|  - Organizes submitted resume evidence against job criteria |
|  - Strictly prohibits demographic & personality criteria   |
|  - Never automatically hires or rejects candidates         |
|  - Communicates uncertainty (missing evidence != failure)   |
+-------------------------------------------------------------+
```

---

## 2. Hard Governance Rules

### Rule 1: No Automated Rejection or Hiring Authority
- The application does not possess the technical capability or operational authorization to automatically hire or reject candidates.
- Candidate review statuses initialize to `PENDING_REVIEW` or `NOT_REVIEWED`.
- Moving a candidate to `SHORTLISTED` or `REJECTED` requires an explicit, authenticated human recruiter action.
- Tiers (`STRONGLY_RECOMMENDED`, `RECOMMENDED`, `POTENTIAL_MATCH`, `UNQUALIFIED`) serve as evidence-completeness aids to prioritize reviewer attention, not final hiring judgments.

### Rule 2: Prohibition of Protected Demographic Traits
HireMatch includes automated pre-flight criteria validation (`ResponsibleAICriteriaValidator`) that rejects criteria mentioning:
- Age or generational brackets (*"under 35"*, *"recent graduate under 25"*).
- Gender, sex, or sexual orientation (*"female preferred"*, *"male coder"*).
- Race, ethnicity, or national origin (*"native English speaker with no foreign accent"*).
- Religion, creed, or spiritual affiliation (*"church-going"*, *"faith-based"*).
- Disability, physical condition, or health status (*"able-bodied"*, *"no chronic illness"*).
- Marital status, family status, or pregnancy (*"married"*, *"no childcare constraints"*).

### Rule 3: Prohibition of Subjective Personality & "Vibe" Judgments
Recruitment screening must focus strictly on verifiable competencies, credentials, and experience. The criteria validator rejects subjective personality traits that introduce unconscious bias:
- Stereotypical buzzwords (*"rockstar"*, *"ninja"*, *"guru"*).
- Cultural fit and vibe requirements (*"good vibes"*, *"culture fit"*, *"beer test"*).
- Subjective behavioral assertions (*"naturally energetic"*, *"aggressive closer"*).

### Rule 4: Uncertainty Communication & No Negative Proof from Silence
- The absence of a skill in a resume is recorded as `NOT_FOUND` or `INSUFFICIENT_EVIDENCE`.
- HireMatch strictly rejects the assumption that silence equals incompetence. Resumes are summarized documents; unmentioned skills represent gaps in documentation, not proven lack of ability.
- Recruiters are explicitly prompted to explore unmentioned criteria during candidate interviews.

### Rule 5: Transparent, Verbatim Evidence Grounding
- Every score is accompanied by itemized criterion-level explanations and verbatim excerpts quoted directly from the candidate's resume.
- Scores can be mathematically traced to exact equations:
  $$\text{Contribution}_i = \frac{w_i \cdot s_i}{\sum_{j \in \text{Eligible}} w_j} \times 100$$
- No hidden score adjustments, unexplained penalties, or black-box overrides exist in the codebase.

---

## 3. User Interface Responsible AI Banners
Responsible AI notices are embedded directly into user workflows:
1. **Application Header**: System status badges accompanied by ethical decision-support disclaimers.
2. **Workspace Dashboard**: Explains that match scores and tiers assist human review and do not constitute hiring decisions.
3. **Candidate Dossier Profile**: Clarifies that extracted skills represent verbatim textual evidence, not an all-encompassing evaluation of applicant worth.
4. **Comparison View**: Emphasizes that candidate differentiators reflect variance in submitted documents against identical requisition criteria.
