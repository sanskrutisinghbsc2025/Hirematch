
from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional

from core.models.candidate import Candidate
from core.models.enums import FileType, ProcessingStatus, ScoreStatus, SessionStatus
from core.models.evaluation import CandidateScore, EvaluationEvidence
from core.models.job import Job
from core.models.session import ScreeningSession
from core.storage.database import Database
from core.utils.logger import logger


class JobRepository:

    def __init__(self, db: Database):
        self.db = db

    def create(self, job: Job) -> Job:
        sql = """
        INSERT INTO jobs (id, title, department, job_category, original_description, parsed_requirements, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """
        self.db.execute_non_query(
            sql,
            (
                job.id,
                job.title,
                job.department,
                job.job_category,
                job.original_description,
                json.dumps(job.parsed_requirements),
                job.created_at,
                job.updated_at,
            ),
        )
        return job

    def get(self, job_id: str) -> Optional[Job]:
        sql = "SELECT * FROM jobs WHERE id = ?;"
        rows = self.db.execute_query(sql, (job_id,))
        if not rows:
            return None
        r = rows[0]
        return Job(
            id=r["id"],
            title=r["title"],
            department=r["department"],
            job_category=r["job_category"],
            original_description=r["original_description"],
            parsed_requirements=json.loads(r["parsed_requirements"]),
            created_at=r["created_at"],
            updated_at=r["updated_at"],
        )

    def list_all(self) -> List[Job]:
        sql = "SELECT * FROM jobs ORDER BY created_at DESC;"
        rows = self.db.execute_query(sql)
        return [
            Job(
                id=r["id"],
                title=r["title"],
                department=r["department"],
                job_category=r["job_category"],
                original_description=r["original_description"],
                parsed_requirements=json.loads(r["parsed_requirements"]),
                created_at=r["created_at"],
                updated_at=r["updated_at"],
            )
            for r in rows
        ]

    def delete(self, job_id: str) -> bool:
        sql = "DELETE FROM jobs WHERE id = ?;"
        count = self.db.execute_non_query(sql, (job_id,))
        return count > 0


class SessionRepository:

    def __init__(self, db: Database):
        self.db = db

    def create(self, session: ScreeningSession) -> ScreeningSession:
        sql = """
        INSERT INTO screening_sessions (id, job_id, session_name, status, candidate_count, max_resume_count, progress_metadata, created_at, completed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        self.db.execute_non_query(
            sql,
            (
                session.id,
                session.job_id,
                session.session_name,
                session.status.value,
                session.candidate_count,
                session.max_resume_count,
                json.dumps(session.progress_metadata),
                session.created_at,
                session.completed_at,
            ),
        )
        return session

    def get(self, session_id: str) -> Optional[ScreeningSession]:
        sql = "SELECT * FROM screening_sessions WHERE id = ?;"
        rows = self.db.execute_query(sql, (session_id,))
        if not rows:
            return None
        r = rows[0]
        return ScreeningSession(
            id=r["id"],
            job_id=r["job_id"],
            session_name=r["session_name"],
            status=SessionStatus(r["status"]),
            candidate_count=r["candidate_count"],
            max_resume_count=r["max_resume_count"],
            progress_metadata=json.loads(r["progress_metadata"]),
            created_at=r["created_at"],
            completed_at=r["completed_at"],
        )

    def list_all(self) -> List[ScreeningSession]:
        sql = "SELECT * FROM screening_sessions ORDER BY created_at DESC;"
        rows = self.db.execute_query(sql)
        return [
            ScreeningSession(
                id=r["id"],
                job_id=r["job_id"],
                session_name=r["session_name"],
                status=SessionStatus(r["status"]),
                candidate_count=r["candidate_count"],
                max_resume_count=r["max_resume_count"],
                progress_metadata=json.loads(r["progress_metadata"]),
                created_at=r["created_at"],
                completed_at=r["completed_at"],
            )
            for r in rows
        ]

    def update_status(
        self,
        session_id: str,
        status: SessionStatus,
        candidate_count: Optional[int] = None,
        completed_at: Optional[str] = None,
    ) -> None:
        if candidate_count is not None and completed_at is not None:
            sql = "UPDATE screening_sessions SET status = ?, candidate_count = ?, completed_at = ? WHERE id = ?;"
            self.db.execute_non_query(sql, (status.value, candidate_count, completed_at, session_id))
        elif candidate_count is not None:
            sql = "UPDATE screening_sessions SET status = ?, candidate_count = ? WHERE id = ?;"
            self.db.execute_non_query(sql, (status.value, candidate_count, session_id))
        elif completed_at is not None:
            sql = "UPDATE screening_sessions SET status = ?, completed_at = ? WHERE id = ?;"
            self.db.execute_non_query(sql, (status.value, completed_at, session_id))
        else:
            sql = "UPDATE screening_sessions SET status = ? WHERE id = ?;"
            self.db.execute_non_query(sql, (status.value, session_id))

    def update_progress(self, session_id: str, progress_metadata: Dict[str, Any]) -> None:
        sql = "UPDATE screening_sessions SET progress_metadata = ? WHERE id = ?;"
        self.db.execute_non_query(sql, (json.dumps(progress_metadata), session_id))

    def delete(self, session_id: str) -> bool:
        with self.db.get_connection() as conn:
            conn.execute("DELETE FROM session_candidates WHERE session_id = ?;", (session_id,))
            conn.execute("DELETE FROM candidate_evaluation_records WHERE session_id = ?;", (session_id,))
            conn.execute("DELETE FROM candidate_scoring_records WHERE session_id = ?;", (session_id,))
            conn.execute("DELETE FROM shortlist_records WHERE session_id = ?;", (session_id,))
            conn.execute("DELETE FROM ranking_snapshots WHERE session_id = ?;", (session_id,))
            conn.execute("DELETE FROM generated_reports WHERE session_id = ?;", (session_id,))
            cursor = conn.execute("DELETE FROM screening_sessions WHERE id = ?;", (session_id,))
            return cursor.rowcount > 0



class CandidateRepository:

    def __init__(self, db: Database):
        self.db = db

    def create(self, candidate: Candidate) -> Candidate:
        existing = self.get_by_hash(candidate.file_hash)
        if existing:
            return existing

        sql = """
        INSERT INTO candidates (id, original_filename, file_hash, file_type, extracted_text, text_ref, processing_status, error_info, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        self.db.execute_non_query(
            sql,
            (
                candidate.id,
                candidate.original_filename,
                candidate.file_hash,
                candidate.file_type.value,
                candidate.extracted_text,
                candidate.text_ref,
                candidate.processing_status.value,
                candidate.error_info,
                candidate.created_at,
            ),
        )
        return candidate

    def get(self, candidate_id: str) -> Optional[Candidate]:
        sql = "SELECT * FROM candidates WHERE id = ?;"
        rows = self.db.execute_query(sql, (candidate_id,))
        if not rows:
            return None
        r = rows[0]
        return Candidate(
            id=r["id"],
            original_filename=r["original_filename"],
            file_hash=r["file_hash"],
            file_type=FileType(r["file_type"]),
            extracted_text=r["extracted_text"],
            text_ref=r["text_ref"],
            processing_status=ProcessingStatus(r["processing_status"]),
            error_info=r["error_info"],
            created_at=r["created_at"],
        )

    def get_by_hash(self, file_hash: str) -> Optional[Candidate]:
        sql = "SELECT * FROM candidates WHERE file_hash = ?;"
        rows = self.db.execute_query(sql, (file_hash,))
        if not rows:
            return None
        r = rows[0]
        return Candidate(
            id=r["id"],
            original_filename=r["original_filename"],
            file_hash=r["file_hash"],
            file_type=FileType(r["file_type"]),
            extracted_text=r["extracted_text"],
            text_ref=r["text_ref"],
            processing_status=ProcessingStatus(r["processing_status"]),
            error_info=r["error_info"],
            created_at=r["created_at"],
        )

    def link_to_session(
        self,
        session_id: str,
        candidate_id: str,
        processing_status: ProcessingStatus,
        manifest_meta: Optional[Dict[str, Any]] = None,
        error_info: Optional[str] = None,
    ) -> None:
        sql = """
        INSERT OR REPLACE INTO session_candidates (session_id, candidate_id, processing_status, manifest_meta, error_info, added_at)
        VALUES (?, ?, ?, ?, ?, ?);
        """
        now = datetime.now(timezone.utc).isoformat()
        self.db.execute_non_query(
            sql,
            (
                session_id,
                candidate_id,
                processing_status.value,
                json.dumps(manifest_meta or {}),
                error_info,
                now,
            ),
        )

    def enroll_in_session(
        self,
        candidate_id: str,
        session_id: str,
        status: ProcessingStatus = ProcessingStatus.PENDING,
        manifest_meta: Optional[Dict[str, Any]] = None,
        error_info: Optional[str] = None,
    ) -> None:
        self.link_to_session(session_id, candidate_id, status, manifest_meta, error_info)

    def list_by_session(self, session_id: str) -> List[Dict[str, Any]]:
        sql = """
        SELECT c.*, sc.processing_status AS session_status, sc.manifest_meta, sc.error_info AS session_error, sc.added_at
        FROM candidates c
        JOIN session_candidates sc ON c.id = sc.candidate_id
        WHERE sc.session_id = ?
        ORDER BY sc.added_at ASC;
        """
        rows = self.db.execute_query(sql, (session_id,))
        result = []
        for r in rows:
            cand = Candidate(
                id=r["id"],
                original_filename=r["original_filename"],
                file_hash=r["file_hash"],
                file_type=FileType(r["file_type"]),
                extracted_text=r["extracted_text"],
                text_ref=r["text_ref"],
                processing_status=ProcessingStatus(r["session_status"]),
                error_info=r["session_error"],
                created_at=r["created_at"],
            )
            result.append({
                "candidate": cand,
                "manifest_meta": json.loads(r["manifest_meta"]),
                "session_status": ProcessingStatus(r["session_status"]),
            })
        return result

    def update_session_candidate_status(
        self,
        session_id: str,
        candidate_id: str,
        status: ProcessingStatus,
        error_info: Optional[str] = None,
    ) -> None:
        sql = """
        UPDATE session_candidates
        SET processing_status = ?, error_info = ?
        WHERE session_id = ? AND candidate_id = ?;
        """
        self.db.execute_non_query(sql, (status.value, error_info, session_id, candidate_id))

    def update_extracted_text(self, candidate_id: str, text: str, text_ref: Optional[str] = None) -> None:
        sql = "UPDATE candidates SET extracted_text = ?, text_ref = ? WHERE id = ?;"
        self.db.execute_non_query(sql, (text, text_ref, candidate_id))

    def update_structured_data(self, candidate_id: str, structured_data: Dict[str, Any]) -> None:
        sql = "UPDATE candidates SET structured_data = ? WHERE id = ?;"
        self.db.execute_non_query(sql, (json.dumps(structured_data), candidate_id))

    def get_structured_data(self, candidate_id: str) -> Dict[str, Any]:
        sql = "SELECT structured_data FROM candidates WHERE id = ?;"
        rows = self.db.execute_query(sql, (candidate_id,))
        if rows and rows[0]["structured_data"]:
            try:
                return json.loads(rows[0]["structured_data"])
            except json.JSONDecodeError:
                return {}
        return {}

    def save_extracted_entities(
        self,
        candidate_id: str,
        skills: List[Any],
        experience: List[Any],
        education: List[Any],
    ) -> None:
        import uuid

        with self.db.get_connection() as conn:
            conn.execute("DELETE FROM extracted_skills WHERE candidate_id = ?;", (candidate_id,))
            if skills:
                conn.executemany(
                    """
                    INSERT INTO extracted_skills (id, candidate_id, skill_name, normalized_skill_name, evidence_text, source_location, extraction_method, confidence)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    [
                        (
                            str(uuid.uuid4()),
                            candidate_id,
                            s.skill_name,
                            s.normalized_skill_name,
                            s.evidence_text,
                            s.source_location,
                            s.extraction_method,
                            s.confidence,
                        )
                        for s in skills
                    ],
                )

            conn.execute("DELETE FROM work_experience WHERE candidate_id = ?;", (candidate_id,))
            if experience:
                conn.executemany(
                    """
                    INSERT INTO work_experience (id, candidate_id, job_title, employer, dates, extracted_description, evidence_text)
                    VALUES (?, ?, ?, ?, ?, ?, ?);
                    """,
                    [
                        (
                            str(uuid.uuid4()),
                            candidate_id,
                            exp.job_title,
                            exp.employer,
                            exp.dates,
                            exp.extracted_description,
                            exp.evidence_text,
                        )
                        for exp in experience
                    ],
                )

            conn.execute("DELETE FROM education_records WHERE candidate_id = ?;", (candidate_id,))
            if education:
                conn.executemany(
                    """
                    INSERT INTO education_records (id, candidate_id, qualification, institution, dates, evidence_text)
                    VALUES (?, ?, ?, ?, ?, ?);
                    """,
                    [
                        (
                            str(uuid.uuid4()),
                            candidate_id,
                            edu.qualification,
                            edu.institution,
                            edu.dates,
                            edu.evidence_text,
                        )
                        for edu in education
                    ],
                )

    def reset_failed_for_retry(self, session_id: str) -> int:
        sql = """
        UPDATE session_candidates
        SET processing_status = 'PENDING', error_info = NULL
        WHERE session_id = ? AND processing_status = 'FAILED';
        """
        return self.db.execute_non_query(sql, (session_id,))

    def get_extracted_skills(self, candidate_id: str) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM extracted_skills WHERE candidate_id = ?;"
        return self.db.execute_query(sql, (candidate_id,))

    def get_work_experience(self, candidate_id: str) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM work_experience WHERE candidate_id = ?;"
        return self.db.execute_query(sql, (candidate_id,))

    def get_education(self, candidate_id: str) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM education_records WHERE candidate_id = ?;"
        return self.db.execute_query(sql, (candidate_id,))


class ScoreRepository:

    def __init__(self, db: Database):
        self.db = db

    def save_score(self, score: CandidateScore) -> CandidateScore:
        sql = """
        INSERT OR REPLACE INTO candidate_scores (candidate_id, overall_score, criterion_scores, score_status, explanation, scoring_config_version, evaluated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?);
        """
        self.db.execute_non_query(
            sql,
            (
                score.candidate_id,
                score.overall_score,
                json.dumps(score.criterion_scores),
                score.score_status.value,
                score.explanation,
                score.scoring_config_version,
                score.evaluated_at,
            ),
        )
        return score

    def save_scores_batch(self, scores: List[CandidateScore]) -> None:
        if not scores:
            return
        sql = """
        INSERT OR REPLACE INTO candidate_scores (candidate_id, overall_score, criterion_scores, score_status, explanation, scoring_config_version, evaluated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?);
        """
        params_list = [
            (
                s.candidate_id,
                s.overall_score,
                json.dumps(s.criterion_scores),
                s.score_status.value,
                s.explanation,
                s.scoring_config_version,
                s.evaluated_at,
            )
            for s in scores
        ]
        self.db.execute_batch(sql, params_list)

    def get(self, candidate_id: str) -> Optional[CandidateScore]:
        return self.get_score(candidate_id)

    def get_by_candidate(self, candidate_id: str) -> Optional[CandidateScore]:
        return self.get_score(candidate_id)

    def get_score(self, candidate_id: str) -> Optional[CandidateScore]:
        sql = "SELECT * FROM candidate_scores WHERE candidate_id = ?;"
        rows = self.db.execute_query(sql, (candidate_id,))
        if not rows:
            return None
        r = rows[0]
        return CandidateScore(
            candidate_id=r["candidate_id"],
            overall_score=r["overall_score"],
            criterion_scores=json.loads(r["criterion_scores"]),
            score_status=ScoreStatus(r["score_status"]),
            explanation=r["explanation"],
            scoring_config_version=r["scoring_config_version"],
            evaluated_at=r["evaluated_at"],
        )

    def list_by_session(self, session_id: str) -> Dict[str, CandidateScore]:
        sql = """
        SELECT cs.*
        FROM candidate_scores cs
        JOIN session_candidates sc ON cs.candidate_id = sc.candidate_id
        WHERE sc.session_id = ?;
        """
        rows = self.db.execute_query(sql, (session_id,))
        scores = {}
        for r in rows:
            scores[r["candidate_id"]] = CandidateScore(
                candidate_id=r["candidate_id"],
                overall_score=r["overall_score"],
                criterion_scores=json.loads(r["criterion_scores"]),
                score_status=ScoreStatus(r["score_status"]),
                explanation=r["explanation"],
                scoring_config_version=r["scoring_config_version"],
                evaluated_at=r["evaluated_at"],
            )
        return scores


class CriterionRepository:

    def __init__(self, db: Database):
        self.db = db

    def save_batch(self, criteria: List[Any], job_id: str) -> None:
        with self.db.get_connection() as conn:
            conn.execute("DELETE FROM evaluation_criteria WHERE job_id = ?;", (job_id,))
            sql = """
            INSERT INTO evaluation_criteria (id, job_id, criterion_name, description, weight, criterion_type, matching_config, is_enabled)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """
            for c in criteria:
                conn.execute(
                    sql,
                    (
                        c.id,
                        job_id,
                        c.criterion_name,
                        c.description,
                        c.weight,
                        c.criterion_type.value if hasattr(c.criterion_type, "value") else str(c.criterion_type),
                        json.dumps(c.matching_config) if hasattr(c, "matching_config") else "{}",
                        1 if getattr(c, "is_enabled", True) else 0,
                    ),
                )
        return self.list_by_job(job_id)

    def list_by_job(self, job_id: str) -> List[Any]:
        from core.models.enums import CriterionType
        from core.models.evaluation import EvaluationCriterion

        sql = "SELECT * FROM evaluation_criteria WHERE job_id = ? ORDER BY weight DESC;"
        rows = self.db.execute_query(sql, (job_id,))
        results = []
        for r in rows:
            results.append(
                EvaluationCriterion(
                    id=r["id"],
                    criterion_name=r["criterion_name"],
                    description=r["description"] or "",
                    weight=float(r["weight"]),
                    criterion_type=CriterionType(r["criterion_type"]),
                    matching_config=json.loads(r["matching_config"] or "{}"),
                    is_enabled=bool(r["is_enabled"]),
                )
            )
        return results

    def update(self, criterion: Any) -> None:
        sql = "UPDATE evaluation_criteria SET weight = ?, is_enabled = ? WHERE id = ?;"
        self.db.execute_non_query(
            sql,
            (
                float(criterion.weight),
                1 if getattr(criterion, "is_enabled", True) else 0,
                criterion.id,
            ),
        )


class EvidenceRepository:

    def __init__(self, db: Database):
        self.db = db

    def save_batch(self, evidence_list: List[EvaluationEvidence]) -> None:
        with self.db.get_connection() as conn:
            for ev in evidence_list:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO evaluation_evidence (id, candidate_id, criterion_id, supporting_text, match_type, evidence_source, evaluation_status, explanation)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        ev.id,
                        ev.candidate_id,
                        ev.criterion_id,
                        ev.supporting_text,
                        ev.match_type.value if hasattr(ev.match_type, "value") else str(ev.match_type),
                        ev.evidence_source,
                        ev.evaluation_status,
                        ev.explanation,
                    ),
                )

    def list_by_candidate(self, candidate_id: str) -> List[EvaluationEvidence]:
        from core.models.enums import MatchType

        sql = "SELECT * FROM evaluation_evidence WHERE candidate_id = ?;"
        rows = self.db.execute_query(sql, (candidate_id,))
        results = []
        for r in rows:
            results.append(
                EvaluationEvidence(
                    id=r["id"],
                    candidate_id=r["candidate_id"],
                    criterion_id=r["criterion_id"],
                    supporting_text=r["supporting_text"],
                    match_type=MatchType(r["match_type"]),
                    evidence_source=r["evidence_source"],
                    evaluation_status=r["evaluation_status"],
                    explanation=r["explanation"] or "",
                )
            )
        return results

    def list_by_candidate_and_criterion(self, candidate_id: str, criterion_id: str) -> List[EvaluationEvidence]:
        from core.models.enums import MatchType

        sql = "SELECT * FROM evaluation_evidence WHERE candidate_id = ? AND criterion_id = ?;"
        rows = self.db.execute_query(sql, (candidate_id, criterion_id))
        results = []
        for r in rows:
            results.append(
                EvaluationEvidence(
                    id=r["id"],
                    candidate_id=r["candidate_id"],
                    criterion_id=r["criterion_id"],
                    supporting_text=r["supporting_text"],
                    match_type=MatchType(r["match_type"]),
                    evidence_source=r["evidence_source"],
                    evaluation_status=r["evaluation_status"],
                    explanation=r["explanation"] or "",
                )
            )
        return results

