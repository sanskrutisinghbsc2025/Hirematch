
import io
from pathlib import Path
import tempfile
import time
import unittest

from config import AppConfig
from core.models.enums import FileType, ProcessingStatus, SessionStatus
from core.models.job import Job
from core.services.session_orchestrator import ScreeningOrchestrator
from core.storage.database import Database
from core.utils.errors import (
    FileValidationError,
    SessionLimitExceededError,
    UnsupportedFileTypeError,
)


class TestBatchProcessingRobustness(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_batch_robustness.db"
        self.db = Database(str(self.db_path))
        self.db.initialize_schema()

        self.config = AppConfig()
        self.config.storage_dir = Path(self.temp_dir.name) / "storage"
        self.config.reports_dir = Path(self.temp_dir.name) / "reports"
        self.config.ensure_directories()

        self.orchestrator = ScreeningOrchestrator(self.db, self.config)

        self.job = Job(
            title="Senior Backend Engineer",
            department="Platform Engineering",
            original_description="Looking for Python, PostgreSQL, Docker, AWS, and distributed systems experience.",
        )
        self.db_job = self.orchestrator.job_repo.create(self.job)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_synthetic_pdf(self, content_text: str) -> bytes:
        import fitz
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((50, 72), content_text)
        pdf_bytes = doc.tobytes()
        doc.close()
        return pdf_bytes

    def test_single_resume_ingestion_and_processing(self):
        session = self.orchestrator.create_session(self.db_job.id, "Single Resume Session")

        pdf_bytes = self._create_synthetic_pdf("Alice Developer\nPython, Docker, PostgreSQL\n5 years experience.")
        files = [{"filename": "alice_dev.pdf", "content": pdf_bytes, "size": len(pdf_bytes)}]

        report = self.orchestrator.add_resumes_to_session(session.id, files)
        self.assertEqual(report["enrolled"], 1)
        self.assertEqual(report["failed"], 0)
        self.assertEqual(report["duplicate"], 0)
        self.assertEqual(report["total_in_session"], 1)

        res = self.orchestrator.process_session_batch(session.id, batch_size=10)
        self.assertEqual(res["processed_in_chunk"], 1)
        self.assertEqual(res["failed_in_chunk"], 0)

    def test_small_batch_ingestion_and_processing(self):
        session = self.orchestrator.create_session(self.db_job.id, "Small Batch Session")

        files = []
        for i in range(5):
            content = f"Candidate {i}\nSkills: Python, AWS, Docker, Kubernetes\nExperience: {i+2} years."
            b = self._create_synthetic_pdf(content)
            files.append({"filename": f"candidate_{i}.pdf", "content": b, "size": len(b)})

        report = self.orchestrator.add_resumes_to_session(session.id, files)
        self.assertEqual(report["enrolled"], 5)
        self.assertEqual(report["total_in_session"], 5)

        proc_res = self.orchestrator.process_session_batch(session.id, batch_size=10)
        self.assertEqual(proc_res["processed_in_chunk"], 5)
        self.assertEqual(proc_res["failed_in_chunk"], 0)

    def test_full_100_resume_batch_performance(self):
        session = self.orchestrator.create_session(self.db_job.id, "100-Resume Batch Session")

        files = []
        for i in range(100):
            body = (
                f"Candidate {i:03d} Dossier\n"
                f"Summary: Backend Software Architect with focus on Python, FastAPI, and Postgres.\n"
                f"Experience: Senior Engineer at TechCorp ({2020 + (i % 4)} - 2024).\n"
                f"Built high-throughput distributed systems using Docker, Kubernetes, and AWS.\n"
                f"Education: Bachelor of Science in Computer Science, University of Technology.\n"
            )
            b = self._create_synthetic_pdf(body)
            files.append({"filename": f"candidate_{i:03d}.pdf", "content": b, "size": len(b)})

        t_start = time.perf_counter()
        report = self.orchestrator.add_resumes_to_session(session.id, files)
        t_ingest = time.perf_counter() - t_start

        self.assertEqual(report["enrolled"], 100)
        self.assertEqual(report["total_in_session"], 100)
        self.assertLess(t_ingest, 10.0, f"100-resume file ingestion took {t_ingest:.2f}s (must be < 10.0s)")

        cands = self.orchestrator.candidate_repo.list_by_session(session.id)
        self.assertEqual(len(cands), 100)

        t_proc_start = time.perf_counter()
        proc_res = self.orchestrator.process_session_batch(session.id, batch_size=100)
        t_proc = time.perf_counter() - t_proc_start

        self.assertEqual(proc_res["processed_in_chunk"], 100)
        self.assertEqual(proc_res["progress"]["processed"], 100)
        self.assertLess(t_proc, 15.0, f"100-resume text extraction took {t_proc:.2f}s (must be < 15.0s)")

    def test_strict_service_layer_100_resume_limit_enforcement(self):
        session = self.orchestrator.create_session(self.db_job.id, "Limit Test Session")

        files_101 = []
        for i in range(101):
            b = self._create_synthetic_pdf(f"Candidate {i}")
            files_101.append({"filename": f"cand_{i}.pdf", "content": b, "size": len(b)})

        with self.assertRaises(SessionLimitExceededError):
            self.orchestrator.add_resumes_to_session(session.id, files_101)

        files_90 = []
        for i in range(90):
            b = self._create_synthetic_pdf(f"Candidate {i}")
            files_90.append({"filename": f"cand_{i}.pdf", "content": b, "size": len(b)})
        rep = self.orchestrator.add_resumes_to_session(session.id, files_90)
        self.assertEqual(rep["enrolled"], 90)

        files_15 = []
        for i in range(90, 105):
            b = self._create_synthetic_pdf(f"Candidate {i}")
            files_15.append({"filename": f"cand_{i}.pdf", "content": b, "size": len(b)})

        with self.assertRaises(SessionLimitExceededError):
            self.orchestrator.add_resumes_to_session(session.id, files_15)

        files_10 = []
        for i in range(90, 100):
            b = self._create_synthetic_pdf(f"Candidate {i}")
            files_10.append({"filename": f"cand_{i}.pdf", "content": b, "size": len(b)})
        rep_final = self.orchestrator.add_resumes_to_session(session.id, files_10)
        self.assertEqual(rep_final["enrolled"], 10)
        self.assertEqual(rep_final["total_in_session"], 100)

    def test_duplicate_file_detection_without_double_counting(self):
        session = self.orchestrator.create_session(self.db_job.id, "Duplicate Test Session")

        pdf_1 = self._create_synthetic_pdf("Original Candidate Alice\nSkills: Python, Go")
        pdf_2 = self._create_synthetic_pdf("Different Candidate Bob\nSkills: Java, Spring")

        files_batch_1 = [
            {"filename": "alice.pdf", "content": pdf_1, "size": len(pdf_1)},
            {"filename": "bob.pdf", "content": pdf_2, "size": len(pdf_2)},
        ]
        rep1 = self.orchestrator.add_resumes_to_session(session.id, files_batch_1)
        self.assertEqual(rep1["enrolled"], 2)
        self.assertEqual(rep1["duplicate"], 0)

        charlie_bytes = self._create_synthetic_pdf("Charlie Candidate")
        files_batch_2 = [
            {"filename": "alice_renamed.pdf", "content": pdf_1, "size": len(pdf_1)},
            {"filename": "charlie.pdf", "content": charlie_bytes, "size": len(charlie_bytes)},
        ]
        rep2 = self.orchestrator.add_resumes_to_session(session.id, files_batch_2)
        self.assertEqual(rep2["enrolled"], 1)
        self.assertEqual(rep2["duplicate"], 1)
        self.assertEqual(rep2["total_in_session"], 4)

    def test_unsupported_formats_and_empty_files_isolation(self):
        session = self.orchestrator.create_session(self.db_job.id, "Format Isolation Session")

        valid_pdf = self._create_synthetic_pdf("Valid Engineer\nPython developer")
        empty_bytes = b""
        invalid_txt = b"Text content not allowed as .txt"
        corrupted_pdf = b"NOT_A_PDF_HEADER_JUST_GARBAGE"

        files = [
            {"filename": "valid.pdf", "content": valid_pdf, "size": len(valid_pdf)},
            {"filename": "empty.pdf", "content": empty_bytes, "size": 0},
            {"filename": "script.sh", "content": invalid_txt, "size": len(invalid_txt)},
            {"filename": "corrupt.pdf", "content": corrupted_pdf, "size": len(corrupted_pdf)},
        ]

        report = self.orchestrator.add_resumes_to_session(session.id, files)
        self.assertEqual(report["enrolled"], 1)
        self.assertEqual(report["failed"], 3)
        self.assertEqual(report["total_in_session"], 4)

        proc_res = self.orchestrator.process_session_batch(session.id)
        self.assertEqual(proc_res["processed_in_chunk"], 1)

    def test_very_long_document_processing_resilience(self):
        session = self.orchestrator.create_session(self.db_job.id, "Long Doc Session")

        long_text = "Experienced Architect\n" + ("Extensive distributed systems experience with Python and AWS. " * 800)
        long_pdf = self._create_synthetic_pdf(long_text)

        files = [{"filename": "long_curriculum_vitae.pdf", "content": long_pdf, "size": len(long_pdf)}]
        report = self.orchestrator.add_resumes_to_session(session.id, files)
        self.assertEqual(report["enrolled"], 1)

        proc_res = self.orchestrator.process_session_batch(session.id)
        self.assertEqual(proc_res["processed_in_chunk"], 1)
        self.assertEqual(proc_res["failed_in_chunk"], 0)

    def test_idempotent_batch_processing_and_retry_behavior(self):
        session = self.orchestrator.create_session(self.db_job.id, "Idempotent Session")

        valid_pdf = self._create_synthetic_pdf("Valid Candidate\nPython and Docker")
        files = [{"filename": "valid.pdf", "content": valid_pdf, "size": len(valid_pdf)}]
        self.orchestrator.add_resumes_to_session(session.id, files)

        res1 = self.orchestrator.process_session_batch(session.id)
        self.assertEqual(res1["processed_in_chunk"], 1)

        res2 = self.orchestrator.process_session_batch(session.id)
        self.assertEqual(res2["processed_in_chunk"], 0)


if __name__ == "__main__":
    unittest.main()
