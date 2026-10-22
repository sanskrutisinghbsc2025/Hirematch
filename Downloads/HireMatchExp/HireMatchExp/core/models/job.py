
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import uuid


@dataclass
class Job:

    title: str
    original_description: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    department: Optional[str] = None
    job_category: Optional[str] = None
    parsed_requirements: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self) -> None:
        if not self.title or not self.title.strip():
            raise ValueError("Job title cannot be empty.")
        if not self.original_description or not self.original_description.strip():
            raise ValueError("Job original_description cannot be empty.")
        if not self.id:
            self.id = str(uuid.uuid4())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "department": self.department,
            "job_category": self.job_category,
            "original_description": self.original_description,
            "parsed_requirements": self.parsed_requirements,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Job":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            title=data["title"],
            department=data.get("department"),
            job_category=data.get("job_category"),
            original_description=data["original_description"],
            parsed_requirements=data.get("parsed_requirements", {}),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            updated_at=data.get("updated_at", datetime.now(timezone.utc).isoformat()),
        )
