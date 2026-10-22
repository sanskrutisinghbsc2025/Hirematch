
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CandidateCompareRequest(BaseModel):
    session_id: Optional[str] = None
    candidate_ids: List[str] = Field(..., min_length=2, max_length=5)


class CandidateHeader(BaseModel):
    candidate_id: str
    id: Optional[str] = None
    candidate_reference: str
    candidate_name: Optional[str] = None
    name: Optional[str] = None
    email: Optional[str] = None
    original_filename: str
    overall_score: Optional[float] = None
    evidence_coverage: float = 0.0
    review_status: str
    reviewer_notes: Optional[str] = None
    resume_quality_score: Optional[float] = None
    resume_quality_label: Optional[str] = None
    fit_tier: Optional[str] = None


class AlignedCriterionRow(BaseModel):
    criterion_id: str
    criterion_name: str
    criterion_type: str
    configured_weight: float
    candidate_evaluations: Dict[str, Dict[str, Any]]
    has_meaningful_difference: bool = False
    variance_note: Optional[str] = None


class ComparisonCompatibility(BaseModel):
    is_compatible: bool
    shared_config_version: Optional[str] = None
    compatibility_warnings: List[str] = []


class CandidateCompareResponse(BaseModel):
    job_id: str
    job_title: str
    compared_at: str
    compatibility: ComparisonCompatibility
    candidate_headers: List[CandidateHeader]
    candidates: Optional[List[CandidateHeader]] = None
    aligned_criteria_rows: List[AlignedCriterionRow]
    criteria_comparison: Optional[List[AlignedCriterionRow]] = None
    key_differentiators: List[str] = []
    differentiators: Optional[List[str]] = None
    education_comparison: Dict[str, str] = {}
    experience_comparison: Dict[str, str] = {}
