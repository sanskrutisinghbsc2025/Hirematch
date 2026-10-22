
from datetime import datetime, timezone
from typing import Dict, List, Optional
import sqlite3

from core.models.enums import ShortlistReviewStatus
from core.models.scoring_models import ShortlistRecord
from core.storage.database import Database
from core.utils.logger import logger


class ShortlistRepository:

    def __init__(self, db: Database):
        self.db = db

    def save(self, record: ShortlistRecord) -> None:
        query = """
        INSERT INTO shortlist_records (
            id, session_id, candidate_id, review_status, reviewer_notes,
            scoring_record_id, scoring_config_id, scoring_config_version,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(session_id, candidate_id) DO UPDATE SET
            review_status = excluded.review_status,
            reviewer_notes = excluded.reviewer_notes,
            scoring_record_id = excluded.scoring_record_id,
            scoring_config_id = excluded.scoring_config_id,
            scoring_config_version = excluded.scoring_config_version,
            updated_at = excluded.updated_at;
        """
        with self.db.get_connection() as conn:
            conn.execute(
                query,
                (
                    record.id,
                    record.session_id,
                    record.candidate_id,
                    record.review_status.value,
                    record.reviewer_notes,
                    record.scoring_record_id,
                    record.scoring_config_id,
                    record.scoring_config_version,
                    record.created_at,
                    record.updated_at,
                ),
            )
        logger.debug(f"Saved ShortlistRecord for candidate {record.candidate_id} in session {record.session_id}")

    def get(self, session_id: str, candidate_id: str) -> Optional[ShortlistRecord]:
        query = """
        SELECT * FROM shortlist_records
        WHERE session_id = ? AND candidate_id = ?;
        """
        with self.db.get_connection() as conn:
            cursor = conn.execute(query, (session_id, candidate_id))
            row = cursor.fetchone()
            if row:
                return self._row_to_record(row)
        return None

    def list_by_session(
        self, session_id: str, status: Optional[ShortlistReviewStatus] = None
    ) -> List[ShortlistRecord]:
        query = """
        SELECT * FROM shortlist_records
        WHERE session_id = ?
        """
        params = [session_id]
        if status:
            query += " AND review_status = ?"
            params.append(status.value)
        query += " ORDER BY updated_at DESC;"

        with self.db.get_connection() as conn:
            cursor = conn.execute(query, tuple(params))
            rows = cursor.fetchall()
            return [self._row_to_record(r) for r in rows]

    def list_by_candidate(self, candidate_id: str) -> List[ShortlistRecord]:
        query = """
        SELECT * FROM shortlist_records
        WHERE candidate_id = ?
        ORDER BY updated_at DESC;
        """
        with self.db.get_connection() as conn:
            cursor = conn.execute(query, (candidate_id,))
            rows = cursor.fetchall()
            return [self._row_to_record(r) for r in rows]

    def delete(self, session_id: str, candidate_id: str) -> bool:
        query = """
        DELETE FROM shortlist_records
        WHERE session_id = ? AND candidate_id = ?;
        """
        with self.db.get_connection() as conn:
            cursor = conn.execute(query, (session_id, candidate_id))
            return cursor.rowcount > 0

    def count_by_status(self, session_id: str) -> Dict[str, int]:
        query = """
        SELECT review_status, COUNT(*) as count
        FROM shortlist_records
        WHERE session_id = ?
        GROUP BY review_status;
        """
        counts = {status.value: 0 for status in ShortlistReviewStatus}
        with self.db.get_connection() as conn:
            cursor = conn.execute(query, (session_id,))
            for row in cursor.fetchall():
                counts[row["review_status"]] = row["count"]
        return counts

    def get_status_counts(self, session_id: str) -> Dict[str, int]:
        return self.count_by_status(session_id)

    def _row_to_record(self, row: sqlite3.Row) -> ShortlistRecord:
        return ShortlistRecord(
            id=row["id"],
            session_id=row["session_id"],
            candidate_id=row["candidate_id"],
            review_status=ShortlistReviewStatus(row["review_status"]),
            reviewer_notes=row["reviewer_notes"],
            scoring_record_id=row["scoring_record_id"],
            scoring_config_id=row["scoring_config_id"],
            scoring_config_version=row["scoring_config_version"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
