
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class WorkExperience:

    job_title: str
    employer: Optional[str] = None
    dates: Optional[str] = None
    extracted_description: str = ""
    evidence_text: str = ""

    @property
    def company(self) -> Optional[str]:
        return self.employer

    @property
    def title(self) -> str:
        return self.job_title

    def __post_init__(self) -> None:
        if not self.job_title or not self.job_title.strip():
            raise ValueError("job_title cannot be empty.")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_title": self.job_title,
            "employer": self.employer,
            "dates": self.dates,
            "extracted_description": self.extracted_description,
            "evidence_text": self.evidence_text,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkExperience":
        return cls(
            job_title=data["job_title"],
            employer=data.get("employer"),
            dates=data.get("dates"),
            extracted_description=data.get("extracted_description", ""),
            evidence_text=data.get("evidence_text", ""),
        )
