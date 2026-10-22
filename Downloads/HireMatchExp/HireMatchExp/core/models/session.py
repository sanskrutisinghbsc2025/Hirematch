
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import uuid

from core.models.enums import SessionStatus


@dataclass
class ScreeningSession:

    job_id: str
    session_name: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: SessionStatus = SessionStatus.CREATED
    candidate_count: int = 0
    max_resume_count: int = 100
    progress_metadata: Dict[str, Any] = field(default_factory=lambda: {
        "total": 0,
        "processed": 0,
        "failed": 0,
        "pending": 0,
        "percent_complete": 0.0,
    })
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.job_id:
            raise ValueError("job_id cannot be empty.")
        if not self.session_name or not self.session_name.strip():
            raise ValueError("session_name cannot be empty.")
        if self.max_resume_count <= 0:
            raise ValueError("max_resume_count must be greater than 0.")
        if self.candidate_count < 0:
            raise ValueError("candidate_count cannot be negative.")
        if self.candidate_count > self.max_resume_count:
            raise ValueError(
                f"candidate_count ({self.candidate_count}) exceeds max_resume_count ({self.max_resume_count})."
            )
        if not isinstance(self.status, SessionStatus):
            if isinstance(self.status, str):
                self.status = SessionStatus(self.status.upper())
            else:
                raise ValueError(f"Invalid status: {self.status}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "job_id": self.job_id,
            "session_name": self.session_name,
            "status": self.status.value,
            "candidate_count": self.candidate_count,
            "max_resume_count": self.max_resume_count,
            "progress_metadata": self.progress_metadata,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScreeningSession":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            job_id=data["job_id"],
            session_name=data["session_name"],
            status=SessionStatus(data.get("status", SessionStatus.CREATED.value)),
            candidate_count=int(data.get("candidate_count", 0)),
            max_resume_count=int(data.get("max_resume_count", 100)),
            progress_metadata=data.get("progress_metadata", {}),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            completed_at=data.get("completed_at"),
        )
