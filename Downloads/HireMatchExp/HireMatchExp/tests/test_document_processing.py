
from io import BytesIO
import json
import os
import tempfile
import unittest
import zipfile

from config import AppConfig
from core.models.candidate import Candidate
from core.models.enums import FileType, ProcessingStatus, SessionStatus
from core.models.job import Job
from core.models.session import ScreeningSession
from core.processing.cleaner import TextCleaner
from core.processing.extractor import DocxExtractor, PyMuPDFExtractor
from core.processing.jd_parser import EnhancedJDParser, StructuredJobDescription
from core.processing.resume_parser import StructuredResumeParser
from core.processing.section_detector import SectionDetector
from core.processing.skill_normalizer import ExtractedSkill, SkillTaxonomyNormalizer
from core.services.session_orchestrator import ScreeningOrchestrator
from core.storage.database import Database
from core.storage.repositories import CandidateRepository, JobRepository, SessionRepository


class TestTextCleaner(unittest.TestCase):

    def test_unicode_normalization_and_ligatures(self):
        raw_text = "The ofﬁce proﬁle was ﬂexible."
        cleaned = TextCleaner.clean(raw_text)
        self.assertIn("office", cleaned)
        self.assertIn("profile", cleaned)
        self.assertIn("flexible", cleaned)

    def test_whitespace_compaction(self):
        raw_text = "Senior   Software    Engineer \n\n\n\n  at   Google   \r\n"
        cleaned = TextCleaner.clean(raw_text)
        self.assertEqual(cleaned, "Senior Software Engineer\n\nat Google")

    def test_technical_tokens_preservation(self):
        raw_text = "Expert in C++, C#, .NET Core, CI/CD, and Node.js backend development."
        cleaned = TextCleaner.clean(raw_text)
        self.assertIn("C++", cleaned)
        self.assertIn("C#", cleaned)
        self.assertIn(".NET Core", cleaned)
        self.assertIn("CI/CD", cleaned)
        self.assertIn("Node.js", cleaned)

    def test_empty_or_whitespace_only(self):
        self.assertEqual(TextCleaner.clean(""), "")
        self.assertEqual(TextCleaner.clean("   \n\t  "), "")


class TestSectionDetector(unittest.TestCase):

    def setUp(self):
        self.detector = SectionDetector()

    def test_detect_canonical_sections(self):
        sample_resume = """
        John Doe
        john.doe@example.com | (555) 123-4567

        PROFESSIONAL SUMMARY
        Experienced software engineer specializing in distributed systems and cloud platforms.

        TECHNICAL SKILLS
        Python, Go, Docker, Kubernetes, AWS, PostgreSQL

        WORK EXPERIENCE
        Staff Software Engineer at Acme Corp (2020 - Present)
        - Architected cloud native microservices handling 100k requests/sec.
        - Mentored team of 8 junior engineers.

        EDUCATION
        B.S. in Computer Science, University of Technology (2014 - 2018)

        CERTIFICATIONS & LICENSES
        AWS Certified Solutions Architect - Professional (2022)

        KEY PROJECTS
        OpenSource Gateway: High throughput API gateway in Go.
        """
        sections = self.detector.detect_sections(sample_resume)

        section_names = [s.canonical_name for s in sections]
        self.assertIn("SUMMARY", section_names)
        self.assertIn("SKILLS", section_names)
        self.assertIn("EXPERIENCE", section_names)
        self.assertIn("EDUCATION", section_names)
        self.assertIn("CERTIFICATIONS", section_names)
        self.assertIn("PROJECTS", section_names)

        summary_sec = self.detector.get_section(sections, "SUMMARY")
        self.assertIsNotNone(summary_sec)
        self.assertIn("distributed systems", summary_sec.content)

        skills_sec = self.detector.get_section(sections, "SKILLS")
        self.assertIsNotNone(skills_sec)
        self.assertIn("Python, Go, Docker", skills_sec.content)


class TestSkillTaxonomyNormalizer(unittest.TestCase):

    def setUp(self):
        self.normalizer = SkillTaxonomyNormalizer()

    def test_canonical_alias_mapping(self):
        text = "Experienced with K8s cluster administration, JS web apps, and postgres databases."
        skills = self.normalizer.extract_and_normalize(text)
        canonical_names = {s.canonical_name for s in skills}

        self.assertIn("Kubernetes", canonical_names)
        self.assertIn("JavaScript", canonical_names)
        self.assertIn("PostgreSQL", canonical_names)

    def test_evidence_sentence_captured(self):
        text = "Led migration to Kubernetes for 40 microservices on AWS. Also used Golang for core API."
        skills = self.normalizer.extract_and_normalize(text)

        k8s_skill = next((s for s in skills if s.canonical_name == "Kubernetes"), None)
        self.assertIsNotNone(k8s_skill)
        self.assertIn("Led migration to Kubernetes", k8s_skill.evidence_sentence)

    def test_exact_lookup(self):
        canonical, cat = self.normalizer.normalize_skill("react.js")
        self.assertEqual(canonical, "React")
        self.assertEqual(cat, "Web & Frontend Frameworks")


class TestStructuredResumeParser(unittest.TestCase):

    def setUp(self):
        self.parser = StructuredResumeParser()

    def test_parse_complete_resume(self):
        text = """
        Alice Smith
        alice.smith@domain.org
        +1 415-555-0199
        San Francisco, CA

        SUMMARY
        Senior Backend Architect with 8+ years of production experience in high-scale systems.

        TECHNICAL SKILLS
        Python, FastApi, Docker, Kubernetes, PostgreSQL, Redis, AWS

        WORK EXPERIENCE
        Principal Engineer - CloudCorp (Jan 2021 - Present)
        San Francisco, CA
        - Directed cloud modernization initiative reducing infrastructure costs by 32%.
        - Designed event-driven data streaming pipeline with Kafka.

        Senior Backend Developer - DataFlow Inc (June 2017 - Dec 2020)
        - Developed REST APIs and microservices using Python and PostgreSQL.

        EDUCATION
        Master of Science in Computer Science
        Stanford University (2015 - 2017)

        Bachelor of Science in Software Engineering
        University of Michigan (2011 - 2015)

        CERTIFICATIONS
        AWS Certified Solutions Architect Associate (2021)
        """
        res = self.parser.parse_resume(text)

        self.assertEqual(res.contact.email, "alice.smith@domain.org")
        self.assertIn("555", res.contact.phone or "")
        self.assertEqual(res.contact.name, "Alice Smith")

        skill_names = {s.canonical_name for s in res.skills}
        self.assertIn("Python", skill_names)
        self.assertIn("Kubernetes", skill_names)
        self.assertIn("PostgreSQL", skill_names)

        self.assertGreaterEqual(len(res.work_experience), 1)
        self.assertTrue(any("CloudCorp" in exp.company or "Principal Engineer" in exp.title for exp in res.work_experience))

        self.assertGreaterEqual(len(res.education), 1)
        self.assertTrue(any("Stanford" in edu.institution or "Master" in edu.degree for edu in res.education))

        self.assertGreaterEqual(len(res.certifications), 1)
        self.assertTrue(any("AWS" in cert.name for cert in res.certifications))

    def test_missing_information_falls_back_gracefully(self):
        sparse_text = "Some unformatted notes without clear contact or skills."
        res = self.parser.parse_resume(sparse_text)

        self.assertIsNone(res.contact.email)
        self.assertIsNone(res.contact.phone)
        self.assertEqual(len(res.skills), 0)
        self.assertEqual(len(res.work_experience), 0)
        self.assertEqual(len(res.education), 0)


class TestEnhancedJDParser(unittest.TestCase):

    def setUp(self):
        self.parser = EnhancedJDParser()

    def test_parse_job_description(self):
        jd_text = """
        Job Title: Senior Data Engineer

        About the Role:
        We are seeking an experienced Senior Data Engineer to scale our real-time data infrastructure.

        Responsibilities:
        - Design and maintain scalable real-time streaming pipelines using Kafka and Spark.
        - Collaborate with data science and analytics teams to optimize query performance.
        - Ensure data governance, security, and quality across BigQuery data warehouse.

        Requirements:
        - 5+ years of software or data engineering experience.
        - Strong proficiency in Python, SQL, and distributed systems.
        - Hands-on experience with Apache Spark, Kafka, and PostgreSQL.
        - Bachelor's degree in Computer Science, Mathematics, or equivalent practical experience.

        Preferred Qualifications:
        - Experience with Docker, Kubernetes, and Terraform.
        - AWS or GCP cloud certifications.
        - Master's degree is a plus.
        """
        parsed = self.parser.parse_job_description(jd_text, fallback_title="Data Engineer")

        self.assertIn("Data Engineer", parsed.title or "")
        self.assertGreaterEqual(len(parsed.responsibilities), 2)
        self.assertEqual(parsed.min_experience_years, 5)

        req_skills = set(parsed.required_skills)
        pref_skills = set(parsed.preferred_skills)

        self.assertIn("Python", req_skills)
        self.assertIn("SQL", req_skills)
        self.assertIn("Docker", pref_skills)
        self.assertIn("Kubernetes", pref_skills)

        self.assertIn("Bachelor", parsed.education_level)


class TestDocumentExtractors(unittest.TestCase):

    def test_pdf_extraction_and_scanned_detection(self):
        extractor = PyMuPDFExtractor()

        pdf_bytes = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n" + (b"Hello World! This is an extractable PDF document with ample text. " * 3)
        extracted = extractor.extract(pdf_bytes, "test_resume.pdf")

        self.assertFalse(extracted.ocr_needed)
        self.assertIn("Hello World", extracted.text)

        scanned_bytes = b"%PDF-1.4\n"
        scanned_extracted = extractor.extract(scanned_bytes, "scanned_doc.pdf")
        self.assertTrue(scanned_extracted.ocr_needed)

    def test_docx_extraction(self):
        stream = BytesIO()
        with zipfile.ZipFile(stream, "w") as z:
            xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>Curriculum Vitae</w:t></w:r></w:p>
    <w:p><w:r><w:t>Experienced Cloud Architect specializing in GCP and Terraform.</w:t></w:r></w:p>
    <w:tbl>
      <w:tr>
        <w:tc><w:p><w:r><w:t>Skill</w:t></w:r></w:p></w:tc>
        <w:tc><w:p><w:r><w:t>Python</w:t></w:r></w:p></w:tc>
      </w:tr>
    </w:tbl>
  </w:body>
</w:document>"""
            z.writestr("word/document.xml", xml)
        docx_bytes = stream.getvalue()

        extractor = DocxExtractor()
        extracted = extractor.extract(docx_bytes, "resume.docx")

        self.assertFalse(extracted.ocr_needed)
        self.assertIn("Curriculum Vitae", extracted.text)
        self.assertIn("Cloud Architect", extracted.text)
        self.assertIn("Python", extracted.text)


class TestOrchestratorRetryMechanics(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_retry.db")
        self.db = Database(self.db_path)
        self.db.initialize_schema()
        self.config = AppConfig()
        self.config.storage_dir = os.path.join(self.temp_dir.name, "storage")
        os.makedirs(self.config.storage_dir, exist_ok=True)
        self.orchestrator = ScreeningOrchestrator(self.db, self.config)
        self.cand_repo = CandidateRepository(self.db)
        self.session_repo = SessionRepository(self.db)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_retry_failed_candidates(self):
        job_repo = JobRepository(self.db)
        job = job_repo.create(Job(title="Test Role", original_description="Testing retry"))

        session = ScreeningSession(
            session_name="Retry Test Session",
            job_id=job.id,
            status=SessionStatus.PROCESSING,
        )
        self.session_repo.create(session)

        cand1 = Candidate(
            original_filename="fail_doc.pdf",
            file_hash="1" * 64,
            file_type=FileType.PDF,
        )
        self.cand_repo.create(cand1)
        self.cand_repo.enroll_in_session(cand1.id, session.id, status=ProcessingStatus.FAILED)

        cand2 = Candidate(
            original_filename="good_doc.pdf",
            file_hash="2" * 64,
            file_type=FileType.PDF,
        )
        self.cand_repo.create(cand2)
        self.cand_repo.enroll_in_session(cand2.id, session.id, status=ProcessingStatus.COMPLETED)

        reset_count = self.orchestrator.retry_failed_candidates(session.id)
        self.assertEqual(reset_count, 1)

        cands = self.cand_repo.list_by_session(session.id)
        cand1_entry = next(c for c in cands if c["candidate"].id == cand1.id)
        cand2_entry = next(c for c in cands if c["candidate"].id == cand2.id)

        self.assertEqual(cand1_entry["session_status"], ProcessingStatus.PENDING)
        self.assertEqual(cand2_entry["session_status"], ProcessingStatus.COMPLETED)


if __name__ == "__main__":
    unittest.main()
