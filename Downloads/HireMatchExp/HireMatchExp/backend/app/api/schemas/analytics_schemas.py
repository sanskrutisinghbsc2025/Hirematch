
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class FunnelMetric(BaseModel):
    stage_name: str
    count: int
    conversion_rate: float
    dropoff_rate: float


class ScoreDistributionMetrics(BaseModel):
    mean: float
    median: float
    std_dev: float
    p25: float
    p75: float
    iqr: float
    min: float
    max: float


class SkillCoverageItem(BaseModel):
    canonical_name: str
    pool_coverage_percentage: float
    candidate_evidence_count: int
    requirement_type: str
    category: str
    gap_status: str


class SessionAnalyticsResponse(BaseModel):
    session_id: str
    session_name: str
    job_title: str
    scoring_config_version: str
    total_candidates: int
    evaluated_candidates: int
    funnel_metrics: List[FunnelMetric]
    score_distribution: ScoreDistributionMetrics
    score_histogram: List[Dict[str, Any]]
    shortlist_counts: Dict[str, int]
    skill_coverage: List[SkillCoverageItem]
    acute_gaps: List[str]
    discrepancy_count: int
    conflicting_candidates_count: int
    traceable_insights: List[Dict[str, Any]]
    average_score: Optional[float] = 0.0
    strong_matches: int = 0
    potential_matches: int = 0
    under_review: int = 0


class PortfolioAnalyticsResponse(BaseModel):
    total_sessions: int
    total_resumes: int
    evaluated_resumes: int
    avg_composite_score: float
    avg_evidence_coverage: float
    overall_funnel: List[FunnelMetric]
    shortlist_distribution: Dict[str, int]
    top_demanded_skills: List[Dict[str, Any]]
    time_series_batches: List[Dict[str, Any]]
    processing_outcomes: Dict[str, int]
    total_candidates: Optional[int] = None
    avg_shortlist_rate: Optional[float] = None
    strong_match_rate: Optional[float] = 0.0
    strong_matches_count: Optional[int] = 0
    potential_match_rate: Optional[float] = 0.0
    potential_matches_count: Optional[int] = 0


class SessionCompareRequest(BaseModel):
    session_ids: List[str] = Field(..., min_length=2, max_length=5)


class SessionCompareResponse(BaseModel):
    is_compatible: bool
    compatibility_warnings: List[str]
    comparison_summary_table: List[Dict[str, Any]]
    aligned_criteria_support_rates: Dict[str, Dict[str, float]]
    session_names: Dict[str, str]
