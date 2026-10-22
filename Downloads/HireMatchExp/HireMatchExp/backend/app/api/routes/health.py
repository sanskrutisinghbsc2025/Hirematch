
from fastapi import APIRouter, Depends
from core.storage.database import Database
from backend.app.api.deps import get_database, get_config

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("")
def health_check(
    db: Database = Depends(get_database),
    config = Depends(get_config),
):
    db_ok = False
    try:
        rows = db.execute_query("SELECT 1 as val;")
        db_ok = len(rows) > 0 and rows[0]["val"] == 1
    except Exception:
        db_ok = False

    storage_ok = config.storage_dir.exists()

    return {
        "status": "healthy" if db_ok and storage_ok else "degraded",
        "app_name": config.app_name,
        "version": config.app_version,
        "database_connected": db_ok,
        "storage_ready": storage_ok,
    }
