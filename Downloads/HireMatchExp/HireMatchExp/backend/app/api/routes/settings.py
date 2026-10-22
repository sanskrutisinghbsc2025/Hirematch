
from fastapi import APIRouter, Depends

from backend.app.api.deps import get_config
from backend.app.api.schemas.settings_schemas import SettingsResponse
from config import AppConfig

router = APIRouter(prefix="/settings", tags=["System Settings"])


@router.get("", response_model=SettingsResponse)
def get_system_settings(config: AppConfig = Depends(get_config)):
    return SettingsResponse(
        app_name=config.app_name,
        app_version=config.app_version,
        max_resumes_per_session=config.max_resumes_per_session,
        max_file_size_mb=config.max_file_size_bytes // (1024 * 1024),
        max_total_upload_mb=config.max_total_upload_size_bytes // (1024 * 1024),
        processing_batch_size=config.processing_batch_size,
        supported_file_types=config.supported_file_types,
        semantic_model_name=config.semantic_model_name,
        spacy_model_name=config.spacy_model_name,
        storage_dir=str(config.storage_dir),
        db_path=str(config.db_path),
        cache_dir=str(config.cache_dir),
    )
