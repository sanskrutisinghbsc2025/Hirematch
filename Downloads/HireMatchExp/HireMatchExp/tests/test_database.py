
from pathlib import Path
import tempfile
import unittest

from core.models.candidate import Candidate
from core.models.enums import FileType, ProcessingStatus, SessionStatus
from core.models.evaluation import CandidateScore
from core.models.job import Job
from core.models.session import ScreeningSession
from core.storage.database import Database
from core.storage.repositories import (
    CandidateRepository,
    JobRepository,
    ScoreRepository,
    SessionRepository,
)


class TestDatabaseAndRepositories(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_hirematch.db"
        self.db = Database(self.db_path)
        self.db.initialize_schema()

        self.job_repo = JobRepository(self.db)
        self.session_repo = SessionRepository(self.db)
        self.candidate_repo = CandidateRepository(self.db)
        self.score_repo = ScoreRepository(self.db)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_job_repository_crud(self):
        job = Job(
            title="Senior Data Scientist",
            department="Analytics",
            original_description="Experience in NLP and Machine Learning.",
            parsed_requirements={"skills": ["Python", "PyTorch"]},
        )
        saved = self.job_repo.create(job)
        self.assertEqual(saved.id, job.id)

        fetched = self.job_repo.get(job.id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.title, "Senior Data Scientist")
        self.assertEqual(fetched.parsed_requirements["skills"], ["Python", "PyTorch"])

        all_jobs = self.job_repo.list_all()
        self.assertEqual(len(all_jobs), 1)

        deleted = self.job_repo.delete(job.id)
        self.assertTrue(deleted)
        self.assertIsNone(self.job_repo.get(job.id))

    def test_session_repository_crud(self):
        job = self.job_repo.create(Job(title="DevOps Lead", original_description="Kubernetes & Terraform"))
        session = ScreeningSession(job_id=job.id, session_name="DevOps Batch 2026", max_resume_count=100)
        self.session_repo.create(session)

        fetched = self.session_repo.get(session.id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.session_name, "DevOps Batch 2026")
        self.assertEqual(fetched.status, SessionStatus.CREATED)

        self.session_repo.update_status(session.id, SessionStatus.PROCESSING, candidate_count=15)
        updated = self.session_repo.get(session.id)
        self.assertEqual(updated.status, SessionStatus.PROCESSING)
        self.assertEqual(updated.candidate_count, 15)

    def test_candidate_repository_and_duplicate_detection(self):
        job = self.job_repo.create(Job(title="Frontend Dev", original_description="React & TS"))
        session = self.session_repo.create(ScreeningSession(job_id=job.id, session_name="Frontend Batch"))

        cand_hash = "f" * 64
        cand = Candidate(original_filename="john_doe.pdf", file_hash=cand_hash, file_type=FileType.PDF)
        created = self.candidate_repo.create(cand)

        found = self.candidate_repo.get_by_hash(cand_hash)
        self.assertIsNotNone(found)
        self.assertEqual(found.id, created.id)

        cand_dup = Candidate(original_filename="john_doe_copy.pdf", file_hash=cand_hash, file_type=FileType.PDF)
        dup_result = self.candidate_repo.create(cand_dup)
        self.assertEqual(dup_result.id, created.id)

        self.candidate_repo.link_to_session(session.id, created.id, ProcessingStatus.PENDING)
        session_cands = self.candidate_repo.list_by_session(session.id)
        self.assertEqual(len(session_cands), 1)
        self.assertEqual(session_cands[0]["candidate"].id, created.id)

    def test_score_repository(self):
        job = self.job_repo.create(Job(title="Product Manager", original_description="Strategy"))
        cand = self.candidate_repo.create(
            Candidate(original_filename="pm.pdf", file_hash="1" * 64, file_type=FileType.PDF)
        )

        score = CandidateScore(
            candidate_id=cand.id,
            overall_score=88.0,
            criterion_scores={"strategy": 90.0, "leadership": 86.0},
            explanation="Strong product roadmap track record.",
        )
        self.score_repo.save_score(score)

        fetched = self.score_repo.get_score(cand.id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.overall_score, 88.0)
        self.assertEqual(fetched.criterion_scores["strategy"], 90.0)


if __name__ == "__main__":
    unittest.main()
