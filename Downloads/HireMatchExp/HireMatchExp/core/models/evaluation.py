
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from core.models.enums import (
    CriterionCategory,
    CriterionType,
    EvaluationMode,
    EvidenceDisagreementType,
    MatchStatus,
    MatchType,
    MatchingRuleType,
    ScoreStatus,
    SemanticSimilarityTier,
)


@dataclass
class EvaluationCriterion:

    criterion_name: str
    description: str = ""
    weight: float = 0.2
    criterion_type: CriterionType = CriterionType.REQUIRED
    category: CriterionCategory = CriterionCategory.TECHNICAL_SKILL
    matching_config: Dict[str, Any] = field(default_factory=dict)
    evidence_requirements: Dict[str, Any] = field(default_factory=dict)
    evaluation_notes: str = ""
    is_enabled: bool = True
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self) -> None:
        if not self.criterion_name or not self.criterion_name.strip():
            raise ValueError("criterion_name cannot be empty.")
        if not (0.0 <= self.weight <= 1.0):
            raise ValueError(f"weight must be between 0.0 and 1.0, got {self.weight}")
        if not isinstance(self.criterion_type, CriterionType):
            if isinstance(self.criterion_type, str):
                self.criterion_type = CriterionType(self.criterion_type.upper())
            else:
                raise ValueError(f"Invalid criterion_type: {self.criterion_type}")
        if not isinstance(self.category, CriterionCategory):
            if isinstance(self.category, str):
                self.category = CriterionCategory(self.category.upper())
            else:
                self.category = CriterionCategory.TECHNICAL_SKILL

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "criterion_name": self.criterion_name,
            "description": self.description,
            "weight": self.weight,
            "criterion_type": self.criterion_type.value,
            "category": self.category.value,
            "matching_config": self.matching_config,
            "evidence_requirements": self.evidence_requirements,
            "evaluation_notes": self.evaluation_notes,
            "is_enabled": self.is_enabled,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvaluationCriterion":
        cat_raw = data.get("category")
        category_val = (
            CriterionCategory(cat_raw.upper())
            if cat_raw and cat_raw.upper() in CriterionCategory._value2member_map_
            else CriterionCategory.TECHNICAL_SKILL
        )
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            criterion_name=data["criterion_name"],
            description=data.get("description", ""),
            weight=float(data.get("weight", 0.2)),
            criterion_type=CriterionType(data.get("criterion_type", CriterionType.REQUIRED.value)),
            category=category_val,
            matching_config=data.get("matching_config", {}),
            evidence_requirements=data.get("evidence_requirements", {}),
            evaluation_notes=data.get("evaluation_notes", ""),
            is_enabled=data.get("is_enabled", True),
        )


@dataclass
class EvaluationEvidence:

    candidate_id: str
    criterion_id: str
    supporting_text: str
    match_type: MatchType = MatchType.NOT_EVALUATED
    evidence_source: str = "general"
    evaluation_status: str = "PENDING"
    explanation: str = ""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise ValueError("candidate_id cannot be empty.")
        if not self.criterion_id:
            raise ValueError("criterion_id cannot be empty.")
        if not isinstance(self.match_type, MatchType):
            if isinstance(self.match_type, str):
                self.match_type = MatchType(self.match_type.upper())
            else:
                raise ValueError(f"Invalid match_type: {self.match_type}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "candidate_id": self.candidate_id,
            "criterion_id": self.criterion_id,
            "supporting_text": self.supporting_text,
            "match_type": self.match_type.value,
            "evidence_source": self.evidence_source,
            "evaluation_status": self.evaluation_status,
            "explanation": self.explanation,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvaluationEvidence":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            candidate_id=data["candidate_id"],
            criterion_id=data["criterion_id"],
            supporting_text=data.get("supporting_text", ""),
            match_type=MatchType(data.get("match_type", MatchType.NOT_EVALUATED.value)),
            evidence_source=data.get("evidence_source", "general"),
            evaluation_status=data.get("evaluation_status", "PENDING"),
            explanation=data.get("explanation", ""),
        )


@dataclass
class SemanticMatchResult:

    passage_text: str
    source_section: str
    similarity_score: float
    similarity_tier: SemanticSimilarityTier
    chunk_index: int = 0
    model_id: str = ""
    char_start: int = 0
    char_end: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passage_text": self.passage_text,
            "source_section": self.source_section,
            "similarity_score": round(self.similarity_score, 4),
            "similarity_tier": self.similarity_tier.value,
            "chunk_index": self.chunk_index,
            "model_id": self.model_id,
            "char_start": self.char_start,
            "char_end": self.char_end,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SemanticMatchResult":
        tier_str = data.get("similarity_tier", SemanticSimilarityTier.INSUFFICIENT.value)
        tier_val = SemanticSimilarityTier(tier_str) if isinstance(tier_str, str) else tier_str
        return cls(
            passage_text=data["passage_text"],
            source_section=data.get("source_section", "GENERAL"),
            similarity_score=float(data.get("similarity_score", 0.0)),
            similarity_tier=tier_val,
            chunk_index=int(data.get("chunk_index", 0)),
            model_id=data.get("model_id", ""),
            char_start=int(data.get("char_start", 0)),
            char_end=int(data.get("char_end", 0)),
        )


@dataclass
class CriterionEvaluationResult:

    criterion_id: str
    criterion_name: str
    criterion_type: CriterionType
    weight: float
    match_status: MatchStatus
    score: float
    matched_terms: List[str] = field(default_factory=list)
    supporting_evidence: List[str] = field(default_factory=list)
    evidence_sources: List[str] = field(default_factory=list)
    matching_method: str = "exact"
    explanation: str = ""
    confidence: float = 1.0
    is_negative_context: bool = False
    semantic_score: Optional[float] = None
    similarity_tier: Optional[SemanticSimilarityTier] = None
    top_passages: List[Dict[str, Any]] = field(default_factory=list)

    category: Optional[CriterionCategory] = None
    disagreement_type: EvidenceDisagreementType = EvidenceDisagreementType.NONE
    conflict_explanation: str = ""
    synthesis_items: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def baseline_score(self) -> float:
        return self.score


    def to_dict(self) -> Dict[str, Any]:
        return {
            "criterion_id": self.criterion_id,
            "criterion_name": self.criterion_name,
            "criterion_type": self.criterion_type.value,
            "weight": self.weight,
            "match_status": self.match_status.value,
            "score": self.score,
            "matched_terms": self.matched_terms,
            "supporting_evidence": self.supporting_evidence,
            "evidence_sources": self.evidence_sources,
            "matching_method": self.matching_method,
            "explanation": self.explanation,
            "confidence": self.confidence,
            "is_negative_context": self.is_negative_context,
            "semantic_score": self.semantic_score,
            "similarity_tier": self.similarity_tier.value if self.similarity_tier else None,
            "top_passages": self.top_passages,
            "category": self.category.value if self.category else None,
            "disagreement_type": self.disagreement_type.value,
            "conflict_explanation": self.conflict_explanation,
            "synthesis_items": self.synthesis_items,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CriterionEvaluationResult":
        tier = data.get("similarity_tier")
        cat_raw = data.get("category")
        category_val = (
            CriterionCategory(cat_raw.upper())
            if cat_raw and cat_raw.upper() in CriterionCategory._value2member_map_
            else None
        )
        disagree_raw = data.get("disagreement_type")
        disagreement_val = (
            EvidenceDisagreementType(disagree_raw.upper())
            if disagree_raw and disagree_raw.upper() in EvidenceDisagreementType._value2member_map_
            else EvidenceDisagreementType.NONE
        )
        return cls(
            criterion_id=data["criterion_id"],
            criterion_name=data["criterion_name"],
            criterion_type=CriterionType(data.get("criterion_type", CriterionType.REQUIRED.value)),
            weight=float(data.get("weight", 0.0)),
            match_status=MatchStatus(data.get("match_status", MatchStatus.NOT_EVALUATED.value)),
            score=float(data.get("score", 0.0)),
            matched_terms=data.get("matched_terms", []),
            supporting_evidence=data.get("supporting_evidence", []),
            evidence_sources=data.get("evidence_sources", []),
            matching_method=data.get("matching_method", "exact"),
            explanation=data.get("explanation", ""),
            confidence=float(data.get("confidence", 1.0)),
            is_negative_context=bool(data.get("is_negative_context", False)),
            semantic_score=float(data["semantic_score"]) if data.get("semantic_score") is not None else None,
            similarity_tier=SemanticSimilarityTier(tier) if tier else None,
            top_passages=data.get("top_passages", []),
            category=category_val,
            disagreement_type=disagreement_val,
            conflict_explanation=data.get("conflict_explanation", ""),
            synthesis_items=data.get("synthesis_items", []),
        )


@dataclass
class CandidateEvaluationRecord:

    candidate_id: str
    session_id: str
    config_id: str
    config_version: str
    overall_score: float
    evidence_coverage: float
    evaluation_status: str = "CALCULATED"
    criterion_results: List[CriterionEvaluationResult] = field(default_factory=list)
    baseline_summary: Dict[str, Any] = field(default_factory=dict)
    semantic_summary: Dict[str, Any] = field(default_factory=dict)
    structured_summary: Dict[str, Any] = field(default_factory=dict)
    unmet_mandatory_criteria: List[str] = field(default_factory=list)
    conflicting_criteria: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    evaluated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "candidate_id": self.candidate_id,
            "session_id": self.session_id,
            "config_id": self.config_id,
            "config_version": self.config_version,
            "overall_score": self.overall_score,
            "evidence_coverage": self.evidence_coverage,
            "evaluation_status": self.evaluation_status,
            "criterion_results": [r.to_dict() for r in self.criterion_results],
            "baseline_summary": self.baseline_summary,
            "semantic_summary": self.semantic_summary,
            "structured_summary": self.structured_summary,
            "unmet_mandatory_criteria": self.unmet_mandatory_criteria,
            "conflicting_criteria": self.conflicting_criteria,
            "warnings": self.warnings,
            "evaluated_at": self.evaluated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CandidateEvaluationRecord":
        raw_results = data.get("criterion_results", [])
        results = [CriterionEvaluationResult.from_dict(r) for r in raw_results]
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            candidate_id=data["candidate_id"],
            session_id=data["session_id"],
            config_id=data.get("config_id", "default"),
            config_version=data.get("config_version", "v1.0"),
            overall_score=float(data.get("overall_score", 0.0)),
            evidence_coverage=float(data.get("evidence_coverage", 0.0)),
            evaluation_status=data.get("evaluation_status", "CALCULATED"),
            criterion_results=results,
            baseline_summary=data.get("baseline_summary", {}),
            semantic_summary=data.get("semantic_summary", {}),
            structured_summary=data.get("structured_summary", {}),
            unmet_mandatory_criteria=data.get("unmet_mandatory_criteria", []),
            conflicting_criteria=data.get("conflicting_criteria", []),
            warnings=data.get("warnings", []),
            evaluated_at=data.get("evaluated_at", datetime.now(timezone.utc).isoformat()),
        )


@dataclass
class CandidateScore:

    candidate_id: str
    overall_score: float
    criterion_scores: Dict[str, Any] = field(default_factory=dict)
    score_status: ScoreStatus = ScoreStatus.CALCULATED
    explanation: str = ""
    scoring_config_version: str = "v1.0"
    evaluated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise ValueError("candidate_id cannot be empty.")
        if not (0.0 <= self.overall_score <= 100.0):
            raise ValueError(f"overall_score must be between 0.0 and 100.0, got {self.overall_score}")
        if not isinstance(self.score_status, ScoreStatus):
            if isinstance(self.score_status, str):
                self.score_status = ScoreStatus(self.score_status.upper())
            else:
                raise ValueError(f"Invalid score_status: {self.score_status}")

    @property
    def evidence_coverage(self) -> float:
        return float(self.criterion_scores.get("evidence_coverage", 0.0))

    @property
    def required_supported(self) -> bool:
        return bool(self.criterion_scores.get("required_supported", True))

    @property
    def required_unmet_count(self) -> int:
        return int(self.criterion_scores.get("required_unmet_count", 0))

    @property
    def evaluation_mode(self) -> str:
        return str(self.criterion_scores.get("evaluation_mode", "BASELINE"))

    @property
    def baseline_score(self) -> Optional[float]:
        val = self.criterion_scores.get("baseline_score")
        return float(val) if val is not None else None

    @property
    def semantic_score(self) -> Optional[float]:
        val = self.criterion_scores.get("semantic_score")
        return float(val) if val is not None else None

    @property
    def combined_score(self) -> Optional[float]:
        val = self.criterion_scores.get("combined_score")
        return float(val) if val is not None else None

    @property
    def semantic_model(self) -> Optional[str]:
        return self.criterion_scores.get("semantic_model")

    @property
    def criterion_results(self) -> List[CriterionEvaluationResult]:
        raw_list = self.criterion_scores.get("criteria", [])
        return [CriterionEvaluationResult.from_dict(item) for item in raw_list]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "overall_score": self.overall_score,
            "criterion_scores": self.criterion_scores,
            "score_status": self.score_status.value,
            "explanation": self.explanation,
            "scoring_config_version": self.scoring_config_version,
            "evaluated_at": self.evaluated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CandidateScore":
        return cls(
            candidate_id=data["candidate_id"],
            overall_score=float(data["overall_score"]),
            criterion_scores=data.get("criterion_scores", {}),
            score_status=ScoreStatus(data.get("score_status", ScoreStatus.CALCULATED.value)),
            explanation=data.get("explanation", ""),
            scoring_config_version=data.get("scoring_config_version", "v1.0"),
            evaluated_at=data.get("evaluated_at", datetime.now(timezone.utc).isoformat()),
        )
