
from datetime import datetime
from pathlib import Path
import tempfile
import unittest

from config import AppConfig
from core.evaluation.baseline_evaluator import BaselineCandidateEvaluator
from core.evaluation.education_matcher import EducationMatcher
from core.evaluation.experience_matcher import ExperienceMatcher
from core.evaluation.keyword_matcher import SectionAwareKeywordMatcher
from core.evaluation.negation_detector import NegationDetector
from core.evaluation.scoring_engine import TransparentScoringEngine
from core.models.candidate import Candidate
from core.models.education import EducationRecord
from core.models.enums import CriterionType, FileType, MatchStatus, ProcessingStatus
from core.models.evaluation import CriterionEvaluationResult, EvaluationCriterion
from core.models.experience import WorkExperience
from core.models.job import Job
from core.models.skills import ExtractedSkill
from core.services.session_orchestrator import ScreeningOrchestrator
from core.storage.database import Database
from core.storage.repositories import (
    CandidateRepository,
    CriterionRepository,
    EvidenceRepository,
    JobRepository,
    ScoreRepository,
    SessionRepository,
)


class TestNegationDetector(unittest.TestCase):

    def setUp(self):
        self.detector = NegationDetector()

    def test_detects_explicit_negation_phrases(self):
        text1 = "I have no experience with GraphQL or Apollo."
        is_neg1, reason1 = self.detector.is_negated(text1, "GraphQL")
        self.assertTrue(is_neg1)
        self.assertIsNotNone(reason1)

        text2 = "Candidate has not worked with AWS Lambda."
        is_neg2, _ = self.detector.is_negated(text2, "AWS")
        self.assertTrue(is_neg2)

        text3 = "Never used Docker in production."
        is_neg3, _ = self.detector.is_negated(text3, "Docker")
        self.assertTrue(is_neg3)

        text4 = "Zero knowledge of Rust programming."
        is_neg4, _ = self.detector.is_negated(text4, "Rust")
        self.assertTrue(is_neg4)

    def test_positive_usage_not_flagged(self):
        text = "5 years of hands-on experience building scalable applications with Python and Docker."
        is_neg_py, _ = self.detector.is_negated(text, "Python")
        is_neg_dk, _ = self.detector.is_negated(text, "Docker")
        self.assertFalse(is_neg_py)
        self.assertFalse(is_neg_dk)

    def test_clause_boundary_isolation(self):
        text = "I have no experience with GCP, but extensive production experience with AWS."
        is_neg_gcp, _ = self.detector.is_negated(text, "GCP")
        is_neg_aws, _ = self.detector.is_negated(text, "AWS")
        self.assertTrue(is_neg_gcp)
        self.assertFalse(is_neg_aws)


class TestSectionAwareKeywordMatcher(unittest.TestCase):

    def setUp(self):
        self.matcher = SectionAwareKeywordMatcher()

    def test_exact_match_in_skills_section(self):
        crit = EvaluationCriterion(
            criterion_name="Python",
            description="Python programming",
            weight=0.5,
            criterion_type=CriterionType.REQUIRED,
            matching_config={"keywords": ["Python"]},
        )
        skills = [
            ExtractedSkill(skill_name="Python", normalized_skill_name="Python", evidence_text="Proficient in Python", source_location="SKILLS")
        ]
        sections = {
            "SKILLS": "Python, Docker, Kubernetes, SQL, Git",
            "EXPERIENCE": "Developed web applications using Flask and PostgreSQL.",
        }
        res = self.matcher.evaluate_criterion(crit, skills, sections, "Full resume text with Python")
        self.assertEqual(res.match_status, MatchStatus.SUPPORTED)
        self.assertGreaterEqual(res.score, 90.0)
        self.assertIn("SKILLS", res.evidence_sources)
        self.assertEqual(res.matching_method, "EXACT")

    def test_phrase_matching(self):
        crit = EvaluationCriterion(
            criterion_name="CI/CD",
            description="Continuous Integration and Deployment",
            weight=0.3,
            criterion_type=CriterionType.PREFERRED,
            matching_config={"keywords": ["Continuous Integration"]},
        )
        sections = {
            "EXPERIENCE": "Implemented Continuous Integration pipelines using GitHub Actions.",
        }
        res = self.matcher.evaluate_criterion(crit, [], sections, "Implemented Continuous Integration pipelines")
        self.assertEqual(res.match_status, MatchStatus.SUPPORTED)
        self.assertIn("EXPERIENCE", res.evidence_sources)

    def test_taxonomy_alias_resolution(self):
        crit = EvaluationCriterion(
            criterion_name="Kubernetes",
            description="Container orchestration",
            weight=0.4,
            criterion_type=CriterionType.REQUIRED,
            matching_config={"keywords": ["Kubernetes"]},
        )
        skills = [
            ExtractedSkill(skill_name="K8s", normalized_skill_name="Kubernetes", evidence_text="Experienced in K8s", source_location="SKILLS")
        ]
        sections = {
            "SKILLS": "Experienced in K8s orchestration and cloud deployment.",
        }
        res = self.matcher.evaluate_criterion(crit, skills, sections, "Experienced in K8s")
        self.assertEqual(res.match_status, MatchStatus.SUPPORTED)
        self.assertIn("Kubernetes", res.matched_terms)
        self.assertEqual(res.matching_method, "TAXONOMY_ALIAS")

    def test_section_weighting_hierarchy(self):
        crit = EvaluationCriterion(
            criterion_name="Terraform",
            description="Infrastructure as Code",
            weight=0.4,
            criterion_type=CriterionType.REQUIRED,
            matching_config={"keywords": ["Terraform"]},
        )
        res_skills = self.matcher.evaluate_criterion(
            crit,
            [],
            {"SKILLS": "Terraform, Ansible"},
            "Terraform, Ansible",
        )
        res_summary = self.matcher.evaluate_criterion(
            crit,
            [],
            {"SUMMARY": "DevOps engineer with Terraform background."},
            "DevOps engineer with Terraform background.",
        )
        self.assertGreater(res_skills.score, res_summary.score)

    def test_negation_prevents_credit(self):
        crit = EvaluationCriterion(
            criterion_name="Kubernetes",
            description="K8s container orchestration",
            weight=0.5,
            criterion_type=CriterionType.REQUIRED,
            matching_config={"keywords": ["Kubernetes"]},
        )
        sections = {
            "EXPERIENCE": "We had no experience with Kubernetes so we deployed on Docker Swarm.",
        }
        res = self.matcher.evaluate_criterion(
            crit,
            [],
            sections,
            "We had no experience with Kubernetes so we deployed on Docker Swarm.",
        )
        self.assertIn(res.match_status, (MatchStatus.NOT_FOUND, MatchStatus.INSUFFICIENT_EVIDENCE))
        self.assertEqual(res.score, 0.0)

    def test_missing_term_returns_not_found(self):
        crit = EvaluationCriterion(
            criterion_name="Elixir",
            description="Elixir functional language",
            weight=0.3,
            criterion_type=CriterionType.PREFERRED,
            matching_config={"keywords": ["Elixir"]},
        )
        sections = {"SKILLS": "Java, Spring Boot"}
        res = self.matcher.evaluate_criterion(crit, [], sections, "Java, Spring Boot")
        self.assertEqual(res.match_status, MatchStatus.NOT_FOUND)
        self.assertEqual(res.score, 0.0)
        self.assertEqual(len(res.supporting_evidence), 0)


class TestExperienceMatcher(unittest.TestCase):

    def setUp(self):
        self.matcher = ExperienceMatcher()

    def test_sufficient_experience(self):
        crit = EvaluationCriterion(
            criterion_name="Work Experience",
            description="At least 5 years experience",
            weight=0.3,
            criterion_type=CriterionType.REQUIRED,
            matching_config={"min_years": 5.0},
        )
        exp_records = [
            WorkExperience(
                job_title="Senior Engineer",
                dates="2020 - 2024",
                employer="Tech Corp",
                extracted_description="Built cloud backend services.",
            ),
            WorkExperience(
                job_title="Software Engineer",
                dates="2018 - 2020",
                employer="Startup Inc",
                extracted_description="Full-stack development.",
            ),
        ]
        res = self.matcher.evaluate_criterion(crit, exp_records)
        self.assertEqual(res.match_status, MatchStatus.SUPPORTED)
        self.assertEqual(res.score, 100.0)
        self.assertIn("6.0", res.explanation)

    def test_concurrent_jobs_do_not_double_count_tenure(self):
        crit = EvaluationCriterion(
            criterion_name="Experience",
            description="5+ years required",
            weight=0.3,
            criterion_type=CriterionType.REQUIRED,
            matching_config={"min_years": 5.0},
        )
        exp_records = [
            WorkExperience(job_title="Lead Developer", dates="2020 - 2023", employer="Company A"),
            WorkExperience(job_title="Consultant", dates="2021 - 2023", employer="Company B"),
        ]
        res = self.matcher.evaluate_criterion(crit, exp_records)
        self.assertEqual(res.match_status, MatchStatus.PARTIALLY_SUPPORTED)
        self.assertAlmostEqual(res.score, 60.0, places=1)

    def test_missing_or_unparseable_dates_insufficient_evidence(self):
        crit = EvaluationCriterion(
            criterion_name="Experience",
            description="3 years expected",
            weight=0.3,
            criterion_type=CriterionType.REQUIRED,
            matching_config={"min_years": 3.0},
        )
        exp_records = [
            WorkExperience(job_title="Developer", dates="Past experience", employer="Company"),
        ]
        res = self.matcher.evaluate_criterion(crit, exp_records)
        self.assertEqual(res.match_status, MatchStatus.INSUFFICIENT_EVIDENCE)
        self.assertIn("dates", res.explanation.lower())


class TestEducationMatcher(unittest.TestCase):

    def setUp(self):
        self.matcher = EducationMatcher()

    def test_higher_degree_satisfies_requirement(self):
        crit = EvaluationCriterion(
            criterion_name="Education",
            description="Bachelor's degree in CS",
            weight=0.2,
            criterion_type=CriterionType.REQUIRED,
            matching_config={"required_level": "Bachelor's"},
        )
        edu_records = [
            EducationRecord(qualification="Master of Science in Computer Science", institution="MIT", dates="2020"),
        ]
        res = self.matcher.evaluate_criterion(crit, edu_records)
        self.assertEqual(res.match_status, MatchStatus.SUPPORTED)
        self.assertEqual(res.score, 100.0)
        self.assertIn("Master's", res.explanation)

    def test_degree_abbreviation_mapping(self):
        crit = EvaluationCriterion(
            criterion_name="Education",
            description="Bachelor's degree required",
            weight=0.2,
            criterion_type=CriterionType.REQUIRED,
            matching_config={"required_level": "Bachelor's"},
        )
        edu_records = [
            EducationRecord(qualification="B.S. in Software Engineering", institution="State University", dates="2019"),
        ]
        res = self.matcher.evaluate_criterion(crit, edu_records)
        self.assertEqual(res.match_status, MatchStatus.SUPPORTED)
        self.assertEqual(res.score, 100.0)

    def test_lower_degree_partial_support(self):
        crit = EvaluationCriterion(
            criterion_name="Education",
            description="Bachelor's degree required",
            weight=0.2,
            criterion_type=CriterionType.REQUIRED,
            matching_config={"required_level": "Bachelor's"},
        )
        edu_records = [
            EducationRecord(qualification="Associate Degree in Information Technology", dates="2018"),
        ]
        res = self.matcher.evaluate_criterion(crit, edu_records)
        self.assertEqual(res.match_status, MatchStatus.PARTIALLY_SUPPORTED)
        self.assertLess(res.score, 100.0)

    def test_certification_matching(self):
        crit = EvaluationCriterion(
            criterion_name="Education & Credentials",
            description="Bachelor's degree or certifications",
            weight=0.2,
            criterion_type=CriterionType.PREFERRED,
            matching_config={"required_level": "Bachelor's"},
        )
        certs = ["AWS Certified Solutions Architect - Associate"]
        res = self.matcher.evaluate_criterion(crit, [], candidate_certifications=certs)
        self.assertEqual(res.match_status, MatchStatus.PARTIALLY_SUPPORTED)
        self.assertEqual(res.score, 40.0)


class TestScoringEngine(unittest.TestCase):

    def setUp(self):
        self.scoring_engine = TransparentScoringEngine()

    def test_normalized_score_aggregation_and_coverage(self):
        criteria = [
            EvaluationCriterion(
                id="c1",
                criterion_name="Python",
                weight=0.5,
                criterion_type=CriterionType.REQUIRED,
            ),
            EvaluationCriterion(
                id="c2",
                criterion_name="Kubernetes",
                weight=0.3,
                criterion_type=CriterionType.REQUIRED,
            ),
            EvaluationCriterion(
                id="c3",
                criterion_name="GraphQL",
                weight=0.2,
                criterion_type=CriterionType.PREFERRED,
            ),
        ]

        results = [
            CriterionEvaluationResult(
                criterion_id="c1",
                criterion_name="Python",
                criterion_type=CriterionType.REQUIRED,
                weight=0.5,
                match_status=MatchStatus.SUPPORTED,
                score=100.0,
                supporting_evidence=["5 years of Python"],
            ),
            CriterionEvaluationResult(
                criterion_id="c2",
                criterion_name="Kubernetes",
                criterion_type=CriterionType.REQUIRED,
                weight=0.3,
                match_status=MatchStatus.PARTIALLY_SUPPORTED,
                score=50.0,
                supporting_evidence=["Basic Kubernetes"],
            ),
            CriterionEvaluationResult(
                criterion_id="c3",
                criterion_name="GraphQL",
                criterion_type=CriterionType.PREFERRED,
                weight=0.2,
                match_status=MatchStatus.NOT_FOUND,
                score=0.0,
            ),
        ]

        score = self.scoring_engine.aggregate_results(
            candidate_id="cand_test_1",
            criteria=criteria,
            criterion_results=results,
        )

        self.assertAlmostEqual(score.overall_score, 65.0, places=1)
        self.assertAlmostEqual(score.evidence_coverage, 66.7, places=1)
        self.assertEqual(score.required_unmet_count, 0)
        self.assertTrue(score.required_supported)
        self.assertIn("65.0/100", score.explanation)

    def test_unmet_required_criteria_flagged(self):
        criteria = [
            EvaluationCriterion(
                id="c1",
                criterion_name="Python",
                weight=0.6,
                criterion_type=CriterionType.REQUIRED,
            ),
            EvaluationCriterion(
                id="c2",
                criterion_name="Rust",
                weight=0.4,
                criterion_type=CriterionType.REQUIRED,
            ),
        ]

        results = [
            CriterionEvaluationResult(
                criterion_id="c1",
                criterion_name="Python",
                criterion_type=CriterionType.REQUIRED,
                weight=0.6,
                match_status=MatchStatus.SUPPORTED,
                score=100.0,
                supporting_evidence=["Expert in Python"],
            ),
            CriterionEvaluationResult(
                criterion_id="c2",
                criterion_name="Rust",
                criterion_type=CriterionType.REQUIRED,
                weight=0.4,
                match_status=MatchStatus.NOT_FOUND,
                score=0.0,
            ),
        ]

        score = self.scoring_engine.aggregate_results(
            candidate_id="cand_test_2",
            criteria=criteria,
            criterion_results=results,
        )

        self.assertFalse(score.required_supported)
        self.assertEqual(score.required_unmet_count, 1)
        self.assertIn("Mandatory criteria missing evidence: Rust", score.explanation)


class TestOrchestratorBatchEvaluation(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        base = Path(self.temp_dir.name)

        self.config = AppConfig(
            base_dir=base,
            db_path=base / "test_eval_hm.db",
            storage_dir=base / "storage",
            cache_dir=base / "cache",
            temp_dir=base / "temp",
            processing_batch_size=5,
        )
        self.config.ensure_directories()

        self.db = Database(self.config.db_path)
        self.db.initialize_schema()

        self.orchestrator = ScreeningOrchestrator(self.db, self.config)
        self.job_repo = JobRepository(self.db)
        self.session_repo = SessionRepository(self.db)
        self.candidate_repo = CandidateRepository(self.db)
        self.score_repo = ScoreRepository(self.db)
        self.evidence_repo = EvidenceRepository(self.db)
        self.crit_repo = CriterionRepository(self.db)

        self.job = self.job_repo.create(
            Job(
                title="Full Stack Python Developer",
                original_description="Looking for a Python and React developer with 3+ years experience and a Bachelor's degree.",
            )
        )

        self.criteria = [
            EvaluationCriterion(
                criterion_name="Python Programming",
                description="Python, FastAPI, Django",
                weight=0.40,
                criterion_type=CriterionType.REQUIRED,
                matching_config={"keywords": ["Python"]},
            ),
            EvaluationCriterion(
                criterion_name="React & Frontend",
                description="React, TypeScript, CSS",
                weight=0.30,
                criterion_type=CriterionType.REQUIRED,
                matching_config={"keywords": ["React"]},
            ),
            EvaluationCriterion(
                criterion_name="Experience Tenure",
                description="3+ years of software engineering",
                weight=0.20,
                criterion_type=CriterionType.REQUIRED,
                matching_config={"min_years": 3.0},
            ),
            EvaluationCriterion(
                criterion_name="Education",
                description="Bachelor's degree in Computer Science or related",
                weight=0.10,
                criterion_type=CriterionType.PREFERRED,
                matching_config={"required_level": "Bachelor's"},
            ),
        ]
        self.crit_repo.save_batch(self.criteria, self.job.id)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_evaluate_session_batch_end_to_end(self):
        session = self.orchestrator.create_session(job_id=self.job.id, session_name="Sprint 1 Screening")

        cand1 = Candidate(
            original_filename="john_doe.pdf",
            file_hash="a" * 64,
            file_type=FileType.PDF,
            processing_status=ProcessingStatus.COMPLETED,
            extracted_text="John Doe Python React Developer with 4 years experience. B.S. in CS.",
        )
        self.candidate_repo.create(cand1)
        self.candidate_repo.link_to_session(
            session_id=session.id,
            candidate_id=cand1.id,
            processing_status=ProcessingStatus.COMPLETED,
            manifest_meta={"filename": "john_doe.pdf", "size_bytes": 1024},
        )
        cand1_struct = {
            "contact": {"name": "John Doe", "email": "john@example.com"},
            "skills": [
                {"skill_name": "Python", "normalized_skill_name": "Python", "evidence_text": "Python Developer", "source_location": "SKILLS"},
                {"skill_name": "React", "normalized_skill_name": "React", "evidence_text": "React Developer", "source_location": "SKILLS"},
            ],
            "experience": [
                {"job_title": "Senior Developer", "employer": "CloudTech", "dates": "2020 - 2024", "extracted_description": "Python React full stack", "evidence_text": "2020 - 2024 Senior Developer"},
            ],
            "education": [
                {"qualification": "B.S. in Computer Science", "institution": "Tech Univ", "dates": "2016 - 2020", "evidence_text": "B.S. in CS"},
            ],
            "sections": [
                {"canonical_name": "SKILLS", "display_title": "Skills", "content": "Python, React, Docker"},
                {"canonical_name": "EXPERIENCE", "display_title": "Work Experience", "content": "Senior Developer at CloudTech 2020 - 2024"},
                {"canonical_name": "EDUCATION", "display_title": "Education", "content": "B.S. in Computer Science"},
            ],
        }
        self.candidate_repo.update_structured_data(cand1.id, cand1_struct)
        self.candidate_repo.save_extracted_entities(
            candidate_id=cand1.id,
            skills=[
                ExtractedSkill(skill_name="Python", normalized_skill_name="Python", evidence_text="Python Developer", source_location="SKILLS"),
                ExtractedSkill(skill_name="React", normalized_skill_name="React", evidence_text="React Developer", source_location="SKILLS"),
            ],
            experience=[
                WorkExperience(job_title="Senior Developer", employer="CloudTech", dates="2020 - 2024", extracted_description="Python React full stack"),
            ],
            education=[
                EducationRecord(qualification="B.S. in Computer Science", institution="Tech Univ", dates="2016 - 2020"),
            ],
        )

        cand2 = Candidate(
            original_filename="jane_smith.pdf",
            file_hash="b" * 64,
            file_type=FileType.PDF,
            processing_status=ProcessingStatus.COMPLETED,
            extracted_text="Jane Smith Junior Analyst. No experience with React or Python.",
        )
        self.candidate_repo.create(cand2)
        self.candidate_repo.link_to_session(
            session_id=session.id,
            candidate_id=cand2.id,
            processing_status=ProcessingStatus.COMPLETED,
            manifest_meta={"filename": "jane_smith.pdf", "size_bytes": 1024},
        )
        cand2_struct = {
            "contact": {"name": "Jane Smith", "email": "jane@example.com"},
            "skills": [
                {"skill_name": "Excel", "normalized_skill_name": "Excel", "evidence_text": "Excel spreadsheets", "source_location": "SKILLS"},
            ],
            "experience": [
                {"job_title": "Data Intern", "employer": "FinCorp", "dates": "2023 - 2024", "extracted_description": "Spreadsheets", "evidence_text": "Data Intern"},
            ],
            "education": [
                {"qualification": "High School Diploma", "institution": "Local High", "dates": "2022", "evidence_text": "High School"},
            ],
            "sections": [
                {"canonical_name": "SKILLS", "display_title": "Skills", "content": "Excel spreadsheets"},
                {"canonical_name": "EXPERIENCE", "display_title": "Experience", "content": "Intern 2023 - 2024"},
            ],
        }
        self.candidate_repo.update_structured_data(cand2.id, cand2_struct)
        self.candidate_repo.save_extracted_entities(
            candidate_id=cand2.id,
            skills=[
                ExtractedSkill(skill_name="Excel", normalized_skill_name="Excel", evidence_text="Excel spreadsheets", source_location="SKILLS"),
            ],
            experience=[
                WorkExperience(job_title="Data Intern", employer="FinCorp", dates="2023 - 2024", extracted_description="Spreadsheets"),
            ],
            education=[
                EducationRecord(qualification="High School Diploma", institution="Local High", dates="2022"),
            ],
        )

        eval_res = self.orchestrator.evaluate_session_batch(session.id)
        self.assertEqual(eval_res["evaluated_in_chunk"], 2)
        self.assertEqual(eval_res["failed_in_chunk"], 0)

        scores = self.score_repo.list_by_session(session.id)
        self.assertEqual(len(scores), 2)

        john_score = next(s for s in scores.values() if s.overall_score > 60.0)
        self.assertGreaterEqual(john_score.overall_score, 70.0)
        self.assertGreaterEqual(john_score.evidence_coverage, 75.0)
        self.assertTrue(john_score.required_supported)

        jane_score = next(s for s in scores.values() if s.overall_score <= 50.0)
        self.assertLess(jane_score.overall_score, 40.0)
        self.assertFalse(jane_score.required_supported)
        self.assertGreater(jane_score.required_unmet_count, 0)

        john_evidence = self.evidence_repo.list_by_candidate(john_score.candidate_id)
        self.assertGreater(len(john_evidence), 0)
        self.assertTrue(any("python" in ev.supporting_text.lower() for ev in john_evidence))

        cands = self.candidate_repo.list_by_session(session.id)
        self.assertTrue(all(c["session_status"] == ProcessingStatus.EVALUATED for c in cands))


if __name__ == "__main__":
    unittest.main()
