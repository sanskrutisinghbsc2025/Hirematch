
import json
from typing import Any, Dict, List, Optional

from core.models.report_models import ExportFormat, GeneratedReportRecord, ReportType
from core.storage.database import Database
from core.utils.logger import logger


class ReportRecordRepository:

    def __init__(self, db: Database):
        self.db = db

    def save(self, record: GeneratedReportRecord) -> GeneratedReportRecord:
        query = """
        INSERT INTO generated_reports (
            id, report_type, session_id, candidate_ids, eval_config_version,
            scoring_config_version, export_format, file_path, metadata, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        params = (
            record.id,
            record.report_type.value if hasattr(record.report_type, "value") else str(record.report_type),
            record.session_id,
            json.dumps(record.candidate_ids),
            record.eval_config_version,
            record.scoring_config_version,
            record.export_format.value if hasattr(record.export_format, "value") else str(record.export_format),
            record.file_path,
            json.dumps(record.metadata),
            record.created_at,
        )

        with self.db.get_connection() as conn:
            conn.execute(query, params)
            conn.commit()

        logger.info(f"Saved generated report record: {record.id} ({record.report_type.value}, {record.export_format.value})")
        return record

    def get(self, report_id: str) -> Optional[GeneratedReportRecord]:
        query = "SELECT * FROM generated_reports WHERE id = ?;"
        with self.db.get_connection() as conn:
            cursor = conn.execute(query, (report_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_record(row)

    def list_by_session(self, session_id: str, report_type: Optional[ReportType] = None) -> List[GeneratedReportRecord]:
        if report_type:
            query = "SELECT * FROM generated_reports WHERE session_id = ? AND report_type = ? ORDER BY created_at DESC;"
            params = (session_id, report_type.value if hasattr(report_type, "value") else str(report_type))
        else:
            query = "SELECT * FROM generated_reports WHERE session_id = ? ORDER BY created_at DESC;"
            params = (session_id,)

        with self.db.get_connection() as conn:
            cursor = conn.execute(query, params)
            return [self._row_to_record(row) for row in cursor.fetchall()]

    def list_all(self, limit: int = 50) -> List[GeneratedReportRecord]:
        query = "SELECT * FROM generated_reports ORDER BY created_at DESC LIMIT ?;"
        with self.db.get_connection() as conn:
            cursor = conn.execute(query, (limit,))
            return [self._row_to_record(row) for row in cursor.fetchall()]

    def delete(self, report_id: str) -> bool:
        query = "DELETE FROM generated_reports WHERE id = ?;"
        with self.db.get_connection() as conn:
            cursor = conn.execute(query, (report_id,))
            conn.commit()
            return cursor.rowcount > 0

    def _row_to_record(self, row: Any) -> GeneratedReportRecord:
        candidate_ids = []
        if row["candidate_ids"]:
            try:
                candidate_ids = json.loads(row["candidate_ids"])
            except Exception:
                candidate_ids = []

        meta = {}
        if row["metadata"]:
            try:
                meta = json.loads(row["metadata"])
            except Exception:
                meta = {}

        return GeneratedReportRecord(
            id=row["id"],
            report_type=ReportType(row["report_type"]),
            session_id=row["session_id"],
            candidate_ids=candidate_ids,
            eval_config_version=row["eval_config_version"] or "v1.0",
            scoring_config_version=row["scoring_config_version"] or "v1.0",
            export_format=ExportFormat(row["export_format"]),
            file_path=row["file_path"],
            metadata=meta,
            created_at=row["created_at"],
        )
