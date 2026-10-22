# HireMatch - Known Limitations & Technical Boundaries

## 1. Demographic Fairness Statement
> [!WARNING]
> **Fairness across demographic subgroups has NOT been established.**
> HireMatch does not collect or infer demographic characteristics (race, gender, age, disability, ethnicity, religion) from candidate resumes, names, or addresses. Consequently, statistical parity, disparate impact ratios, and equalized odds across demographic subgroups have not been evaluated.
> 
> Deploying organizations must conduct jurisdiction-specific adverse impact audits and legal reviews in accordance with applicable labor regulations (e.g., EEOC Uniform Guidelines on Employee Selection Procedures, NYC Local Law 144) prior to operational deployment.

---

## 2. Evaluation & Modeling Limitations

### 1. Document Summarization Bias
- Resumes are self-reported, condensed summaries of past professional history.
- The absence of a specific skill or keyword does not prove candidate inability; it only indicates the absence of textual evidence in the submitted document.
- Unmentioned criteria must be treated as areas for interview exploration, not automatic disqualifications.

### 2. Context Window & Tokenization Boundaries
- Pretrained semantic models operate with defined context limits:
  - `sentence-transformers/all-MiniLM-L6-v2`: 256–512 word pieces.
  - `all-mpnet-base-v2`: 384–512 word pieces.
  - `cross-encoder/ms-marco-MiniLM-L-6-v2`: 512 word pieces.
- To prevent truncation of candidate qualifications, HireMatch sections documents into coherent chunks ($150-400$ characters). However, cross-page narrative continuity may suffer minor degradation in exceptionally long narrative CVs ($>15$ pages).

### 3. OCR & Scanned Image Resumes
- HireMatch parses digital vector PDF and DOCX files.
- If a candidate uploads a flattened image PDF (scanned photocopy with no embedded text layer), the document extractor flags the file as `ocr_needed = True` with `< 30` extracted characters.
- In environments without an integrated OCR engine (e.g. Tesseract), image-only PDFs require human recruiter review or document resubmission.

### 4. Non-English & Multilingual Resumes
- Current skill normalizers (`skills_db.json`), section detectors, and spaCy models are optimized for English-language resumes and job descriptions.
- Resumes submitted in other languages or utilizing regional non-standard section titles may experience lower extraction confidence and should be reviewed manually.

### 5. Domain Vocabulary Boundaries
- The skill taxonomy normalizer contains 160+ curated alias mappings covering modern software engineering, data science, DevOps, and cloud technologies.
- Niche proprietary tools or emergent technologies not present in the taxonomy default to exact phrase matching and semantic embedding similarity.

---

## 3. Recommended Recruiter Operational Best Practices
1. **Never use overall scores as an automated filter**: Scores are sorting aids to prioritize candidate review order, not cut-offs.
2. **Review verbatim evidence in candidate dossiers**: Inspect the quotes extracted from the resume before conducting candidate outreach.
3. **Verify unmentioned required skills in interviews**: Use the "Insufficient Evidence" summary as a targeted interview guide.
4. **Regularly review scoring configuration weights**: Avoid assigning 100% weight to a single criterion to maintain holistic candidate evaluation.
