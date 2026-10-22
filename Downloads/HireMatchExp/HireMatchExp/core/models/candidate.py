
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import uuid

from core.models.enums import FileType, ProcessingStatus


@dataclass
class Candidate:

    original_filename: str
    file_hash: str
    file_type: FileType
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    extracted_text: Optional[str] = None
    text_ref: Optional[str] = None
    processing_status: ProcessingStatus = ProcessingStatus.PENDING
    error_info: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self) -> None:
        if not self.original_filename or not self.original_filename.strip():
            raise ValueError("Candidate original_filename cannot be empty.")
        if not self.file_hash or len(self.file_hash) != 64:
            raise ValueError("Candidate file_hash must be a valid 64-character SHA-256 string.")
        if not isinstance(self.file_type, FileType):
            if isinstance(self.file_type, str):
                self.file_type = FileType(self.file_type.upper())
            else:
                raise ValueError(f"Invalid file_type: {self.file_type}")
        if not isinstance(self.processing_status, ProcessingStatus):
            if isinstance(self.processing_status, str):
                self.processing_status = ProcessingStatus(self.processing_status.upper())
            else:
                raise ValueError(f"Invalid processing_status: {self.processing_status}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "original_filename": self.original_filename,
            "file_hash": self.file_hash,
            "file_type": self.file_type.value,
            "extracted_text": self.extracted_text,
            "text_ref": self.text_ref,
            "processing_status": self.processing_status.value,
            "error_info": self.error_info,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Candidate":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            original_filename=data["original_filename"],
            file_hash=data["file_hash"],
            file_type=FileType(data["file_type"]),
            extracted_text=data.get("extracted_text"),
            text_ref=data.get("text_ref"),
            processing_status=ProcessingStatus(data.get("processing_status", ProcessingStatus.PENDING.value)),
            error_info=data.get("error_info"),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
        )
