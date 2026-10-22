
import json
from typing import Any, Dict, List, Optional

from core.models.eval_config import EvaluationConfiguration
from core.models.evaluation import CandidateEvaluationRecord
from core.storage.database import Database
from core.utils.logger import logger


class EvaluationConfigurationRepository:

    def __init__(self, db: Database):
        self.db = db

    def save_config(self, config: EvaluationConfiguration) -> EvaluationConfiguration:
        sql = """
        INSERT OR REPLACE INTO evaluation_configurations (id, job_id, version, name, config_data, created_at)
        VALUES (?, ?, ?, ?, ?, ?);
        """
        payload = json.dumps(config.to_dict())
        self.db.execute_non_query(
            sql,
            (config.id, config.job_id, config.version, config.name, payload, config.created_at),
        )
        return config

    def get_config(self, config_id: str) -> Optional[EvaluationConfiguration]:
        sql = "SELECT config_data FROM evaluation_configurations WHERE id = ?;"
        rows = self.db.execute_query(sql, (config_id,))
        if not rows:
            return None
        data = json.loads(rows[0]["config_data"])
        return EvaluationConfiguration.from_dict(data)

    def get_latest_for_job(self, job_id: str) -> Optional[EvaluationConfiguration]:
        sql = """
        SELECT config_data FROM evaluation_configurations
        WHERE job_id = ?
        ORDER BY created_at DESC, version DESC
        LIMIT 1;
        """
        rows = self.db.execute_query(sql, (job_id,))
        if not rows:
            return None
        data = json.loads(rows[0]["config_data"])
        return EvaluationConfiguration.from_dict(data)

    def get_latest_by_job(self, job_id: str) -> Optional[EvaluationConfiguration]:
        return self.get_latest_for_job(job_id)

    def save(self, config: EvaluationConfiguration) -> EvaluationConfiguration:
        return self.save_config(config)


    def list_versions_for_job(self, job_id: str) -> List[EvaluationConfiguration]:
        sql = """
        SELECT config_data FROM evaluation_configurations
        WHERE job_id = ?
        ORDER BY created_at DESC, version DESC;
        """
        rows = self.db.execute_query(sql, (job_id,))
        return [EvaluationConfiguration.from_dict(json.loads(r["config_data"])) for r in rows]


class EvaluationRecordRepository:

    def __init__(self, db: Database):
        self.db = db

    def save_record(self, record: CandidateEvaluationRecord) -> CandidateEvaluationRecord:
        sql = """
        INSERT OR REPLACE INTO candidate_evaluation_records (
            id, candidate_id, session_id, config_id, config_version,
            overall_score, evidence_coverage, evaluation_status,
            detailed_results, baseline_summary, semantic_summary, structured_summary,
            warnings, evaluated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        self.db.execute_non_query(
            sql,
            (
                record.id,
                record.candidate_id,
                record.session_id,
                record.config_id,
                record.config_version,
                record.overall_score,
                record.evidence_coverage,
                record.evaluation_status,
                json.dumps([r.to_dict() for r in record.criterion_results]),
                json.dumps(record.baseline_summary),
                json.dumps(record.semantic_summary),
                json.dumps(record.structured_summary),
                json.dumps(record.warnings),
                record.evaluated_at,
            ),
        )
        return record

    def save_batch(self, records: List[CandidateEvaluationRecord]) -> None:
        if not records:
            return
        sql = """
        INSERT OR REPLACE INTO candidate_evaluation_records (
            id, candidate_id, session_id, config_id, config_version,
            overall_score, evidence_coverage, evaluation_status,
            detailed_results, baseline_summary, semantic_summary, structured_summary,
            warnings, evaluated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        params_list = [
            (
                r.id,
                r.candidate_id,
                r.session_id,
                r.config_id,
                r.config_version,
                r.overall_score,
                r.evidence_coverage,
                r.evaluation_status,
                json.dumps([res.to_dict() for res in r.criterion_results]),
                json.dumps(r.baseline_summary),
                json.dumps(r.semantic_summary),
                json.dumps(r.structured_summary),
                json.dumps(r.warnings),
                r.evaluated_at,
            )
            for r in records
        ]
        self.db.execute_batch(sql, params_list)

    def get_record(self, record_id: str) -> Optional[CandidateEvaluationRecord]:
        sql = "SELECT * FROM candidate_evaluation_records WHERE id = ?;"
        rows = self.db.execute_query(sql, (record_id,))
        if not rows:
            return None
        return self._row_to_record(rows[0])

    def get_latest_record(self, candidate_id: str, session_id: Optional[str] = None) -> Optional[CandidateEvaluationRecord]:
        if session_id:
            sql = """
            SELECT * FROM candidate_evaluation_records
            WHERE candidate_id = ? AND session_id = ?
            ORDER BY evaluated_at DESC
            LIMIT 1;
            """
            rows = self.db.execute_query(sql, (candidate_id, session_id))
        else:
            sql = """
            SELECT * FROM candidate_evaluation_records
            WHERE candidate_id = ?
            ORDER BY evaluated_at DESC
            LIMIT 1;
            """
            rows = self.db.execute_query(sql, (candidate_id,))
        if not rows:
            return None
        return self._row_to_record(rows[0])

    def get_by_candidate_and_session(
        self, candidate_id: str, session_id: Optional[str] = None
    ) -> Optional[CandidateEvaluationRecord]:
        return self.get_latest_record(candidate_id, session_id)

    def list_records_for_session(self, session_id: str) -> Dict[str, CandidateEvaluationRecord]:
        sql = """
        SELECT r.*
        FROM candidate_evaluation_records r
        INNER JOIN (
            SELECT candidate_id, MAX(evaluated_at) as max_eval
            FROM candidate_evaluation_records
            WHERE session_id = ?
            GROUP BY candidate_id
        ) latest ON r.candidate_id = latest.candidate_id AND r.evaluated_at = latest.max_eval
        WHERE r.session_id = ?;
        """
        rows = self.db.execute_query(sql, (session_id, session_id))
        records: Dict[str, CandidateEvaluationRecord] = {}
        for row in rows:
            rec = self._row_to_record(row)
            records[rec.candidate_id] = rec
        return records

    def list_by_session(self, session_id: str) -> List[CandidateEvaluationRecord]:
        return list(self.list_records_for_session(session_id).values())


    def list_record_history(
        self, candidate_id: str, session_id: Optional[str] = None
    ) -> List[CandidateEvaluationRecord]:
        if session_id:
            sql = """
            SELECT * FROM candidate_evaluation_records
            WHERE candidate_id = ? AND session_id = ?
            ORDER BY evaluated_at DESC;
            """
            rows = self.db.execute_query(sql, (candidate_id, session_id))
        else:
            sql = """
            SELECT * FROM candidate_evaluation_records
            WHERE candidate_id = ?
            ORDER BY evaluated_at DESC;
            """
            rows = self.db.execute_query(sql, (candidate_id,))
        return [self._row_to_record(row) for row in rows]

    @staticmethod
    def _row_to_record(row: Any) -> CandidateEvaluationRecord:
        raw_detailed = json.loads(row["detailed_results"])

        unmet_mandatory: List[str] = []
        conflicting_criteria: List[str] = []
        for r in raw_detailed:
            c_name = r.get("criterion_name", "")
            c_type = str(r.get("criterion_type", "")).upper()
            status = str(r.get("match_status", "")).upper()
            score = float(r.get("score", 0.0))
            is_req = "REQUIRED" in c_type or r.get("is_required", False)
            disagree = str(r.get("disagreement_type", "")).upper()

            if status in ("CONFLICTING_EVIDENCE", "CONTRADICTED") or "NEGATED" in disagree:
                if c_name and c_name not in conflicting_criteria:
                    conflicting_criteria.append(c_name)

            if is_req and (score < 50.0 or status in ("NOT_FOUND", "INSUFFICIENT_EVIDENCE", "NOT_SUPPORTED", "CONTRADICTED")):
                if c_name and c_name not in unmet_mandatory:
                    unmet_mandatory.append(c_name)

        return CandidateEvaluationRecord.from_dict(
            {
                "id": row["id"],
                "candidate_id": row["candidate_id"],
                "session_id": row["session_id"],
                "config_id": row["config_id"],
                "config_version": row["config_version"],
                "overall_score": row["overall_score"],
                "evidence_coverage": row["evidence_coverage"],
                "evaluation_status": row["evaluation_status"],
                "criterion_results": raw_detailed,
                "baseline_summary": json.loads(row["baseline_summary"]),
                "semantic_summary": json.loads(row["semantic_summary"]),
                "structured_summary": json.loads(row["structured_summary"]),
                "unmet_mandatory_criteria": unmet_mandatory,
                "conflicting_criteria": conflicting_criteria,
                "warnings": json.loads(row["warnings"]),
                "evaluated_at": row["evaluated_at"],
            }
        )
