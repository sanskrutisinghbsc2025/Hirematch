
import json
from typing import Any, Dict, List, Optional
import sqlite3

from core.models.enums import ScoreCompleteness
from core.models.scoring_models import (
    CandidateScoringRecord,
    CriterionContribution,
    RankingSnapshot,
    RequiredCriteriaSummary,
)
from core.storage.database import Database
from core.utils.logger import logger


class ScoringRecordRepository:

    def __init__(self, db: Database):
        self.db = db

    def save(self, record: CandidateScoringRecord) -> None:
        query = """
        INSERT OR REPLACE INTO candidate_scoring_records (
            id, candidate_id, session_id, evaluation_record_id,
            scoring_config_id, scoring_config_version, overall_score,
            evidence_coverage, completeness_status, criterion_contributions,
            required_summary, explanation, warnings, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        contribs_json = json.dumps([c.to_dict() for c in record.criterion_contributions])
        req_json = json.dumps(record.required_summary.to_dict())
        warn_json = json.dumps(record.warnings)

        with self.db.get_connection() as conn:
            conn.execute(
                query,
                (
                    record.id,
                    record.candidate_id,
                    record.session_id,
                    record.evaluation_record_id,
                    record.scoring_config_id,
                    record.scoring_config_version,
                    record.overall_score,
                    record.evidence_coverage,
                    record.completeness_status.value,
                    contribs_json,
                    req_json,
                    record.explanation,
                    warn_json,
                    record.created_at,
                ),
            )
        logger.debug(f"Saved CandidateScoringRecord {record.id} for candidate {record.candidate_id}")

    def save_batch(self, records: List[CandidateScoringRecord]) -> None:
        if not records:
            return
        query = """
        INSERT OR REPLACE INTO candidate_scoring_records (
            id, candidate_id, session_id, evaluation_record_id,
            scoring_config_id, scoring_config_version, overall_score,
            evidence_coverage, completeness_status, criterion_contributions,
            required_summary, explanation, warnings, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        params = [
            (
                r.id,
                r.candidate_id,
                r.session_id,
                r.evaluation_record_id,
                r.scoring_config_id,
                r.scoring_config_version,
                r.overall_score,
                r.evidence_coverage,
                r.completeness_status.value,
                json.dumps([c.to_dict() for c in r.criterion_contributions]),
                json.dumps(r.required_summary.to_dict()),
                r.explanation,
                json.dumps(r.warnings),
                r.created_at,
            )
            for r in records
        ]
        with self.db.get_connection() as conn:
            conn.executemany(query, params)
        logger.info(f"Saved batch of {len(records)} CandidateScoringRecords.")

    def get_latest_by_candidate(self, candidate_id: str) -> Optional[CandidateScoringRecord]:
        query = """
        SELECT * FROM candidate_scoring_records
        WHERE candidate_id = ?
        ORDER BY created_at DESC
        LIMIT 1;
        """
        with self.db.get_connection() as conn:
            cursor = conn.execute(query, (candidate_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_record(row)
        return None

    def get_by_candidate_and_session(
        self, candidate_id: str, session_id: str
    ) -> Optional[CandidateScoringRecord]:
        query = """
        SELECT * FROM candidate_scoring_records
        WHERE candidate_id = ? AND session_id = ?
        ORDER BY created_at DESC
        LIMIT 1;
        """
        with self.db.get_connection() as conn:
            cursor = conn.execute(query, (candidate_id, session_id))
            row = cursor.fetchone()
            if row:
                return self._row_to_record(row)
        return None

    def list_by_session(
        self, session_id: str, scoring_config_id: Optional[str] = None
    ) -> List[CandidateScoringRecord]:
        params: List[Any] = [session_id]
        config_clause = ""
        if scoring_config_id:
            config_clause = "AND scoring_config_id = ?"
            params.append(scoring_config_id)

        query = f"""
        SELECT * FROM candidate_scoring_records
        WHERE session_id = ? {config_clause}
        AND created_at IN (
            SELECT MAX(created_at)
            FROM candidate_scoring_records
            WHERE session_id = ? {config_clause}
            GROUP BY candidate_id
        )
        ORDER BY overall_score DESC NULLS LAST, evidence_coverage DESC;
        """
        double_params = params + params
        with self.db.get_connection() as conn:
            cursor = conn.execute(query, tuple(double_params))
            rows = cursor.fetchall()
            return [self._row_to_record(r) for r in rows]

    def _row_to_record(self, row: sqlite3.Row) -> CandidateScoringRecord:
        raw_contribs = json.loads(row["criterion_contributions"])
        contribs = [CriterionContribution.from_dict(c) for c in raw_contribs]
        raw_req = json.loads(row["required_summary"])
        req_summary = RequiredCriteriaSummary.from_dict(raw_req)
        raw_warn = json.loads(row["warnings"])

        return CandidateScoringRecord(
            id=row["id"],
            candidate_id=row["candidate_id"],
            session_id=row["session_id"],
            evaluation_record_id=row["evaluation_record_id"],
            scoring_config_id=row["scoring_config_id"],
            scoring_config_version=row["scoring_config_version"],
            overall_score=row["overall_score"] if row["overall_score"] is not None else None,
            evidence_coverage=float(row["evidence_coverage"]),
            completeness_status=ScoreCompleteness(row["completeness_status"]),
            criterion_contributions=contribs,
            required_summary=req_summary,
            explanation=row["explanation"],
            warnings=raw_warn,
            created_at=row["created_at"],
        )


class RankingSnapshotRepository:

    def __init__(self, db: Database):
        self.db = db

    def save(self, snapshot: RankingSnapshot) -> None:
        query = """
        INSERT INTO ranking_snapshots (
            id, session_id, scoring_config_id, scoring_config_version,
            ranked_items, created_at
        ) VALUES (?, ?, ?, ?, ?, ?);
        """
        with self.db.get_connection() as conn:
            conn.execute(
                query,
                (
                    snapshot.id,
                    snapshot.session_id,
                    snapshot.scoring_config_id,
                    snapshot.scoring_config_version,
                    json.dumps(snapshot.ranked_items),
                    snapshot.created_at,
                ),
            )
        logger.debug(f"Saved RankingSnapshot {snapshot.id} for session {snapshot.session_id}")

    def get_latest_by_session(self, session_id: str) -> Optional[RankingSnapshot]:
        query = """
        SELECT * FROM ranking_snapshots
        WHERE session_id = ?
        ORDER BY created_at DESC
        LIMIT 1;
        """
        with self.db.get_connection() as conn:
            cursor = conn.execute(query, (session_id,))
            row = cursor.fetchone()
            if row:
                return RankingSnapshot(
                    id=row["id"],
                    session_id=row["session_id"],
                    scoring_config_id=row["scoring_config_id"],
                    scoring_config_version=row["scoring_config_version"],
                    ranked_items=json.loads(row["ranked_items"]),
                    created_at=row["created_at"],
                )
        return None
