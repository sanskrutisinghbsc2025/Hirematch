
from pathlib import Path
from typing import Any, BinaryIO, List, NamedTuple, Optional, Union

from config import AppConfig, settings
from core.models.enums import FileType
from core.utils.errors import (
    BatchSizeExceededError,
    FileSizeExceededError,
    FileValidationError,
    SessionLimitExceededError,
    UnsupportedFileTypeError,
)
from core.utils.logger import logger
from core.utils.sanitizer import sanitize_filename


class UploadedFileMeta(NamedTuple):
    filename: str
    size_bytes: int
    content: Union[bytes, BinaryIO]
    file_type: FileType


class FileValidatorService:

    def __init__(self, config: Optional[AppConfig] = None):
        self.config = config or settings

    def detect_file_type(self, filename: str) -> FileType:
        suffix = Path(filename).suffix.lower()
        if suffix == ".pdf":
            return FileType.PDF
        elif suffix == ".docx":
            return FileType.DOCX
        return FileType.UNKNOWN

    def validate_file(self, filename: str, size_bytes: int, content: Optional[bytes] = None) -> UploadedFileMeta:
        file_type = self.detect_file_type(filename)
        if file_type == FileType.UNKNOWN:
            raise UnsupportedFileTypeError(
                f"Unsupported file type for '{filename}'. Allowed: {', '.join(self.config.supported_file_types)}",
                user_message=f"'{filename}' has an unsupported file format. Please upload PDF or DOCX files only.",
            )
        safe_name = sanitize_filename(filename)

        if size_bytes <= 0:
            raise FileValidationError(
                f"File '{filename}' is empty (0 bytes).",
                user_message=f"'{filename}' appears to be empty.",
            )

        if size_bytes > self.config.max_file_size_bytes:
            max_mb = self.config.max_file_size_bytes / (1024 * 1024)
            actual_mb = size_bytes / (1024 * 1024)
            raise FileSizeExceededError(
                f"File '{filename}' ({actual_mb:.2f} MB) exceeds maximum allowed size ({max_mb:.2f} MB).",
                user_message=f"'{filename}' ({actual_mb:.1f}MB) exceeds the {max_mb:.0f}MB limit.",
            )

        if content:
            if file_type == FileType.PDF and not content.startswith(b"%PDF"):
                raise FileValidationError(
                    f"File '{filename}' does not have a valid PDF header signature.",
                    user_message=f"'{filename}' does not appear to be a valid PDF document.",
                )
            elif file_type == FileType.DOCX and not content.startswith(b"PK"):
                raise FileValidationError(
                    f"File '{filename}' does not have a valid DOCX zip header.",
                    user_message=f"'{filename}' does not appear to be a valid DOCX document.",
                )

        return UploadedFileMeta(
            filename=safe_name,
            size_bytes=size_bytes,
            content=content or b"",
            file_type=file_type,
        )

    def validate_batch(self, files: List[Any], current_session_count: int = 0) -> None:
        new_count = len(files)
        total_projected = current_session_count + new_count

        if total_projected > self.config.max_resumes_per_session:
            raise SessionLimitExceededError(
                f"Cannot add {new_count} resumes. Session limit is {self.config.max_resumes_per_session} "
                f"(current count: {current_session_count}, projected: {total_projected}).",
                user_message=(
                    f"Adding {new_count} resumes would exceed the maximum limit of "
                    f"{self.config.max_resumes_per_session} resumes per session. Currently enrolled: {current_session_count}."
                ),
            )

        total_bytes = 0
        for f in files:
            size = getattr(f, "size", None)
            if size is None and hasattr(f, "getvalue"):
                size = len(f.getvalue())
            elif size is None and isinstance(f, bytes):
                size = len(f)
            elif size is None and hasattr(f, "stat"):
                size = f.stat().st_size
            total_bytes += (size or 0)

        if total_bytes > self.config.max_total_upload_size_bytes:
            max_mb = self.config.max_total_upload_size_bytes / (1024 * 1024)
            actual_mb = total_bytes / (1024 * 1024)
            raise BatchSizeExceededError(
                f"Total upload size ({actual_mb:.2f} MB) exceeds maximum allowed batch limit ({max_mb:.2f} MB).",
                user_message=f"Total upload size ({actual_mb:.1f}MB) exceeds the allowed limit ({max_mb:.0f}MB).",
            )
