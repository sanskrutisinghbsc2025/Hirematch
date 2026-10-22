
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class EducationRecord:

    qualification: str
    institution: Optional[str] = None
    dates: Optional[str] = None
    evidence_text: str = ""

    def __post_init__(self) -> None:
        if not self.qualification or not self.qualification.strip():
            raise ValueError("qualification cannot be empty.")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "qualification": self.qualification,
            "institution": self.institution,
            "dates": self.dates,
            "evidence_text": self.evidence_text,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EducationRecord":
        return cls(
            qualification=data["qualification"],
            institution=data.get("institution"),
            dates=data.get("dates"),
            evidence_text=data.get("evidence_text", ""),
        )
