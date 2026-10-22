
import io
from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient

from backend.app.api.deps import get_config, get_database, get_orchestrator
from unittest.mock import patch
from backend.app.main import app
from config import AppConfig
from core.evaluation.embedding_provider import MockEmbeddingProvider
from core.models.enums import CriterionCategory, CriterionType
from core.models.evaluation import EvaluationCriterion
from core.services.session_orchestrator import ScreeningOrchestrator
from core.storage.database import Database


class TestAPIEndpoints(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.patcher = patch(
            "core.services.session_orchestrator.ModelManager.get_embedding_provider",
            return_value=MockEmbeddingProvider(dimension=384),
        )
        cls.patcher.start()

    @classmethod
    def tearDownClass(cls):
        cls.patcher.stop()

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        base = Path(self.temp_dir.name)

        self.config = AppConfig(
            base_dir=base,
            db_path=base / "api_test.db",
            storage_dir=base / "storage",
            cache_dir=base / "cache",
            temp_dir=base / "temp",
            reports_dir=base / "reports",
            max_resumes_per_session=100,
            processing_batch_size=10,
        )
        self.config.ensure_directories()

        self.db = Database(self.config.db_path)
        self.db.initialize_schema()

        self.orchestrator = ScreeningOrchestrator(self.db, self.config)

        app.dependency_overrides[get_config] = lambda: self.config
        app.dependency_overrides[get_database] = lambda: self.db
        app.dependency_overrides[get_orchestrator] = lambda: self.orchestrator

        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.temp_dir.cleanup()

    def test_root_and_health(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "online")
        self.assertEqual(data["api_prefix"], "/api")

        health_res = self.client.get("/api/health")
        self.assertEqual(health_res.status_code, 200)
        h_data = health_res.json()
        self.assertTrue(h_data["database_connected"])
        self.assertEqual(h_data["status"], "healthy")

    def test_settings_endpoint(self):
        res = self.client.get("/api/settings")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["max_resumes_per_session"], 100)
        self.assertEqual(data["processing_batch_size"], 10)
        self.assertIn(".pdf", data["supported_file_types"])

    def test_job_and_criteria_lifecycle(self):
        raw_text = (
            "Senior Python Engineer\n"
            "We are looking for a Python developer with 5+ years of experience with FastAPI and PostgreSQL. "
            "Bachelor's degree in Computer Science required. AWS experience preferred."
        )
        parse_res = self.client.post("/api/jobs/parse", json={"description": raw_text})
        self.assertEqual(parse_res.status_code, 200)
        parsed = parse_res.json()
        self.assertTrue(len(parsed["auto_criteria"]) >= 2)

        job_payload = {
            "title": "Senior Python Engineer",
            "department": "Engineering",
            "original_description": raw_text,
        }
        create_res = self.client.post("/api/jobs", json=job_payload)
        self.assertEqual(create_res.status_code, 201)
        job_data = create_res.json()
        job_id = job_data["id"]
        self.assertEqual(job_data["title"], "Senior Python Engineer")

        get_res = self.client.get(f"/api/jobs/{job_id}")
        self.assertEqual(get_res.status_code, 200)
        self.assertEqual(get_res.json()["id"], job_id)

    def test_session_lifecycle_and_resume_upload(self):
        job_res = self.client.post(
            "/api/jobs",
            json={"title": "Full Stack Engineer", "original_description": "Seeking Python and React developers with 3 years experience."},
        )
        self.assertEqual(job_res.status_code, 201)
        job_id = job_res.json()["id"]

        sess_payload = {
            "job_id": job_id,
            "session_name": "Batch Q4 2026",
            "max_resume_count": 50,
        }
        res = self.client.post("/api/sessions", json=sess_payload)
        self.assertEqual(res.status_code, 201)
        sess_data = res.json()
        session_id = sess_data["id"]
        self.assertEqual(sess_data["session_name"], "Batch Q4 2026")

        list_res = self.client.get("/api/sessions")
        self.assertEqual(list_res.status_code, 200)
        self.assertGreaterEqual(len(list_res.json()), 1)

        alice_content = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\nAlice Python Dev\n%%EOF"
        bob_content = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\nBob React Dev\n%%EOF"
        files = [
            ("files", ("alice_resume.pdf", io.BytesIO(alice_content), "application/pdf")),
            ("files", ("bob_resume.pdf", io.BytesIO(bob_content), "application/pdf")),
        ]
        up_res = self.client.post(f"/api/sessions/{session_id}/resumes", files=files)
        self.assertEqual(up_res.status_code, 200)
        up_data = up_res.json()
        self.assertEqual(len(up_data["details"]), 2)
        self.assertEqual(up_data["enrolled"], 2)

        status_res = self.client.get(f"/api/sessions/{session_id}/processing-status")
        self.assertEqual(status_res.status_code, 200)
        s_data = status_res.json()
        self.assertEqual(s_data["total"], 2)

        cands_res = self.client.get(f"/api/sessions/{session_id}/candidates")
        self.assertEqual(cands_res.status_code, 200)
        c_list = cands_res.json()
        self.assertEqual(c_list["total"], 2)

    def test_shortlist_human_in_the_loop_update(self):
        job_res = self.client.post(
            "/api/jobs",
            json={"title": "Backend Architect", "original_description": "Expert in cloud backend systems and microservices."},
        )
        self.assertEqual(job_res.status_code, 201)
        job_id = job_res.json()["id"]

        session_res = self.client.post(
            "/api/sessions",
            json={"job_id": job_id, "session_name": "Review Batch"},
        )
        self.assertEqual(session_res.status_code, 201)
        session_id = session_res.json()["id"]

        pdf_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\ntrailer\n<<\n>>\n%%EOF"
        up_res = self.client.post(
            f"/api/sessions/{session_id}/resumes",
            files=[("files", ("architect.pdf", io.BytesIO(pdf_content), "application/pdf"))],
        )
        self.assertEqual(up_res.status_code, 200)
        c1_id = up_res.json()["details"][0]["candidate_id"]

        payload = {
            "review_status": "SHORTLISTED",
            "reviewer_notes": "Strong candidate with comprehensive system design evidence.",
        }
        put_res = self.client.put(f"/api/candidates/{c1_id}/shortlist", json=payload)
        self.assertEqual(put_res.status_code, 200)
        res_data = put_res.json()
        self.assertEqual(res_data["review_status"], "SHORTLISTED")
        self.assertEqual(res_data["reviewer_notes"], payload["reviewer_notes"])

    def test_model_lab_endpoints(self):
        models_res = self.client.get("/api/models")
        self.assertEqual(models_res.status_code, 200)
        models = models_res.json()
        self.assertIsInstance(models, list)
        self.assertGreaterEqual(len(models), 1)

        datasets_res = self.client.get("/api/model-lab/datasets")
        self.assertEqual(datasets_res.status_code, 200)
        datasets = datasets_res.json()
        self.assertIsInstance(datasets, list)

    def test_analytics_overview_endpoint(self):
        res = self.client.get("/api/analytics/overview")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("total_sessions", data)
        self.assertIn("overall_funnel", data)
        self.assertIn("processing_outcomes", data)


if __name__ == "__main__":
    unittest.main()
