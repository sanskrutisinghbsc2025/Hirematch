
from contextlib import contextmanager
from pathlib import Path
import sqlite3
from typing import Any, Generator, List, Optional, Tuple

from core.utils.errors import DatabaseError
from core.utils.logger import logger


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    department TEXT,
    job_category TEXT,
    original_description TEXT NOT NULL,
    parsed_requirements TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS screening_sessions (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    session_name TEXT NOT NULL,
    status TEXT NOT NULL,
    candidate_count INTEGER NOT NULL DEFAULT 0,
    max_resume_count INTEGER NOT NULL DEFAULT 100,
    progress_metadata TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    completed_at TEXT,
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS candidates (
    id TEXT PRIMARY KEY,
    original_filename TEXT NOT NULL,
    file_hash TEXT NOT NULL UNIQUE,
    file_type TEXT NOT NULL,
    extracted_text TEXT,
    text_ref TEXT,
    processing_status TEXT NOT NULL,
    error_info TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS session_candidates (
    session_id TEXT NOT NULL,
    candidate_id TEXT NOT NULL,
    processing_status TEXT NOT NULL,
    manifest_meta TEXT NOT NULL DEFAULT '{}',
    error_info TEXT,
    added_at TEXT NOT NULL,
    PRIMARY KEY (session_id, candidate_id),
    FOREIGN KEY (session_id) REFERENCES screening_sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (candidate_id) REFERENCES candidates(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS extracted_skills (
    id TEXT PRIMARY KEY,
    candidate_id TEXT NOT NULL,
    skill_name TEXT NOT NULL,
    normalized_skill_name TEXT NOT NULL,
    evidence_text TEXT NOT NULL,
    source_location TEXT NOT NULL,
    extraction_method TEXT NOT NULL,
    confidence REAL,
    FOREIGN KEY (candidate_id) REFERENCES candidates(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS work_experience (
    id TEXT PRIMARY KEY,
    candidate_id TEXT NOT NULL,
    job_title TEXT NOT NULL,
    employer TEXT,
    dates TEXT,
    extracted_description TEXT,
    evidence_text TEXT,
    FOREIGN KEY (candidate_id) REFERENCES candidates(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS education_records (
    id TEXT PRIMARY KEY,
    candidate_id TEXT NOT NULL,
    qualification TEXT NOT NULL,
    institution TEXT,
    dates TEXT,
    evidence_text TEXT,
    FOREIGN KEY (candidate_id) REFERENCES candidates(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS evaluation_criteria (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    criterion_name TEXT NOT NULL,
    description TEXT,
    weight REAL NOT NULL DEFAULT 0.2,
    criterion_type TEXT NOT NULL DEFAULT 'REQUIRED',
    matching_config TEXT NOT NULL DEFAULT '{}',
    is_enabled INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS evaluation_evidence (
    id TEXT PRIMARY KEY,
    candidate_id TEXT NOT NULL,
    criterion_id TEXT NOT NULL,
    supporting_text TEXT NOT NULL,
    match_type TEXT NOT NULL,
    evidence_source TEXT NOT NULL,
    evaluation_status TEXT NOT NULL,
    explanation TEXT,
    FOREIGN KEY (candidate_id) REFERENCES candidates(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS candidate_scores (
    candidate_id TEXT PRIMARY KEY,
    overall_score REAL NOT NULL,
    criterion_scores TEXT NOT NULL DEFAULT '{}',
    score_status TEXT NOT NULL,
    explanation TEXT,
    scoring_config_version TEXT NOT NULL,
    evaluated_at TEXT NOT NULL,
    FOREIGN KEY (candidate_id) REFERENCES candidates(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS embedding_cache (
    cache_key TEXT PRIMARY KEY,
    model_name TEXT NOT NULL,
    text_content TEXT NOT NULL,
    embedding_blob BLOB NOT NULL,
    dimension INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evaluation_configurations (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    version TEXT NOT NULL,
    name TEXT NOT NULL,
    config_data TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS candidate_evaluation_records (
    id TEXT PRIMARY KEY,
    candidate_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    config_id TEXT NOT NULL,
    config_version TEXT NOT NULL,
    overall_score REAL NOT NULL,
    evidence_coverage REAL NOT NULL,
    evaluation_status TEXT NOT NULL,
    detailed_results TEXT NOT NULL DEFAULT '[]',
    baseline_summary TEXT NOT NULL DEFAULT '{}',
    semantic_summary TEXT NOT NULL DEFAULT '{}',
    structured_summary TEXT NOT NULL DEFAULT '{}',
    warnings TEXT NOT NULL DEFAULT '[]',
    evaluated_at TEXT NOT NULL,
    FOREIGN KEY (candidate_id) REFERENCES candidates(id) ON DELETE CASCADE,
    FOREIGN KEY (session_id) REFERENCES screening_sessions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS candidate_scoring_records (
    id TEXT PRIMARY KEY,
    candidate_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    evaluation_record_id TEXT NOT NULL,
    scoring_config_id TEXT NOT NULL,
    scoring_config_version TEXT NOT NULL,
    overall_score REAL,
    evidence_coverage REAL NOT NULL,
    completeness_status TEXT NOT NULL,
    criterion_contributions TEXT NOT NULL DEFAULT '[]',
    required_summary TEXT NOT NULL DEFAULT '{}',
    explanation TEXT NOT NULL DEFAULT '',
    warnings TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    FOREIGN KEY (candidate_id) REFERENCES candidates(id) ON DELETE CASCADE,
    FOREIGN KEY (session_id) REFERENCES screening_sessions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS shortlist_records (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    candidate_id TEXT NOT NULL,
    review_status TEXT NOT NULL DEFAULT 'NEEDS_REVIEW',
    reviewer_notes TEXT NOT NULL DEFAULT '',
    scoring_record_id TEXT,
    scoring_config_id TEXT NOT NULL DEFAULT 'default',
    scoring_config_version TEXT NOT NULL DEFAULT 'v1.0',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES screening_sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (candidate_id) REFERENCES candidates(id) ON DELETE CASCADE,
    UNIQUE(session_id, candidate_id)
);

CREATE TABLE IF NOT EXISTS ranking_snapshots (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    scoring_config_id TEXT NOT NULL,
    scoring_config_version TEXT NOT NULL,
    ranked_items TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES screening_sessions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS generated_reports (
    id TEXT PRIMARY KEY,
    report_type TEXT NOT NULL,
    session_id TEXT NOT NULL,
    candidate_ids TEXT NOT NULL DEFAULT '[]',
    eval_config_version TEXT,
    scoring_config_version TEXT,
    export_format TEXT NOT NULL,
    file_path TEXT,
    metadata TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES screening_sessions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS resume_quality_assessments (
    id TEXT PRIMARY KEY,
    candidate_id TEXT NOT NULL,
    session_id TEXT,
    overall_score REAL NOT NULL,
    quality_label TEXT NOT NULL,
    criterion_results TEXT NOT NULL DEFAULT '[]',
    strong_areas TEXT NOT NULL DEFAULT '[]',
    areas_for_improvement TEXT NOT NULL DEFAULT '[]',
    detected_issues TEXT NOT NULL DEFAULT '[]',
    section_completeness TEXT NOT NULL DEFAULT '{}',
    readability_metrics TEXT NOT NULL DEFAULT '{}',
    extraction_diagnostics TEXT NOT NULL DEFAULT '{}',
    executive_summary TEXT NOT NULL DEFAULT '',
    assessed_at TEXT NOT NULL,
    FOREIGN KEY (candidate_id) REFERENCES candidates(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS evaluation_datasets (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    task TEXT NOT NULL,
    description TEXT,
    rubric_version TEXT NOT NULL,
    created_by TEXT NOT NULL,
    is_frozen INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evaluation_dataset_items (
    id TEXT PRIMARY KEY,
    dataset_id TEXT NOT NULL,
    query_text TEXT NOT NULL,
    passage_text TEXT NOT NULL,
    relevance_grade INTEGER NOT NULL DEFAULT 1,
    category TEXT NOT NULL DEFAULT 'GENERAL',
    reviewer_notes TEXT,
    metadata TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY (dataset_id) REFERENCES evaluation_datasets(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS model_benchmark_runs (
    id TEXT PRIMARY KEY,
    run_name TEXT NOT NULL,
    dataset_id TEXT,
    session_id TEXT,
    config_json TEXT NOT NULL DEFAULT '{}',
    results_json TEXT NOT NULL DEFAULT '{}',
    pairwise_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'PENDING',
    error_log TEXT NOT NULL DEFAULT '[]',
    started_at TEXT NOT NULL,
    completed_at TEXT,
    FOREIGN KEY (dataset_id) REFERENCES evaluation_datasets(id) ON DELETE SET NULL,
    FOREIGN KEY (session_id) REFERENCES screening_sessions(id) ON DELETE SET NULL
);

-- Optimization indexes for high-frequency queries
CREATE INDEX IF NOT EXISTS idx_candidates_file_hash ON candidates(file_hash);
CREATE INDEX IF NOT EXISTS idx_session_candidates_session ON session_candidates(session_id);
CREATE INDEX IF NOT EXISTS idx_session_candidates_status ON session_candidates(processing_status);
CREATE INDEX IF NOT EXISTS idx_scores_candidate ON candidate_scores(candidate_id);
CREATE INDEX IF NOT EXISTS idx_evidence_candidate ON evaluation_evidence(candidate_id);
CREATE INDEX IF NOT EXISTS idx_skills_candidate ON extracted_skills(candidate_id);
CREATE INDEX IF NOT EXISTS idx_embedding_cache_model ON embedding_cache(model_name);
CREATE INDEX IF NOT EXISTS idx_eval_config_job ON evaluation_configurations(job_id);
CREATE INDEX IF NOT EXISTS idx_eval_rec_cand ON candidate_evaluation_records(candidate_id);
CREATE INDEX IF NOT EXISTS idx_eval_rec_sess ON candidate_evaluation_records(session_id);
CREATE INDEX IF NOT EXISTS idx_eval_rec_config ON candidate_evaluation_records(config_id);
CREATE INDEX IF NOT EXISTS idx_scoring_rec_cand ON candidate_scoring_records(candidate_id);
CREATE INDEX IF NOT EXISTS idx_scoring_rec_sess ON candidate_scoring_records(session_id);
CREATE INDEX IF NOT EXISTS idx_scoring_rec_config ON candidate_scoring_records(scoring_config_id);
CREATE INDEX IF NOT EXISTS idx_shortlist_sess ON shortlist_records(session_id);
CREATE INDEX IF NOT EXISTS idx_shortlist_cand ON shortlist_records(candidate_id);
CREATE INDEX IF NOT EXISTS idx_shortlist_status ON shortlist_records(review_status);
CREATE INDEX IF NOT EXISTS idx_ranking_snap_sess ON ranking_snapshots(session_id);
CREATE INDEX IF NOT EXISTS idx_reports_sess ON generated_reports(session_id);
CREATE INDEX IF NOT EXISTS idx_reports_type ON generated_reports(report_type);
CREATE INDEX IF NOT EXISTS idx_quality_cand ON resume_quality_assessments(candidate_id);
CREATE INDEX IF NOT EXISTS idx_quality_sess ON resume_quality_assessments(session_id);
CREATE INDEX IF NOT EXISTS idx_bench_dataset ON evaluation_dataset_items(dataset_id);
CREATE INDEX IF NOT EXISTS idx_bench_runs_dataset ON model_benchmark_runs(dataset_id);
CREATE INDEX IF NOT EXISTS idx_bench_runs_session ON model_benchmark_runs(session_id);
CREATE INDEX IF NOT EXISTS idx_bench_runs_status ON model_benchmark_runs(status);
"""


class Database:

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        conn = None
        try:
            conn = sqlite3.connect(
                str(self.db_path),
                timeout=30.0,
                check_same_thread=False,
            )
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA synchronous = NORMAL;")
            conn.execute("PRAGMA cache_size = -64000;")
            conn.execute("PRAGMA temp_store = MEMORY;")
            yield conn
            conn.commit()
        except sqlite3.Error as e:
            if conn:
                conn.rollback()
            logger.error(f"Database error on {self.db_path}: {e}")
            raise DatabaseError(f"Database error: {e}", user_message="A storage operation failed.") from e
        finally:
            if conn:
                conn.close()

    def initialize_schema(self) -> None:
        try:
            with self.get_connection() as conn:
                conn.executescript(SCHEMA_SQL)
                try:
                    conn.execute("ALTER TABLE candidates ADD COLUMN structured_data TEXT DEFAULT '{}';")
                except sqlite3.OperationalError:
                    pass
            logger.info(f"Database initialized successfully at {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize database schema: {e}")
            raise DatabaseError(f"Schema initialization failed: {e}") from e

    def execute_query(self, sql: str, params: Tuple[Any, ...] = ()) -> List[sqlite3.Row]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            return cursor.fetchall()

    def execute_non_query(self, sql: str, params: Tuple[Any, ...] = ()) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            return cursor.rowcount

    def execute_write(self, sql: str, params: Tuple[Any, ...] = ()) -> int:
        return self.execute_non_query(sql, params)

    def execute_batch(self, sql: str, params_list: List[Tuple[Any, ...]]) -> int:
        if not params_list:
            return 0
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(sql, params_list)
            return cursor.rowcount
