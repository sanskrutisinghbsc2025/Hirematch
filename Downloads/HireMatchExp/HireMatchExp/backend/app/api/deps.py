
from functools import lru_cache
import os
import sys

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from config import AppConfig, settings
from core.services.session_orchestrator import ScreeningOrchestrator
from core.storage.database import Database


@lru_cache()
def get_config() -> AppConfig:
    return settings


@lru_cache()
def get_database() -> Database:
    cfg = get_config()
    db = Database(cfg.db_path)
    db.initialize_schema()
    return db


@lru_cache()
def get_orchestrator() -> ScreeningOrchestrator:
    db = get_database()
    cfg = get_config()
    return ScreeningOrchestrator(db, cfg)
