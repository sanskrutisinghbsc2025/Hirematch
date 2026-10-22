
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from core.models.evaluation import EvaluationCriterion


@dataclass
class EvaluationConfiguration:

    job_id: str
    version: str = "v1.0"
    name: str = "Default Evaluation Configuration"
    criteria: List[EvaluationCriterion] = field(default_factory=list)
    aggregation_method: str = "weighted_average"
    missing_evidence_behavior: str = "neutral"
    baseline_weight: float = 0.5
    semantic_weight: float = 0.5
    semantic_thresholds: Dict[str, float] = field(
        default_factory=lambda: {"strong": 0.70, "possible": 0.50, "weak": 0.35}
    )
    notes: str = ""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self) -> None:
        if not self.job_id:
            raise ValueError("job_id cannot be empty.")
        if not self.version:
            raise ValueError("version cannot be empty.")
        if not (0.0 <= self.baseline_weight <= 1.0):
            raise ValueError(f"baseline_weight must be between 0.0 and 1.0, got {self.baseline_weight}")
        if not (0.0 <= self.semantic_weight <= 1.0):
            raise ValueError(f"semantic_weight must be between 0.0 and 1.0, got {self.semantic_weight}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "job_id": self.job_id,
            "version": self.version,
            "name": self.name,
            "criteria": [c.to_dict() for c in self.criteria],
            "aggregation_method": self.aggregation_method,
            "missing_evidence_behavior": self.missing_evidence_behavior,
            "baseline_weight": self.baseline_weight,
            "semantic_weight": self.semantic_weight,
            "semantic_thresholds": self.semantic_thresholds,
            "notes": self.notes,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvaluationConfiguration":
        raw_criteria = data.get("criteria", [])
        criteria = [EvaluationCriterion.from_dict(c) for c in raw_criteria]
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            job_id=data["job_id"],
            version=data.get("version", "v1.0"),
            name=data.get("name", "Default Evaluation Configuration"),
            criteria=criteria,
            aggregation_method=data.get("aggregation_method", "weighted_average"),
            missing_evidence_behavior=data.get("missing_evidence_behavior", "neutral"),
            baseline_weight=float(data.get("baseline_weight", 0.5)),
            semantic_weight=float(data.get("semantic_weight", 0.5)),
            semantic_thresholds=data.get(
                "semantic_thresholds", {"strong": 0.70, "possible": 0.50, "weak": 0.35}
            ),
            notes=data.get("notes", ""),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
        )

    @classmethod
    def create_default(
        cls,
        job_id: str,
        criteria: Optional[List[EvaluationCriterion]] = None,
        version: str = "v1.0",
        name: str = "Default Evaluation Configuration",
    ) -> "EvaluationConfiguration":
        return cls(
            job_id=job_id,
            version=version,
            name=name,
            criteria=criteria or [],
            baseline_weight=0.5,
            semantic_weight=0.5,
        )
