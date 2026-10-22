
from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import List


@dataclass
class AppConfig:

    app_name: str = "HireMatch"
    app_version: str = "0.1.0-alpha"
    debug: bool = False
    log_level: str = "INFO"

    base_dir: Path = field(default_factory=lambda: Path(__file__).resolve().parent)

    db_path: Path = field(default=Path("data/hirematch.db"))
    storage_dir: Path = field(default=Path("data/storage"))
    cache_dir: Path = field(default=Path("data/cache/models"))
    temp_dir: Path = field(default=Path("data/temp"))
    reports_dir: Path = field(default=Path("data/reports"))

    supported_file_types: List[str] = field(default_factory=lambda: [".pdf", ".docx"])
    
    max_resumes_per_session: int = 100
    max_file_size_bytes: int = 10 * 1024 * 1024
    max_total_upload_size_bytes: int = 200 * 1024 * 1024
    processing_batch_size: int = 10

    semantic_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    spacy_model_name: str = "en_core_web_sm"

    quality_good_threshold: float = 75.0
    quality_moderate_threshold: float = 50.0

    auto_cleanup_temp: bool = True

    def __post_init__(self) -> None:
        if self.max_resumes_per_session <= 0:
            raise ValueError("max_resumes_per_session must be greater than 0")
        if self.max_file_size_bytes <= 0:
            raise ValueError("max_file_size_bytes must be greater than 0")
        if self.max_total_upload_size_bytes <= 0:
            raise ValueError("max_total_upload_size_bytes must be greater than 0")
        if self.processing_batch_size <= 0:
            raise ValueError("processing_batch_size must be greater than 0")
        if self.processing_batch_size > self.max_resumes_per_session:
            raise ValueError("processing_batch_size cannot exceed max_resumes_per_session")
        if not (0.0 <= self.quality_moderate_threshold <= self.quality_good_threshold <= 100.0):
            raise ValueError("quality_moderate_threshold must be <= quality_good_threshold and both between 0 and 100")

        if not self.db_path.is_absolute():
            self.db_path = self.base_dir / self.db_path
        if not self.storage_dir.is_absolute():
            self.storage_dir = self.base_dir / self.storage_dir
        if not self.cache_dir.is_absolute():
            self.cache_dir = self.base_dir / self.cache_dir
        if not self.temp_dir.is_absolute():
            self.temp_dir = self.base_dir / self.temp_dir
        if not self.reports_dir.is_absolute():
            self.reports_dir = self.base_dir / self.reports_dir

    def ensure_directories(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_env(cls) -> "AppConfig":
        base_dir = Path(__file__).resolve().parent

        db_path_env = os.getenv("HIREMATCH_DB_PATH", "data/hirematch.db")
        storage_dir_env = os.getenv("HIREMATCH_STORAGE_DIR", "data/storage")
        cache_dir_env = os.getenv("HIREMATCH_CACHE_DIR", "data/cache/models")
        temp_dir_env = os.getenv("HIREMATCH_TEMP_DIR", "data/temp")

        return cls(
            app_name=os.getenv("HIREMATCH_APP_NAME", "HireMatch"),
            app_version=os.getenv("HIREMATCH_APP_VERSION", "0.1.0-alpha"),
            debug=os.getenv("HIREMATCH_DEBUG", "false").lower() in ("true", "1", "yes"),
            log_level=os.getenv("HIREMATCH_LOG_LEVEL", "INFO").upper(),
            base_dir=base_dir,
            db_path=Path(db_path_env),
            storage_dir=Path(storage_dir_env),
            cache_dir=Path(cache_dir_env),
            temp_dir=Path(temp_dir_env),
            supported_file_types=[".pdf", ".docx"],
            max_resumes_per_session=int(os.getenv("HIREMATCH_MAX_RESUMES_PER_SESSION", "100")),
            max_file_size_bytes=int(os.getenv("HIREMATCH_MAX_FILE_SIZE_BYTES", str(10 * 1024 * 1024))),
            max_total_upload_size_bytes=int(os.getenv("HIREMATCH_MAX_TOTAL_UPLOAD_SIZE_BYTES", str(200 * 1024 * 1024))),
            processing_batch_size=int(os.getenv("HIREMATCH_PROCESSING_BATCH_SIZE", "10")),
            semantic_model_name=os.getenv("HIREMATCH_SEMANTIC_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
            spacy_model_name=os.getenv("HIREMATCH_SPACY_MODEL", "en_core_web_sm"),
            quality_good_threshold=float(os.getenv("HIREMATCH_QUALITY_GOOD_THRESHOLD", "75.0")),
            quality_moderate_threshold=float(os.getenv("HIREMATCH_QUALITY_MODERATE_THRESHOLD", "50.0")),
            auto_cleanup_temp=os.getenv("HIREMATCH_AUTO_CLEANUP", "true").lower() in ("true", "1", "yes"),
        )


settings = AppConfig.from_env()
