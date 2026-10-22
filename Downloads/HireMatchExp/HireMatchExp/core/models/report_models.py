
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from core.models.enums import CriterionCategory, CriterionType, MatchStatus, ShortlistReviewStatus


class ReportType(str, Enum):
    INDIVIDUAL_CANDIDATE = "INDIVIDUAL_CANDIDATE"
    SESSION_SUMMARY = "SESSION_SUMMARY"
    CANDIDATE_COMPARISON = "CANDIDATE_COMPARISON"
    SHORTLIST_REPORT = "SHORTLIST_REPORT"


class ExportFormat(str, Enum):
    PDF = "PDF"
    CSV = "CSV"
    XLSX = "XLSX"
    JSON = "JSON"


@dataclass
class CriterionReportItem:
    criterion_id: str
    criterion_name: str
    category: CriterionCategory
    criterion_type: CriterionType
    configured_weight: float
    support_value: float
    normalized_points: float
    match_status: MatchStatus
    matching_method: str = "MULTI_LAYER"
    supporting_evidence: List[str] = field(default_factory=list)
    source_sections: List[str] = field(default_factory=list)
    explanation: str = ""
    warnings: List[str] = field(default_factory=list)
    is_eligible: bool = True
    exclusion_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "criterion_id": self.criterion_id,
            "criterion_name": self.criterion_name,
            "category": self.category.value if hasattr(self.category, "value") else str(self.category),
            "criterion_type": self.criterion_type.value if hasattr(self.criterion_type, "value") else str(self.criterion_type),
            "configured_weight": self.configured_weight,
            "support_value": self.support_value,
            "normalized_points": self.normalized_points,
            "match_status": self.match_status.value if hasattr(self.match_status, "value") else str(self.match_status),
            "matching_method": self.matching_method,
            "supporting_evidence": self.supporting_evidence,
            "source_sections": self.source_sections,
            "explanation": self.explanation,
            "warnings": self.warnings,
            "is_eligible": self.is_eligible,
            "exclusion_reason": self.exclusion_reason,
        }


@dataclass
class CandidateReportData:
    report_id: str
    candidate_id: str
    candidate_reference: str
    original_filename: str
    session_id: str
    session_name: str
    job_id: str
    job_title: str
    processing_status: str
    evaluation_status: str
    evaluated_at: Optional[str]
    scoring_config_version: str

    overall_score: Optional[float]
    evidence_coverage: float
    completeness_status: str
    total_criteria_count: int
    supported_criteria_count: int
    partial_criteria_count: int
    insufficient_criteria_count: int
    conflicting_criteria_count: int

    criterion_items: List[CriterionReportItem] = field(default_factory=list)

    extracted_skills: List[str] = field(default_factory=list)
    work_experience: List[Dict[str, Any]] = field(default_factory=list)
    education: List[Dict[str, Any]] = field(default_factory=list)
    certifications: List[str] = field(default_factory=list)

    review_status: str = "NEEDS_REVIEW"
    reviewer_notes: str = ""
    shortlist_updated_at: Optional[str] = None

    evaluation_warnings: List[str] = field(default_factory=list)
    evidence_limitations: List[str] = field(default_factory=list)
    responsible_ai_disclaimer: str = (
        "HireMatch candidate scores represent mathematical evidence alignment metrics against "
        "configured job requirements. They do not constitute automated hiring decisions, personality "
        "assessments, or guarantees of future job performance. All hiring actions require human review."
    )
    generated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    contact_info: Optional[Dict[str, str]] = None

    resume_quality_score: Optional[float] = None
    resume_quality_label: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "candidate_id": self.candidate_id,
            "candidate_reference": self.candidate_reference,
            "original_filename": self.original_filename,
            "session_id": self.session_id,
            "session_name": self.session_name,
            "job_id": self.job_id,
            "job_title": self.job_title,
            "processing_status": self.processing_status,
            "evaluation_status": self.evaluation_status,
            "evaluated_at": self.evaluated_at,
            "scoring_config_version": self.scoring_config_version,
            "overall_score": self.overall_score,
            "evidence_coverage": self.evidence_coverage,
            "completeness_status": self.completeness_status,
            "total_criteria_count": self.total_criteria_count,
            "supported_criteria_count": self.supported_criteria_count,
            "partial_criteria_count": self.partial_criteria_count,
            "insufficient_criteria_count": self.insufficient_criteria_count,
            "conflicting_criteria_count": self.conflicting_criteria_count,
            "criterion_items": [c.to_dict() for c in self.criterion_items],
            "extracted_skills": self.extracted_skills,
            "work_experience": self.work_experience,
            "education": self.education,
            "certifications": self.certifications,
            "review_status": self.review_status,
            "reviewer_notes": self.reviewer_notes,
            "shortlist_updated_at": self.shortlist_updated_at,
            "evaluation_warnings": self.evaluation_warnings,
            "evidence_limitations": self.evidence_limitations,
            "responsible_ai_disclaimer": self.responsible_ai_disclaimer,
            "generated_at": self.generated_at,
            "contact_info": self.contact_info,
            "resume_quality_score": self.resume_quality_score,
            "resume_quality_label": self.resume_quality_label,
        }


@dataclass
class SessionSummaryReportData:
    report_id: str
    session_id: str
    session_name: str
    job_id: str
    job_title: str
    department: str
    session_created_at: str
    max_resume_count: int

    total_resumes_enrolled: int
    completed_processing_count: int
    failed_processing_count: int
    pending_processing_count: int
    duplicate_count: int

    completed_evaluation_count: int
    scoring_config_id: str
    scoring_config_version: str
    coverage_limitation_warning: Optional[str] = None
    evaluation_methods_used: List[str] = field(default_factory=list)

    score_distribution: Dict[str, Any] = field(default_factory=dict)

    criterion_performance: List[Dict[str, Any]] = field(default_factory=list)

    shortlist_summary: Dict[str, int] = field(default_factory=dict)

    candidate_summaries: List[Dict[str, Any]] = field(default_factory=list)

    warnings: List[str] = field(default_factory=list)
    responsible_ai_disclaimer: str = (
        "HireMatch session metrics provide descriptive applicant pool summaries based on configured "
        "evaluation requirements. They do not constitute automated selection, demographic analytics, "
        "or validation of overall candidate potential."
    )
    generated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "session_id": self.session_id,
            "session_name": self.session_name,
            "job_id": self.job_id,
            "job_title": self.job_title,
            "department": self.department,
            "session_created_at": self.session_created_at,
            "max_resume_count": self.max_resume_count,
            "total_resumes_enrolled": self.total_resumes_enrolled,
            "completed_processing_count": self.completed_processing_count,
            "failed_processing_count": self.failed_processing_count,
            "pending_processing_count": self.pending_processing_count,
            "duplicate_count": self.duplicate_count,
            "coverage_limitation_warning": self.coverage_limitation_warning,
            "completed_evaluation_count": self.completed_evaluation_count,
            "scoring_config_id": self.scoring_config_id,
            "scoring_config_version": self.scoring_config_version,
            "evaluation_methods_used": self.evaluation_methods_used,
            "score_distribution": self.score_distribution,
            "criterion_performance": self.criterion_performance,
            "shortlist_summary": self.shortlist_summary,
            "candidate_summaries": self.candidate_summaries,
            "warnings": self.warnings,
            "responsible_ai_disclaimer": self.responsible_ai_disclaimer,
            "generated_at": self.generated_at,
        }


@dataclass
class ComparisonCompatibilityResult:
    is_compatible: bool
    shared_job_id: str
    shared_config_version: Optional[str]
    compatibility_warnings: List[str] = field(default_factory=list)
    common_criteria_count: int = 0
    discrepant_criteria: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_compatible": self.is_compatible,
            "shared_job_id": self.shared_job_id,
            "shared_config_version": self.shared_config_version,
            "compatibility_warnings": self.compatibility_warnings,
            "common_criteria_count": self.common_criteria_count,
            "discrepant_criteria": self.discrepant_criteria,
        }


@dataclass
class AlignedCriterionComparisonRow:
    criterion_id: str
    criterion_name: str
    category: CriterionCategory
    criterion_type: CriterionType
    configured_weight: float
    candidate_evaluations: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    has_meaningful_difference: bool = False
    variance_note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "criterion_id": self.criterion_id,
            "criterion_name": self.criterion_name,
            "category": self.category.value if hasattr(self.category, "value") else str(self.category),
            "criterion_type": self.criterion_type.value if hasattr(self.criterion_type, "value") else str(self.criterion_type),
            "configured_weight": self.configured_weight,
            "candidate_evaluations": self.candidate_evaluations,
            "has_meaningful_difference": self.has_meaningful_difference,
            "variance_note": self.variance_note,
        }


@dataclass
class CandidateComparisonData:
    report_id: str
    session_id: str
    session_name: str
    job_id: str
    job_title: str
    compared_candidate_ids: List[str]
    candidate_headers: List[Dict[str, Any]]
    compatibility: ComparisonCompatibilityResult
    aligned_criteria_rows: List[AlignedCriterionComparisonRow] = field(default_factory=list)
    education_comparison: Dict[str, str] = field(default_factory=dict)
    experience_comparison: Dict[str, str] = field(default_factory=dict)
    key_differentiators: List[str] = field(default_factory=list)
    generated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "session_id": self.session_id,
            "session_name": self.session_name,
            "job_id": self.job_id,
            "job_title": self.job_title,
            "compared_candidate_ids": self.compared_candidate_ids,
            "candidate_headers": self.candidate_headers,
            "compatibility": self.compatibility.to_dict(),
            "aligned_criteria_rows": [r.to_dict() for r in self.aligned_criteria_rows],
            "education_comparison": self.education_comparison,
            "experience_comparison": self.experience_comparison,
            "key_differentiators": self.key_differentiators,
            "generated_at": self.generated_at,
        }


@dataclass
class ShortlistReportItem:
    candidate_id: str
    candidate_reference: str
    original_filename: str
    review_status: ShortlistReviewStatus
    overall_score: Optional[float]
    evidence_coverage: float
    key_evidence_highlights: List[str] = field(default_factory=list)
    reviewer_notes: str = ""
    updated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "candidate_reference": self.candidate_reference,
            "original_filename": self.original_filename,
            "review_status": self.review_status.value if hasattr(self.review_status, "value") else str(self.review_status),
            "overall_score": self.overall_score,
            "evidence_coverage": self.evidence_coverage,
            "key_evidence_highlights": self.key_evidence_highlights,
            "reviewer_notes": self.reviewer_notes,
            "updated_at": self.updated_at,
        }


@dataclass
class ShortlistReportData:
    report_id: str
    session_id: str
    session_name: str
    job_id: str
    job_title: str
    total_shortlisted_count: int
    items: List[ShortlistReportItem] = field(default_factory=list)
    status_counts: Dict[str, int] = field(default_factory=dict)
    responsible_ai_disclaimer: str = (
        "Shortlist status and associated notes represent human recruiter determinations. "
        "Candidates are never shortlisted or rejected automatically by the AI system."
    )
    generated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "session_id": self.session_id,
            "session_name": self.session_name,
            "job_id": self.job_id,
            "job_title": self.job_title,
            "total_shortlisted_count": self.total_shortlisted_count,
            "items": [i.to_dict() for i in self.items],
            "status_counts": self.status_counts,
            "responsible_ai_disclaimer": self.responsible_ai_disclaimer,
            "generated_at": self.generated_at,
        }


@dataclass
class GeneratedReportRecord:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    report_type: ReportType = ReportType.INDIVIDUAL_CANDIDATE
    session_id: str = ""
    candidate_ids: List[str] = field(default_factory=list)
    eval_config_version: str = "v1.0"
    scoring_config_version: str = "v1.0"
    export_format: ExportFormat = ExportFormat.PDF
    file_path: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "report_type": self.report_type.value if hasattr(self.report_type, "value") else str(self.report_type),
            "session_id": self.session_id,
            "candidate_ids": self.candidate_ids,
            "eval_config_version": self.eval_config_version,
            "scoring_config_version": self.scoring_config_version,
            "export_format": self.export_format.value if hasattr(self.export_format, "value") else str(self.export_format),
            "file_path": self.file_path,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }
