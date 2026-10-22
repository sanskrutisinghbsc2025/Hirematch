
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RequiredSummary(BaseModel):
    total_required: int = 0
    satisfied_count: int = 0
    not_found_count: int = 0
    insufficient_evidence_count: int = 0
    conflicting_count: int = 0
    all_satisfied: bool = False


class QualityCriterionSchema(BaseModel):
    criterion_key: str
    criterion_name: str
    score: float
    weight: float
    weighted_score: float
    status: str
    observations: str
    evidence_snippets: List[str] = []


class QualityStrengthSchema(BaseModel):
    title: str
    description: str
    criterion_key: str
    evidence_quote: Optional[str] = None


class QualityImprovementSchema(BaseModel):
    title: str
    recommendation: str
    criterion_key: str
    rationale: str


class QualityIssueSchema(BaseModel):
    issue_type: str
    severity: str
    description: str
    context: Optional[str] = None


class ReadabilityMetricsSchema(BaseModel):
    word_count: int = 0
    sentence_count: int = 0
    avg_words_per_sentence: float = 0.0
    bullet_count: int = 0
    bullet_ratio: float = 0.0
    action_verb_count: int = 0
    action_verb_ratio: float = 0.0
    quantified_metric_count: int = 0
    readability_level: str = "Clear and Concise"


class ExtractionDiagnosticsSchema(BaseModel):
    char_count: int = 0
    line_count: int = 0
    page_count: int = 1
    ocr_needed: bool = False
    is_empty: bool = False
    parse_confidence: float = 1.0
    warnings: List[str] = []


class ResumeQualityReportResponse(BaseModel):
    id: str
    candidate_id: str
    session_id: Optional[str] = None
    overall_score: float
    quality_label: str
    criterion_results: List[QualityCriterionSchema] = []
    strong_areas: List[QualityStrengthSchema] = []
    areas_for_improvement: List[QualityImprovementSchema] = []
    detected_issues: List[QualityIssueSchema] = []
    section_completeness: Dict[str, Any] = {}
    readability_metrics: ReadabilityMetricsSchema = ReadabilityMetricsSchema()
    extraction_diagnostics: ExtractionDiagnosticsSchema = ExtractionDiagnosticsSchema()
    executive_summary: str = ""
    responsible_ai_notice: str = (
        "Resume quality reflects how clearly and consistently the submitted resume communicates its information. "
        "It is separate from the candidate's match score. Resume quality is not candidate quality."
    )
    assessed_at: str


class CandidateSummary(BaseModel):
    id: str
    candidate_id: str
    name: str
    original_filename: str
    email: Optional[str] = None
    fit_tier: str = "Under Review"
    rank: int
    overall_score: Optional[float] = None
    evidence_coverage: float = 0.0
    review_status: str
    is_tied: bool = False
    required_satisfied_count: int = 0
    required_total_count: int = 0
    missing_critical_count: int = 0
    conflicts_count: int = 0
    completeness_status: str
    session_status: str
    created_at: str
    resume_quality_score: Optional[float] = None
    resume_quality_label: Optional[str] = None


class CandidateListResponse(BaseModel):
    items: List[CandidateSummary]
    total: int
    page: int
    page_size: int
    total_pages: int


class CandidateDetailResponse(BaseModel):
    id: str
    candidate_id: str
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    fit_tier: str = "Under Review"
    rank: Optional[int] = None
    overall_score: Optional[float] = None
    original_filename: str
    file_type: str
    file_hash: str
    processing_status: str
    error_info: Optional[str] = None
    created_at: str
    contact: Dict[str, Any] = {}
    ocr_needed: bool = False
    sections: List[Dict[str, Any]] = []
    skills: List[Any] = []
    experience: List[Any] = []
    education: List[Any] = []
    projects: List[Any] = []
    certifications: List[Any] = []
    extracted_text: Optional[str] = None
    latest_score: Optional[float] = None
    review_status: str = "IN_REVIEW"
    reviewer_notes: Optional[str] = None
    notes: Optional[str] = None
    explanation: Optional[str] = None
    ai_review: Optional[str] = None
    unmet_mandatory_criteria: List[str] = []
    conflicting_criteria: List[str] = []
    discrepancies: List[Dict[str, Any]] = []
    discrepancy_count: int = 0
    resume_quality: Optional[ResumeQualityReportResponse] = None
    resume_quality_score: Optional[float] = None
    resume_quality_label: Optional[str] = None


class ShortlistUpdateRequest(BaseModel):
    review_status: str = Field(..., description="SHORTLISTED, IN_REVIEW, NEEDS_REVIEW, or NOT_SHORTLISTED")
    reviewer_notes: Optional[str] = Field(None, max_length=1000)
