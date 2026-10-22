
from typing import List
from pydantic import BaseModel


class SettingsResponse(BaseModel):
    app_name: str
    app_version: str
    max_resumes_per_session: int
    max_file_size_mb: int
    max_total_upload_mb: int
    processing_batch_size: int
    supported_file_types: List[str]
    semantic_model_name: str
    spacy_model_name: str
    storage_dir: str
    db_path: str
    cache_dir: str
