
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class ExtractedSkill:

    skill_name: str
    normalized_skill_name: str
    evidence_text: str
    source_location: str = "general"
    extraction_method: str = "exact_match"
    confidence: Optional[float] = None

    @property
    def canonical_name(self) -> str:
        return self.normalized_skill_name

    @property
    def evidence_sentence(self) -> str:
        return self.evidence_text

    def __post_init__(self) -> None:
        if not self.skill_name or not self.skill_name.strip():
            raise ValueError("skill_name cannot be empty.")
        if not self.normalized_skill_name:
            self.normalized_skill_name = self.skill_name.strip().lower()
        if self.confidence is not None and not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"confidence must be between 0.0 and 1.0, got {self.confidence}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill_name": self.skill_name,
            "normalized_skill_name": self.normalized_skill_name,
            "evidence_text": self.evidence_text,
            "source_location": self.source_location,
            "extraction_method": self.extraction_method,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExtractedSkill":
        return cls(
            skill_name=data["skill_name"],
            normalized_skill_name=data.get("normalized_skill_name", data["skill_name"].lower()),
            evidence_text=data.get("evidence_text", ""),
            source_location=data.get("source_location", "general"),
            extraction_method=data.get("extraction_method", "exact_match"),
            confidence=data.get("confidence"),
        )
