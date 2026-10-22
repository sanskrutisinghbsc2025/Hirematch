
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from core.models.enums import (
    CriterionCategory,
    CriterionType,
    MatchStatus,
    MissingEvidencePolicy,
    RankingSortField,
    ScoreCompleteness,
    ShortlistReviewStatus,
    TieHandlingStrategy,
)


@dataclass
class ScoringCriterion:

    id: str
    criterion_name: str
    description: str = ""
    category: CriterionCategory = CriterionCategory.TECHNICAL_SKILL
    weight: float = 0.2
    criterion_type: CriterionType = CriterionType.REQUIRED
    evaluation_method: str = "MULTI_LAYER"
    is_enabled: bool = True
    missing_evidence_policy: MissingEvidencePolicy = MissingEvidencePolicy.ZERO_CREDIT
    config_version: str = "v1.0"

    def __post_init__(self) -> None:
        if not self.criterion_name or not self.criterion_name.strip():
            raise ValueError("criterion_name cannot be empty.")
        if not (0.0 <= self.weight <= 1.0):
            raise ValueError(f"weight must be between 0.0 and 1.0, got {self.weight}")
        if not isinstance(self.category, CriterionCategory):
            if isinstance(self.category, str):
                self.category = CriterionCategory(self.category.upper())
            else:
                self.category = CriterionCategory.TECHNICAL_SKILL
        if not isinstance(self.criterion_type, CriterionType):
            if isinstance(self.criterion_type, str):
                self.criterion_type = CriterionType(self.criterion_type.upper())
            else:
                self.criterion_type = CriterionType.REQUIRED
        if not isinstance(self.missing_evidence_policy, MissingEvidencePolicy):
            if isinstance(self.missing_evidence_policy, str):
                self.missing_evidence_policy = MissingEvidencePolicy(self.missing_evidence_policy.upper())
            else:
                self.missing_evidence_policy = MissingEvidencePolicy.ZERO_CREDIT

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "criterion_name": self.criterion_name,
            "description": self.description,
            "category": self.category.value,
            "weight": self.weight,
            "criterion_type": self.criterion_type.value,
            "evaluation_method": self.evaluation_method,
            "is_enabled": self.is_enabled,
            "missing_evidence_policy": self.missing_evidence_policy.value,
            "config_version": self.config_version,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScoringCriterion":
        cat_raw = data.get("category")
        category_val = (
            CriterionCategory(cat_raw.upper())
            if cat_raw and cat_raw.upper() in CriterionCategory._value2member_map_
            else CriterionCategory.TECHNICAL_SKILL
        )
        pol_raw = data.get("missing_evidence_policy")
        policy_val = (
            MissingEvidencePolicy(pol_raw.upper())
            if pol_raw and pol_raw.upper() in MissingEvidencePolicy._value2member_map_
            else MissingEvidencePolicy.ZERO_CREDIT
        )
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            criterion_name=data["criterion_name"],
            description=data.get("description", ""),
            category=category_val,
            weight=float(data.get("weight", 0.2)),
            criterion_type=CriterionType(data.get("criterion_type", CriterionType.REQUIRED.value)),
            evaluation_method=data.get("evaluation_method", "MULTI_LAYER"),
            is_enabled=bool(data.get("is_enabled", True)),
            missing_evidence_policy=policy_val,
            config_version=data.get("config_version", "v1.0"),
        )


@dataclass
class ScoringConfiguration:

    job_id: str
    version: str = "v1.0"
    name: str = "Default Scoring Configuration"
    criteria: List[ScoringCriterion] = field(default_factory=list)
    tie_strategy: TieHandlingStrategy = TieHandlingStrategy.STANDARD_COMPETITION
    secondary_sort: RankingSortField = RankingSortField.EVIDENCE_COVERAGE
    notes: str = ""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self) -> None:
        if not self.job_id:
            raise ValueError("job_id cannot be empty.")
        if not self.version:
            raise ValueError("version cannot be empty.")
        if not isinstance(self.tie_strategy, TieHandlingStrategy):
            if isinstance(self.tie_strategy, str):
                self.tie_strategy = TieHandlingStrategy(self.tie_strategy.upper())
            else:
                self.tie_strategy = TieHandlingStrategy.STANDARD_COMPETITION
        if not isinstance(self.secondary_sort, RankingSortField):
            if isinstance(self.secondary_sort, str):
                self.secondary_sort = RankingSortField(self.secondary_sort.upper())
            else:
                self.secondary_sort = RankingSortField.EVIDENCE_COVERAGE

    def get_criterion(self, criterion_id: str) -> Optional[ScoringCriterion]:
        for c in self.criteria:
            if c.id == criterion_id:
                return c
        return None

    def validate_configuration(self) -> List[str]:
        errors = []
        if not self.criteria:
            errors.append("Configuration must contain at least one scoring criterion.")
            return errors

        seen_ids = set()
        enabled_weight_sum = 0.0
        has_enabled = False

        for c in self.criteria:
            if c.id in seen_ids:
                errors.append(f"Duplicate criterion ID detected: {c.id}")
            seen_ids.add(c.id)

            if c.weight < 0.0 or c.weight > 1.0:
                errors.append(f"Criterion '{c.criterion_name}' weight {c.weight} must be between 0.0 and 1.0.")

            if c.is_enabled:
                has_enabled = True
                enabled_weight_sum += c.weight

        if not has_enabled:
            errors.append("At least one criterion must be enabled.")
        elif enabled_weight_sum <= 0.0:
            errors.append("Sum of enabled criteria weights must be greater than 0.")

        return errors

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "job_id": self.job_id,
            "version": self.version,
            "name": self.name,
            "criteria": [c.to_dict() for c in self.criteria],
            "tie_strategy": self.tie_strategy.value,
            "secondary_sort": self.secondary_sort.value,
            "notes": self.notes,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScoringConfiguration":
        raw_criteria = data.get("criteria", [])
        criteria = [ScoringCriterion.from_dict(c) for c in raw_criteria]
        tie_raw = data.get("tie_strategy")
        tie_val = (
            TieHandlingStrategy(tie_raw.upper())
            if tie_raw and tie_raw.upper() in TieHandlingStrategy._value2member_map_
            else TieHandlingStrategy.STANDARD_COMPETITION
        )
        sort_raw = data.get("secondary_sort")
        sort_val = (
            RankingSortField(sort_raw.upper())
            if sort_raw and sort_raw.upper() in RankingSortField._value2member_map_
            else RankingSortField.EVIDENCE_COVERAGE
        )
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            job_id=data["job_id"],
            version=data.get("version", "v1.0"),
            name=data.get("name", "Default Scoring Configuration"),
            criteria=criteria,
            tie_strategy=tie_val,
            secondary_sort=sort_val,
            notes=data.get("notes", ""),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
        )


@dataclass
class CriterionContribution:

    criterion_id: str
    criterion_name: str
    category: CriterionCategory
    criterion_type: CriterionType
    configured_weight: float
    support_value: float
    normalized_contribution: float
    match_status: MatchStatus
    is_eligible: bool = True
    exclusion_reason: Optional[str] = None
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "criterion_id": self.criterion_id,
            "criterion_name": self.criterion_name,
            "category": self.category.value,
            "criterion_type": self.criterion_type.value,
            "configured_weight": self.configured_weight,
            "support_value": self.support_value,
            "normalized_contribution": self.normalized_contribution,
            "match_status": self.match_status.value,
            "is_eligible": self.is_eligible,
            "exclusion_reason": self.exclusion_reason,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CriterionContribution":
        cat_raw = data.get("category", CriterionCategory.TECHNICAL_SKILL.value)
        return cls(
            criterion_id=data["criterion_id"],
            criterion_name=data["criterion_name"],
            category=CriterionCategory(cat_raw),
            criterion_type=CriterionType(data.get("criterion_type", CriterionType.REQUIRED.value)),
            configured_weight=float(data.get("configured_weight", 0.0)),
            support_value=float(data.get("support_value", 0.0)),
            normalized_contribution=float(data.get("normalized_contribution", 0.0)),
            match_status=MatchStatus(data.get("match_status", MatchStatus.NOT_EVALUATED.value)),
            is_eligible=bool(data.get("is_eligible", True)),
            exclusion_reason=data.get("exclusion_reason"),
            notes=data.get("notes", ""),
        )


@dataclass
class RequiredCriteriaSummary:

    total_required: int = 0
    supported_count: int = 0
    partially_supported_count: int = 0
    not_found_count: int = 0
    insufficient_evidence_count: int = 0
    conflicting_count: int = 0
    not_evaluated_count: int = 0
    details: Dict[str, str] = field(default_factory=dict)

    @property
    def all_satisfied(self) -> bool:
        if self.total_required == 0:
            return True
        return (self.supported_count + self.partially_supported_count) == self.total_required

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_required": self.total_required,
            "supported_count": self.supported_count,
            "partially_supported_count": self.partially_supported_count,
            "not_found_count": self.not_found_count,
            "insufficient_evidence_count": self.insufficient_evidence_count,
            "conflicting_count": self.conflicting_count,
            "not_evaluated_count": self.not_evaluated_count,
            "all_satisfied": self.all_satisfied,
            "details": self.details,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RequiredCriteriaSummary":
        return cls(
            total_required=int(data.get("total_required", 0)),
            supported_count=int(data.get("supported_count", 0)),
            partially_supported_count=int(data.get("partially_supported_count", 0)),
            not_found_count=int(data.get("not_found_count", 0)),
            insufficient_evidence_count=int(data.get("insufficient_evidence_count", 0)),
            conflicting_count=int(data.get("conflicting_count", 0)),
            not_evaluated_count=int(data.get("not_evaluated_count", 0)),
            details=data.get("details", {}),
        )


@dataclass
class CandidateScoringRecord:

    candidate_id: str
    session_id: str
    evaluation_record_id: str
    scoring_config_id: str
    scoring_config_version: str
    overall_score: Optional[float]
    evidence_coverage: float
    completeness_status: ScoreCompleteness
    criterion_contributions: List[CriterionContribution] = field(default_factory=list)
    required_summary: RequiredCriteriaSummary = field(default_factory=RequiredCriteriaSummary)
    explanation: str = ""
    warnings: List[str] = field(default_factory=list)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "candidate_id": self.candidate_id,
            "session_id": self.session_id,
            "evaluation_record_id": self.evaluation_record_id,
            "scoring_config_id": self.scoring_config_id,
            "scoring_config_version": self.scoring_config_version,
            "overall_score": self.overall_score,
            "evidence_coverage": self.evidence_coverage,
            "completeness_status": self.completeness_status.value,
            "criterion_contributions": [c.to_dict() for c in self.criterion_contributions],
            "required_summary": self.required_summary.to_dict(),
            "explanation": self.explanation,
            "warnings": self.warnings,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CandidateScoringRecord":
        raw_contribs = data.get("criterion_contributions", [])
        contribs = [CriterionContribution.from_dict(c) for c in raw_contribs]
        raw_req = data.get("required_summary", {})
        req_summary = RequiredCriteriaSummary.from_dict(raw_req) if raw_req else RequiredCriteriaSummary()
        comp_raw = data.get("completeness_status", ScoreCompleteness.COMPLETE.value)
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            candidate_id=data["candidate_id"],
            session_id=data["session_id"],
            evaluation_record_id=data.get("evaluation_record_id", ""),
            scoring_config_id=data.get("scoring_config_id", "default"),
            scoring_config_version=data.get("scoring_config_version", "v1.0"),
            overall_score=float(data["overall_score"]) if data.get("overall_score") is not None else None,
            evidence_coverage=float(data.get("evidence_coverage", 0.0)),
            completeness_status=ScoreCompleteness(comp_raw),
            criterion_contributions=contribs,
            required_summary=req_summary,
            explanation=data.get("explanation", ""),
            warnings=data.get("warnings", []),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
        )


@dataclass
class ShortlistRecord:

    session_id: str
    candidate_id: str
    review_status: ShortlistReviewStatus = ShortlistReviewStatus.NEEDS_REVIEW
    reviewer_notes: str = ""
    scoring_record_id: Optional[str] = None
    scoring_config_id: str = "default"
    scoring_config_version: str = "v1.0"
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "candidate_id": self.candidate_id,
            "review_status": self.review_status.value,
            "reviewer_notes": self.reviewer_notes,
            "scoring_record_id": self.scoring_record_id,
            "scoring_config_id": self.scoring_config_id,
            "scoring_config_version": self.scoring_config_version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ShortlistRecord":
        st_raw = data.get("review_status", ShortlistReviewStatus.NEEDS_REVIEW.value)
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            session_id=data["session_id"],
            candidate_id=data["candidate_id"],
            review_status=ShortlistReviewStatus(st_raw),
            reviewer_notes=data.get("reviewer_notes", ""),
            scoring_record_id=data.get("scoring_record_id"),
            scoring_config_id=data.get("scoring_config_id", "default"),
            scoring_config_version=data.get("scoring_config_version", "v1.0"),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            updated_at=data.get("updated_at", datetime.now(timezone.utc).isoformat()),
        )


@dataclass
class RankedCandidate:

    rank: int
    candidate_id: str
    candidate_name: str
    filename: str
    overall_score: Optional[float]
    evidence_coverage: float
    completeness_status: ScoreCompleteness
    required_summary: RequiredCriteriaSummary
    is_tied: bool = False
    scoring_record_id: Optional[str] = None
    shortlist_status: Optional[ShortlistReviewStatus] = None
    reviewer_notes: str = ""
    resume_quality_score: Optional[float] = None
    resume_quality_label: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rank": self.rank,
            "candidate_id": self.candidate_id,
            "candidate_name": self.candidate_name,
            "filename": self.filename,
            "overall_score": self.overall_score,
            "evidence_coverage": self.evidence_coverage,
            "completeness_status": self.completeness_status.value,
            "required_summary": self.required_summary.to_dict(),
            "is_tied": self.is_tied,
            "scoring_record_id": self.scoring_record_id,
            "shortlist_status": self.shortlist_status.value if self.shortlist_status else None,
            "reviewer_notes": self.reviewer_notes,
            "resume_quality_score": self.resume_quality_score,
            "resume_quality_label": self.resume_quality_label,
        }


@dataclass
class RankingSnapshot:

    session_id: str
    scoring_config_id: str
    scoring_config_version: str
    ranked_items: List[Dict[str, Any]] = field(default_factory=list)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "scoring_config_id": self.scoring_config_id,
            "scoring_config_version": self.scoring_config_version,
            "ranked_items": self.ranked_items,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RankingSnapshot":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            session_id=data["session_id"],
            scoring_config_id=data.get("scoring_config_id", "default"),
            scoring_config_version=data.get("scoring_config_version", "v1.0"),
            ranked_items=data.get("ranked_items", []),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
        )
