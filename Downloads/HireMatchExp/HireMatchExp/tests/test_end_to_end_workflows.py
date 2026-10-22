
from pathlib import Path
import tempfile
import unittest

from config import AppConfig
from core.models.enums import EvaluationMode, ProcessingStatus, SessionStatus, ShortlistReviewStatus
from core.models.job import Job
from core.models.report_models import ExportFormat
from core.models.scoring_models import ScoringConfiguration, ScoringCriterion
from core.services.session_orchestrator import ScreeningOrchestrator
from core.storage.database import Database


class TestEndToEndRecruiterWorkflows(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_e2e_workflow.db"
        self.db = Database(str(self.db_path))
        self.db.initialize_schema()

        self.config = AppConfig()
        self.config.storage_dir = Path(self.temp_dir.name) / "storage"
        self.config.reports_dir = Path(self.temp_dir.name) / "reports"
        self.config.ensure_directories()

        self.orchestrator = ScreeningOrchestrator(self.db, self.config)

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

    def test_complete_recruiter_screening_lifecycle_e2e(self):
        job = Job(
            title="Senior Distributed Systems Architect",
            department="Infrastructure",
            original_description=(
                "Mandatory Requirements:\n"
                "- Strong proficiency in Python, Go, and distributed architecture.\n"
                "- Minimum 5 years of professional backend experience.\n"
                "- Deep hands-on experience with Docker, Kubernetes, and PostgreSQL.\n\n"
                "Preferred Qualifications:\n"
                "- Master of Science in Computer Science or related degree.\n"
                "- Familiarity with AWS cloud and Terraform infrastructure."
            ),
        )
        db_job = self.orchestrator.job_repo.create(job)
        self.assertIsNotNone(db_job.id)

        session = self.orchestrator.create_session(db_job.id, "Infrastructure Screening Q4")
        self.assertEqual(session.status, SessionStatus.CREATED)

        cand_a_text = (
            "Alice Smith\nSenior Infrastructure Engineer\n\n"
            "SUMMARY\n6 years experience designing distributed backends using Python, Go, and PostgreSQL.\n\n"
            "TECHNICAL SKILLS\nPython, Go, Docker, Kubernetes, PostgreSQL, AWS, Terraform\n\n"
            "WORK EXPERIENCE\nPrincipal Engineer at CloudTech (2018 - 2024)\n"
            "- Led infrastructure engineering and cloud architecture for 6 years.\n\n"
            "EDUCATION\nMaster of Science in Computer Science, Tech University (2018)\n"
        )
        cand_b_text = (
            "Bob Jones\nBackend Developer\n\n"
            "SUMMARY\n3 years experience building APIs with Python and PostgreSQL.\n\n"
            "TECHNICAL SKILLS\nPython, Django, PostgreSQL, Docker\n\n"
            "WORK EXPERIENCE\nSoftware Engineer at WebCo (2021 - 2024)\n\n"
            "EDUCATION\nBachelor of Science in Information Technology (2021)\n"
        )
        cand_c_text = (
            "Charlie Brown\nJunior Data Analyst\n\n"
            "TECHNICAL SKILLS\nExcel, Tableau, basic Python scripting\n\n"
            "WORK EXPERIENCE\nAnalyst at DataCorp (2023 - 2024)\n"
        )

        pdf_a = self._create_synthetic_pdf(cand_a_text)
        pdf_b = self._create_synthetic_pdf(cand_b_text)
        pdf_c = self._create_synthetic_pdf(cand_c_text)
        corrupted = b"NOT_A_VALID_PDF_HEADER"

        files = [
            {"filename": "alice_smith.pdf", "content": pdf_a, "size": len(pdf_a)},
            {"filename": "bob_jones.pdf", "content": pdf_b, "size": len(pdf_b)},
            {"filename": "charlie_brown.pdf", "content": pdf_c, "size": len(pdf_c)},
            {"filename": "alice_duplicate.pdf", "content": pdf_a, "size": len(pdf_a)},
            {"filename": "damaged_file.pdf", "content": corrupted, "size": len(corrupted)},
        ]

        ingest_report = self.orchestrator.add_resumes_to_session(session.id, files)
        self.assertEqual(ingest_report["enrolled"], 3)
        self.assertEqual(ingest_report["duplicate"], 1)
        self.assertEqual(ingest_report["failed"], 1)
        self.assertEqual(ingest_report["total_in_session"], 5)

        proc_res = self.orchestrator.process_session_batch(session.id)
        self.assertEqual(proc_res["processed_in_chunk"], 3)

        eval_res = self.orchestrator.evaluate_session_multi_layer(session_id=session.id)
        self.assertEqual(eval_res["evaluated_in_chunk"], 3)

        scoring_res = self.orchestrator.score_session(session.id)
        ranked_candidates = self.orchestrator.get_ranked_candidates(session.id)
        self.assertEqual(len(ranked_candidates), 3)

        top_cand = ranked_candidates[0]
        self.assertGreaterEqual(top_cand.overall_score, 50.0)

        self.orchestrator.update_shortlist_status(
            session_id=session.id,
            candidate_id=top_cand.candidate_id,
            status=ShortlistReviewStatus.SHORTLISTED,
            notes="Strong candidate with proven distributed systems background.",
        )
        shortlist = self.orchestrator.list_shortlist(session.id)
        self.assertEqual(len(shortlist), 1)
        self.assertEqual(shortlist[0].review_status, ShortlistReviewStatus.SHORTLISTED)

        cand_ids = [c.candidate_id for c in ranked_candidates[:2]]
        comp = self.orchestrator.generate_candidate_comparison(candidate_ids=cand_ids, session_id=session.id)
        self.assertEqual(len(comp.compared_candidate_ids), 2)
        self.assertTrue(comp.compatibility.is_compatible)

        weight_adjustments = {comp.aligned_criteria_rows[0].criterion_id: 0.5}
        sim_res = self.orchestrator.simulate_ranking_sensitivity(session.id, weight_adjustments)
        self.assertTrue(sim_res["success"])
        self.assertIn("simulated_candidates", sim_res)

        csv_bytes, csv_filename, _ = self.orchestrator.export_session_report(session.id, export_format=ExportFormat.CSV)
        self.assertTrue(len(csv_bytes) > 0)

        xlsx_bytes, xlsx_filename, _ = self.orchestrator.export_session_report(session.id, export_format=ExportFormat.XLSX)
        self.assertTrue(len(xlsx_bytes) > 0)

        analytics = self.orchestrator.get_session_analytics_profile(session.id)
        self.assertIsNotNone(analytics)
        self.assertEqual(analytics.enrolled_count, 4)
        self.assertEqual(analytics.total_scored, 3)
        self.assertGreater(analytics.mean_score, 0.0)

        skill_coverage = self.orchestrator.get_skill_coverage_analytics(session.id)
        self.assertTrue(len(skill_coverage) > 0)

        insights = self.orchestrator.get_session_insights(session.id)
        self.assertIsNotNone(insights)


if __name__ == "__main__":
    unittest.main()
