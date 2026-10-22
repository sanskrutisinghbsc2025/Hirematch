
from pathlib import Path
import tempfile
import unittest

from config import AppConfig
from core.models.enums import ProcessingStatus, SessionStatus
from core.models.job import Job
from core.services.session_orchestrator import ScreeningOrchestrator
from core.storage.database import Database
from core.storage.repositories import (
    CandidateRepository,
    JobRepository,
    SessionRepository,
)
from core.utils.errors import SessionLimitExceededError


class TestOrchestrator(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        base = Path(self.temp_dir.name)

        self.config = AppConfig(
            base_dir=base,
            db_path=base / "test_hirematch.db",
            storage_dir=base / "storage",
            cache_dir=base / "cache",
            temp_dir=base / "temp",
            max_resumes_per_session=100,
            processing_batch_size=5,
        )
        self.config.ensure_directories()

        self.db = Database(self.config.db_path)
        self.db.initialize_schema()

        self.orchestrator = ScreeningOrchestrator(self.db, self.config)
        self.job_repo = JobRepository(self.db)
        self.session_repo = SessionRepository(self.db)
        self.candidate_repo = CandidateRepository(self.db)

        self.job = self.job_repo.create(
            Job(title="Cloud Solutions Architect", original_description="AWS, Kubernetes, Terraform")
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_create_session(self):
        session = self.orchestrator.create_session(
            job_id=self.job.id,
            session_name="Q4 Cloud Hiring",
            max_resume_count=100,
        )
        self.assertIsNotNone(session.id)
        self.assertEqual(session.session_name, "Q4 Cloud Hiring")
        self.assertEqual(session.max_resume_count, 100)
        self.assertEqual(session.status, SessionStatus.CREATED)

    def test_enforce_100_resume_session_limit(self):
        session = self.orchestrator.create_session(job_id=self.job.id, session_name="Limit Test Session")

        oversized_batch = [
            {
                "filename": f"candidate_{i}.pdf",
                "content": b"%PDF-1.4 Resume text " + str(i).encode(),
                "size": 100,
            }
            for i in range(101)
        ]

        with self.assertRaises(SessionLimitExceededError):
            self.orchestrator.add_resumes_to_session(session.id, oversized_batch)

    def test_incremental_batch_exceeding_100_limit(self):
        session = self.orchestrator.create_session(job_id=self.job.id, session_name="Incremental Limit Test")

        batch_1 = [
            {
                "filename": f"cand_{i}.pdf",
                "content": b"%PDF-1.4 Resume text " + str(i).encode(),
                "size": 100,
            }
            for i in range(90)
        ]
        report_1 = self.orchestrator.add_resumes_to_session(session.id, batch_1)
        self.assertEqual(report_1["enrolled"], 90)

        batch_2 = [
            {
                "filename": f"cand_extra_{i}.pdf",
                "content": b"%PDF-1.4 Extra text " + str(i).encode(),
                "size": 100,
            }
            for i in range(15)
        ]
        with self.assertRaises(SessionLimitExceededError):
            self.orchestrator.add_resumes_to_session(session.id, batch_2)

    def test_duplicate_resume_detection(self):
        session = self.orchestrator.create_session(job_id=self.job.id, session_name="Duplicate Test")

        resume_content = b"%PDF-1.4 Unique Resume of Alice Johnson with distinct qualifications."

        batch = [
            {"filename": "alice_resume.pdf", "content": resume_content, "size": len(resume_content)},
            {"filename": "alice_copy.pdf", "content": resume_content, "size": len(resume_content)},
        ]

        report = self.orchestrator.add_resumes_to_session(session.id, batch)
        self.assertEqual(report["enrolled"], 1)
        self.assertEqual(report["duplicate"], 1)
        self.assertEqual(report["failed"], 0)

    def test_failure_isolation(self):
        session = self.orchestrator.create_session(job_id=self.job.id, session_name="Failure Isolation Test")

        batch = [
            {"filename": "valid_1.pdf", "content": b"%PDF-1.4 Valid candidate 1 content", "size": 35},
            {"filename": "invalid_format.txt", "content": b"Unsupported text format", "size": 23},
            {"filename": "valid_2.pdf", "content": b"%PDF-1.4 Valid candidate 2 content", "size": 35},
        ]

        report = self.orchestrator.add_resumes_to_session(session.id, batch)
        self.assertEqual(report["enrolled"], 2)
        self.assertEqual(report["failed"], 1)

        candidates = self.candidate_repo.list_by_session(session.id)
        self.assertEqual(len(candidates), 3)

        statuses = [c["session_status"] for c in candidates]
        self.assertEqual(statuses.count(ProcessingStatus.PENDING), 2)
        self.assertEqual(statuses.count(ProcessingStatus.FAILED), 1)

    def test_batch_processing_and_progress_updates(self):
        session = self.orchestrator.create_session(job_id=self.job.id, session_name="Batch Process Test")

        batch = [
            {"filename": f"engineer_{i}.pdf", "content": b"%PDF-1.4 Text for candidate " + str(i).encode(), "size": 35}
            for i in range(3)
        ]
        self.orchestrator.add_resumes_to_session(session.id, batch)

        res = self.orchestrator.process_session_batch(session.id, batch_size=2)
        self.assertEqual(res["processed_in_chunk"], 2)
        self.assertEqual(res["progress"]["pending"], 1)

        res2 = self.orchestrator.process_session_batch(session.id, batch_size=2)
        self.assertEqual(res2["processed_in_chunk"], 1)
        self.assertEqual(res2["progress"]["pending"], 0)

        updated_session = self.session_repo.get(session.id)
        self.assertEqual(updated_session.status, SessionStatus.COMPLETED)
        self.assertIsNotNone(updated_session.completed_at)


if __name__ == "__main__":
    unittest.main()
