
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class SynthesisItem(BaseModel):
    passage_text: str
    source_section: str
    matched_by: List[str]
    confidence_score: float
    is_negated: bool = False


class CriterionResultItem(BaseModel):
    criterion_name: str
    criterion_type: str
    category: Optional[str] = None
    weight: float = 1.0
    score: float = 0.0
    match_status: str
    explanation: Optional[str] = ""
    supporting_evidence: List[str] = []
    evidence_sources: List[str] = []
    matching_method: Optional[str] = "lexical"
    similarity_tier: Optional[str] = None
    semantic_score: Optional[float] = 0.0
    synthesis_items: List[Dict[str, Any]] = []


class ScoringContributionItem(BaseModel):
    criterion_name: str
    category: str
    criterion_type: str
    configured_weight: float
    support_value: float
    normalized_contribution: float
    notes: Optional[str] = None
    match_status: str


class CandidateEvaluationResponse(BaseModel):
    candidate_id: str
    session_id: Optional[str] = None
    overall_score: float
    evidence_coverage: float
    config_version: str
    evaluated_at: str
    unmet_mandatory_criteria: List[str] = []
    conflicting_criteria: List[str] = []
    baseline_summary: Dict[str, Any] = {}
    semantic_summary: Dict[str, Any] = {}
    structured_summary: Dict[str, Any] = {}
    criterion_results: List[CriterionResultItem] = []
    criterion_contributions: List[ScoringContributionItem] = []
    explanation: Optional[str] = None
    ai_review: Optional[str] = None
    fit_tier: Optional[str] = None
    criteria_scores: List[Dict[str, Any]] = []
    discrepancies: List[Dict[str, Any]] = []

