
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid


class GapStatus(str, Enum):
    WELL_COVERED = "WELL_COVERED"
    MODERATE_COVERAGE = "MODERATE_COVERAGE"
    ACUTE_GAP = "ACUTE_GAP"


class InsightSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class InsightCategory(str, Enum):
    ACUTE_SKILL_GAP = "ACUTE_SKILL_GAP"
    LOW_SCORE_VARIATION = "LOW_SCORE_VARIATION"
    CLUSTERED_SCORES = "CLUSTERED_SCORES"
    PROCESSING_BOTTLENECK = "PROCESSING_BOTTLENECK"
    HIGH_EVALUATION_DIFFICULTY = "HIGH_EVALUATION_DIFFICULTY"
    SEMANTIC_DISCOVERY = "SEMANTIC_DISCOVERY"


@dataclass
class AnalyticsFilter:
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    job_id: Optional[str] = None
    session_ids: Optional[List[str]] = None
    min_score: Optional[float] = None
    max_score: Optional[float] = None
    shortlist_status: Optional[str] = None
    evidence_status: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "start_date": self.start_date,
            "end_date": self.end_date,
            "job_id": self.job_id,
            "session_ids": self.session_ids,
            "min_score": self.min_score,
            "max_score": self.max_score,
            "shortlist_status": self.shortlist_status,
            "evidence_status": self.evidence_status,
        }


@dataclass
class TimeSeriesPoint:
    period: str
    session_count: int = 0
    resume_count: int = 0
    avg_score: Optional[float] = None
    shortlist_count: int = 0


@dataclass
class PortfolioAnalytics:
    total_sessions: int
    total_resumes_enrolled: int
    total_resumes_processed: int
    completed_processing_count: int
    partial_processing_count: int
    failed_processing_count: int
    duplicate_processing_count: int
    average_session_processing_seconds: Optional[float] = None
    average_resume_processing_seconds: Optional[float] = None
    overall_mean_score: Optional[float] = None
    overall_median_score: Optional[float] = None
    score_quartiles: Dict[str, float] = field(default_factory=lambda: {"q1": 0.0, "q2": 0.0, "q3": 0.0})
    time_series_trends: List[TimeSeriesPoint] = field(default_factory=list)
    shortlist_funnel_totals: Dict[str, int] = field(default_factory=dict)
    active_jobs_count: int = 0
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_sessions": self.total_sessions,
            "total_resumes_enrolled": self.total_resumes_enrolled,
            "total_resumes_processed": self.total_resumes_processed,
            "completed_processing_count": self.completed_processing_count,
            "partial_processing_count": self.partial_processing_count,
            "failed_processing_count": self.failed_processing_count,
            "duplicate_processing_count": self.duplicate_processing_count,
            "average_session_processing_seconds": self.average_session_processing_seconds,
            "average_resume_processing_seconds": self.average_resume_processing_seconds,
            "overall_mean_score": self.overall_mean_score,
            "overall_median_score": self.overall_median_score,
            "score_quartiles": self.score_quartiles,
            "time_series_trends": [
                {
                    "period": p.period,
                    "session_count": p.session_count,
                    "resume_count": p.resume_count,
                    "avg_score": p.avg_score,
                    "shortlist_count": p.shortlist_count,
                }
                for p in self.time_series_trends
            ],
            "shortlist_funnel_totals": self.shortlist_funnel_totals,
            "active_jobs_count": self.active_jobs_count,
            "generated_at": self.generated_at,
        }


@dataclass
class CriterionAnalytics:
    criterion_id: str
    criterion_name: str
    category: str
    criterion_type: str
    configured_weight: float
    total_evaluated: int
    mean_support_value: float
    mean_normalized_points: float
    std_dev: float
    variance: float
    is_low_variation: bool
    supported_count: int
    partially_supported_count: int
    insufficient_evidence_count: int
    conflicting_evidence_count: int
    evidence_coverage_rate: float
    insufficient_rate: float
    keyword_vs_semantic_divergence: float
    semantic_boost_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "criterion_id": self.criterion_id,
            "criterion_name": self.criterion_name,
            "category": self.category,
            "criterion_type": self.criterion_type,
            "configured_weight": self.configured_weight,
            "total_evaluated": self.total_evaluated,
            "mean_support_value": self.mean_support_value,
            "mean_normalized_points": self.mean_normalized_points,
            "std_dev": self.std_dev,
            "variance": self.variance,
            "is_low_variation": self.is_low_variation,
            "supported_count": self.supported_count,
            "partially_supported_count": self.partially_supported_count,
            "insufficient_evidence_count": self.insufficient_evidence_count,
            "conflicting_evidence_count": self.conflicting_evidence_count,
            "evidence_coverage_rate": self.evidence_coverage_rate,
            "insufficient_rate": self.insufficient_rate,
            "keyword_vs_semantic_divergence": self.keyword_vs_semantic_divergence,
            "semantic_boost_count": self.semantic_boost_count,
        }


@dataclass
class SkillCoverageItem:
    raw_skill_name: str
    canonical_name: str
    category: str
    requirement_type: str
    candidate_evidence_count: int
    total_candidates: int
    pool_coverage_percentage: float
    gap_status: GapStatus
    sample_evidence_snippets: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw_skill_name": self.raw_skill_name,
            "canonical_name": self.canonical_name,
            "category": self.category,
            "requirement_type": self.requirement_type,
            "candidate_evidence_count": self.candidate_evidence_count,
            "total_candidates": self.total_candidates,
            "pool_coverage_percentage": self.pool_coverage_percentage,
            "gap_status": self.gap_status.value,
            "sample_evidence_snippets": self.sample_evidence_snippets,
        }


@dataclass
class TraceableInsight:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    category: InsightCategory = InsightCategory.ACUTE_SKILL_GAP
    severity: InsightSeverity = InsightSeverity.INFO
    title: str = ""
    description: str = ""
    calculation_basis: str = ""
    affected_criteria: List[str] = field(default_factory=list)
    metric_value: Optional[float] = None
    benchmark_threshold: Optional[float] = None
    suggested_recruiter_action: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category.value,
            "severity": self.severity.value,
            "title": self.title,
            "description": self.description,
            "calculation_basis": self.calculation_basis,
            "affected_criteria": self.affected_criteria,
            "metric_value": self.metric_value,
            "benchmark_threshold": self.benchmark_threshold,
            "suggested_recruiter_action": self.suggested_recruiter_action,
        }


@dataclass
class SessionAnalytics:
    session_id: str
    session_name: str
    job_id: str
    job_title: str
    total_enrolled: int
    total_scored: int
    unscorable_count: int
    score_mean: Optional[float]
    score_median: Optional[float]
    score_std_dev: float
    score_variance: float
    score_iqr: float
    is_tightly_clustered: bool
    score_buckets: Dict[str, int]
    evidence_coverage_mean: float
    coverage_buckets: Dict[str, int]
    criterion_analytics: List[CriterionAnalytics] = field(default_factory=list)
    skill_coverage: List[SkillCoverageItem] = field(default_factory=list)
    insights: List[TraceableInsight] = field(default_factory=list)
    shortlist_counts: Dict[str, int] = field(default_factory=dict)
    average_processing_seconds: Optional[float] = None
    scoring_config_version: str = "v1.0"
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def enrolled_count(self) -> int:
        return self.total_enrolled

    @property
    def mean_score(self) -> Optional[float]:
        return self.score_mean

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "session_name": self.session_name,
            "job_id": self.job_id,
            "job_title": self.job_title,
            "total_enrolled": self.total_enrolled,
            "total_scored": self.total_scored,
            "unscorable_count": self.unscorable_count,
            "score_mean": self.score_mean,
            "score_median": self.score_median,
            "score_std_dev": self.score_std_dev,
            "score_variance": self.score_variance,
            "score_iqr": self.score_iqr,
            "is_tightly_clustered": self.is_tightly_clustered,
            "score_buckets": self.score_buckets,
            "evidence_coverage_mean": self.evidence_coverage_mean,
            "coverage_buckets": self.coverage_buckets,
            "criterion_analytics": [c.to_dict() for c in self.criterion_analytics],
            "skill_coverage": [s.to_dict() for s in self.skill_coverage],
            "insights": [i.to_dict() for i in self.insights],
            "shortlist_counts": self.shortlist_counts,
            "average_processing_seconds": self.average_processing_seconds,
            "scoring_config_version": self.scoring_config_version,
            "generated_at": self.generated_at,
        }


@dataclass
class SessionComparisonAnalytics:
    session_ids: List[str]
    session_names: Dict[str, str]
    job_titles: Dict[str, str]
    is_compatible: bool
    compatibility_warnings: List[str]
    comparison_summary_table: List[Dict[str, Any]]
    aligned_criteria_support_rates: Dict[str, Dict[str, float]]
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_ids": self.session_ids,
            "session_names": self.session_names,
            "job_titles": self.job_titles,
            "is_compatible": self.is_compatible,
            "compatibility_warnings": self.compatibility_warnings,
            "comparison_summary_table": self.comparison_summary_table,
            "aligned_criteria_support_rates": self.aligned_criteria_support_rates,
            "generated_at": self.generated_at,
        }
