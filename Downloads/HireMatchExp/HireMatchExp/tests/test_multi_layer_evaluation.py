
import shutil
import tempfile
import unittest
from pathlib import Path

from config import AppConfig
from core.evaluation.criteria_validator import ResponsibleAICriteriaValidator
from core.evaluation.education_cert_evaluator import EducationCertEvaluator
from core.evaluation.evidence_synthesizer import (
    MultiLayerEvidenceSynthesizer,
    SynthesizedCriterionEvaluation,
)
from core.evaluation.experience_evaluator import ConservativeExperienceEvaluator
from core.evaluation.multi_layer_evaluator import MultiLayerCandidateEvaluator
from core.models.candidate import Candidate
from core.models.education import EducationRecord
from core.models.enums import (
    CriterionCategory,
    CriterionType,
    EvidenceDisagreementType,
    FileType,
    MatchStatus,
    ProcessingStatus,
    SemanticSimilarityTier,
)
from core.models.eval_config import EvaluationConfiguration
from core.models.evaluation import (
    CandidateEvaluationRecord,
    CriterionEvaluationResult,
    EvaluationCriterion,
)
from core.models.experience import WorkExperience
from core.models.job import Job
from core.models.session import ScreeningSession
from core.models.skills import ExtractedSkill
from core.services.session_orchestrator import ScreeningOrchestrator
from core.storage.database import Database
from core.storage.eval_repository import (
    EvaluationConfigurationRepository,
    EvaluationRecordRepository,
)
from core.storage.repositories import (
    CandidateRepository,
    JobRepository,
    SessionRepository,
)


class TestResponsibleAICriteriaValidator(unittest.TestCase):

    def setUp(self):
        self.validator = ResponsibleAICriteriaValidator()

    def test_valid_job_criteria(self):
        valid_crits = [
            EvaluationCriterion(criterion_name="Python Backend", description="Experience with FastAPI and Python 3.11", weight=0.3),
            EvaluationCriterion(criterion_name="Cloud Infrastructure", description="AWS or GCP cloud deployment and Docker", weight=0.3),
            EvaluationCriterion(criterion_name="Bachelor's Degree", description="BS in Computer Science or related field", weight=0.2),
            EvaluationCriterion(criterion_name="Years of Experience", description="At least 5 years of professional software engineering", weight=0.2),
        ]
        for c in valid_crits:
            res = self.validator.validate_criterion(c)
            self.assertTrue(res.is_valid, f"Expected '{c.criterion_name}' to be valid, got: {res.violations}")

    def test_demographic_exclusions(self):
        forbidden_cases = [
            ("Age Restriction", "Candidate must be under 35 years old", "age"),
            ("Gender Requirement", "Seeking female software developers for diversity quota", "gender"),
            ("Religion", "Active member of Christian community", "religion"),
            ("Marital Status", "Must be single with no dependents", "marital"),
            ("Nationality", "Must be Indian citizen or native English speaker", "nationality"),
            ("Physical Appearance", "Must submit professional headshot photograph", "photo"),
        ]
        for name, desc, expected_cat in forbidden_cases:
            crit = EvaluationCriterion(criterion_name=name, description=desc, weight=0.2)
            res = self.validator.validate_criterion(crit)
            self.assertFalse(res.is_valid, f"Expected '{name}' to be rejected for demographic exclusion.")
            self.assertTrue(any(expected_cat in v.lower() for v in res.violations), f"Expected '{expected_cat}' in violations: {res.violations}")

    def test_personality_exclusions(self):
        personality_cases = [
            ("Cultural Fit", "Must match team culture and good vibes", "personality"),
            ("Rockstar Developer", "Looking for a 10x ninja rockstar developer", "personality"),
            ("Personality Check", "Must have an outgoing, charismatic personality", "personality"),
        ]
        for name, desc, expected_cat in personality_cases:
            crit = EvaluationCriterion(criterion_name=name, description=desc, weight=0.2)
            res = self.validator.validate_criterion(crit)
            self.assertFalse(res.is_valid, f"Expected '{name}' to be rejected for personality exclusion.")


class TestConservativeExperienceEvaluator(unittest.TestCase):

    def setUp(self):
        self.evaluator = ConservativeExperienceEvaluator()

    def test_non_overlapping_tenure_merging(self):
        crit = EvaluationCriterion(
            criterion_name="5+ Years Software Engineering",
            description="Demonstrated track record of 5+ years",
            evidence_requirements={"years": 5.0},
            category=CriterionCategory.EXPERIENCE_DURATION,
        )
        exp = [
            WorkExperience(job_title="Senior Engineer", employer="Company A", dates="2020 - 2024", extracted_description="Python"),
            WorkExperience(job_title="Consultant", employer="Company B", dates="2021 - 2023", extracted_description="Python"),
        ]
        res = self.evaluator.evaluate(crit, exp, relevant_keywords=["python"])
        self.assertEqual(res.match_status, MatchStatus.PARTIALLY_SUPPORTED)
        self.assertAlmostEqual(res.score, 80.0, delta=1.0)

    def test_sufficient_tenure_supported(self):
        crit = EvaluationCriterion(
            criterion_name="3+ Years Experience",
            description="3+ years in DevOps",
            evidence_requirements={"years": 3.0},
            category=CriterionCategory.EXPERIENCE_DURATION,
        )
        exp = [
            WorkExperience(job_title="DevOps Engineer", employer="Cloud Corp", dates="2019 - 2023", extracted_description="Kubernetes"),
        ]
        res = self.evaluator.evaluate(crit, exp)
        self.assertEqual(res.match_status, MatchStatus.SUPPORTED)
        self.assertEqual(res.score, 100.0)

    def test_missing_dates_insufficient_evidence_not_penalized(self):
        crit = EvaluationCriterion(
            criterion_name="4+ Years Experience",
            description="4+ years required",
            evidence_requirements={"years": 4.0},
            category=CriterionCategory.EXPERIENCE_DURATION,
        )
        exp = [
            WorkExperience(job_title="Software Developer", employer="Startup", dates="Various", extracted_description="Python"),
        ]
        res = self.evaluator.evaluate(crit, exp)
        self.assertEqual(res.match_status, MatchStatus.INSUFFICIENT_EVIDENCE)
        self.assertIn("INSUFFICIENT_EVIDENCE without negative penalty", res.explanation)


class TestEducationCertEvaluator(unittest.TestCase):

    def setUp(self):
        self.evaluator = EducationCertEvaluator()

    def test_degree_tier_exceeds(self):
        crit = EvaluationCriterion(
            criterion_name="Bachelor's Degree",
            description="Bachelor's in Computer Science or related",
            category=CriterionCategory.EDUCATION_REQUIREMENT,
        )
        edu = [
            EducationRecord(qualification="Master of Science in Computer Science", institution="MIT", dates="2020 - 2022"),
        ]
        res = self.evaluator.evaluate(crit, edu)
        self.assertEqual(res.match_status, MatchStatus.SUPPORTED)
        self.assertEqual(res.score, 100.0)
        self.assertIn("Exceeds", res.explanation)

    def test_degree_tier_falls_short(self):
        crit = EvaluationCriterion(
            criterion_name="Master's Degree",
            description="Master of Science required",
            category=CriterionCategory.EDUCATION_REQUIREMENT,
        )
        edu = [
            EducationRecord(qualification="High School Diploma", institution="West High", dates="2018"),
        ]
        res = self.evaluator.evaluate(crit, edu)
        self.assertEqual(res.match_status, MatchStatus.NOT_FOUND)
        self.assertEqual(res.disagreement_type, EvidenceDisagreementType.DEGREE_MISMATCH)

    def test_certification_issuer_matching(self):
        crit = EvaluationCriterion(
            criterion_name="AWS Certified Solutions Architect",
            description="AWS Cloud certification",
            category=CriterionCategory.CERTIFICATION,
        )
        certs = ["AWS Certified Solutions Architect - Associate"]
        res = self.evaluator.evaluate(crit, [], certifications=certs)
        self.assertEqual(res.match_status, MatchStatus.SUPPORTED)
        self.assertEqual(res.score, 100.0)

    def test_missing_education_not_negative_proof(self):
        crit = EvaluationCriterion(
            criterion_name="Bachelor's Degree",
            description="Bachelor's degree required",
            category=CriterionCategory.EDUCATION_REQUIREMENT,
        )
        res = self.evaluator.evaluate(crit, [], certifications=[])
        self.assertEqual(res.match_status, MatchStatus.INSUFFICIENT_EVIDENCE)
        self.assertIn("does not confirm absence of qualifications", res.explanation)


class TestEvidenceSynthesisAndConflicts(unittest.TestCase):

    def test_negation_vs_semantic_conflict_detection(self):
        crit = EvaluationCriterion(
            id="crit-react",
            criterion_name="React Frontend",
            description="Commercial React experience",
            weight=0.3,
        )
        b_res = CriterionEvaluationResult(
            criterion_id="crit-react",
            criterion_name="React Frontend",
            criterion_type=CriterionType.REQUIRED,
            weight=0.3,
            match_status=MatchStatus.NOT_FOUND,
            score=0.0,
            is_negative_context=True,
            explanation="Candidate states: No commercial experience with React",
            supporting_evidence=["No commercial experience with React"],
            evidence_sources=["EXPERIENCE"],
            confidence=0.95,
        )
        s_res = CriterionEvaluationResult(
            criterion_id="crit-react",
            criterion_name="React Frontend",
            criterion_type=CriterionType.REQUIRED,
            weight=0.3,
            match_status=MatchStatus.SUPPORTED,
            score=82.0,
            semantic_score=0.78,
            similarity_tier=SemanticSimilarityTier.STRONG,
            top_passages=[{"passage_text": "No commercial experience with React", "source_section": "EXPERIENCE", "similarity_score": 0.78}],
        )

        synth = MultiLayerEvidenceSynthesizer.synthesize_criterion(crit, b_res, s_res)
        self.assertEqual(synth.match_status, MatchStatus.CONFLICTING_EVIDENCE)
        self.assertEqual(synth.disagreement_type, EvidenceDisagreementType.KEYWORD_NEGATED_IN_CONTEXT)
        self.assertEqual(synth.synthesized_score, 0.0)
        self.assertIn("Conflict detected", synth.conflict_explanation)

    def test_citation_deduplication(self):
        b_res = CriterionEvaluationResult(
            criterion_id="crit-k8s",
            criterion_name="Kubernetes",
            criterion_type=CriterionType.REQUIRED,
            weight=0.3,
            match_status=MatchStatus.SUPPORTED,
            score=100.0,
            supporting_evidence=["Managed production Kubernetes clusters on AWS"],
            evidence_sources=["EXPERIENCE"],
            confidence=0.9,
        )
        s_res = CriterionEvaluationResult(
            criterion_id="crit-k8s",
            criterion_name="Kubernetes",
            criterion_type=CriterionType.REQUIRED,
            weight=0.3,
            match_status=MatchStatus.SUPPORTED,
            score=95.0,
            semantic_score=0.85,
            top_passages=[{
                "passage_text": "Managed production Kubernetes clusters on AWS and automated rollouts.",
                "source_section": "EXPERIENCE",
                "similarity_score": 0.85,
            }],
        )
        citations = MultiLayerEvidenceSynthesizer._deduplicate_citations(b_res, s_res, None)
        self.assertEqual(len(citations), 1)
        self.assertIn("baseline", citations[0].matched_by)
        self.assertIn("semantic", citations[0].matched_by)


class TestConfigurationAndRecordPersistence(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_eval.db"
        self.db = Database(self.db_path)
        self.db.initialize_schema()
        self.config_repo = EvaluationConfigurationRepository(self.db)
        self.record_repo = EvaluationRecordRepository(self.db)

        job_repo = JobRepository(self.db)
        session_repo = SessionRepository(self.db)
        cand_repo = CandidateRepository(self.db)

        job_repo.create(Job(id="job-1", title="Backend Engineer", original_description="Python"))
        session_repo.create(ScreeningSession(id="sess-1", job_id="job-1", session_name="Session 1"))
        cand_repo.create(Candidate(id="cand-1", original_filename="cand.pdf", file_type=FileType.PDF, file_hash="d" * 64, extracted_text="Resume text"))

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_config_versioning_and_retrieval(self):
        cfg_v1 = EvaluationConfiguration(
            id="cfg-1",
            job_id="job-1",
            version="v1.0",
            name="Initial Scoring Config",
            baseline_weight=0.5,
            semantic_weight=0.5,
        )
        self.config_repo.save_config(cfg_v1)

        cfg_v2 = EvaluationConfiguration(
            id="cfg-2",
            job_id="job-1",
            version="v1.1",
            name="Updated Weights Config",
            baseline_weight=0.3,
            semantic_weight=0.7,
        )
        self.config_repo.save_config(cfg_v2)

        latest = self.config_repo.get_latest_for_job("job-1")
        self.assertIsNotNone(latest)
        self.assertEqual(latest.version, "v1.1")

        all_vers = self.config_repo.list_versions_for_job("job-1")
        self.assertEqual(len(all_vers), 2)

    def test_candidate_record_persistence_and_history(self):
        rec1 = CandidateEvaluationRecord(
            candidate_id="cand-1",
            session_id="sess-1",
            config_id="cfg-1",
            config_version="v1.0",
            overall_score=75.0,
            evidence_coverage=80.0,
            evaluation_status="CALCULATED",
        )
        self.record_repo.save_record(rec1)

        rec2 = CandidateEvaluationRecord(
            candidate_id="cand-1",
            session_id="sess-1",
            config_id="cfg-2",
            config_version="v1.1",
            overall_score=85.0,
            evidence_coverage=85.0,
            evaluation_status="CALCULATED",
        )
        self.record_repo.save_record(rec2)

        latest = self.record_repo.get_latest_record("cand-1", "sess-1")
        self.assertIsNotNone(latest)
        self.assertEqual(latest.config_version, "v1.1")
        self.assertEqual(latest.overall_score, 85.0)

        history = self.record_repo.list_record_history("cand-1", "sess-1")
        self.assertEqual(len(history), 2)


class TestMultiLayerCandidateEvaluator(unittest.TestCase):

    def setUp(self):
        self.evaluator = MultiLayerCandidateEvaluator()

    def test_evaluate_candidate_record_and_coverage(self):
        job = Job(id="job-ml", title="Senior Python Cloud Engineer", original_description="Looking for Python and AWS engineer with 4+ years")
        cand = Candidate(
            id="cand-ml",
            original_filename="alex_cloud.pdf",
            file_type=FileType.PDF,
            file_hash="a" * 64,
            extracted_text=(
                "Alex Smith\n"
                "Email: alex@example.com\n\n"
                "PROFESSIONAL SUMMARY\n"
                "Senior Backend Engineer with 5 years experience in Python and AWS.\n\n"
                "SKILLS\n"
                "Python, AWS, FastAPI, Docker, Microservices\n\n"
                "WORK EXPERIENCE\n"
                "Senior Backend Engineer at TechCorp (2019 - 2024)\n"
                "Architected cloud backend services with Python and AWS.\n\n"
                "EDUCATION\n"
                "Bachelor of Science in Computer Science, Tech University (2015 - 2019)\n"
            ),
        )
        criteria = [
            EvaluationCriterion(id="c1", criterion_name="Python Backend", description="Python development", weight=0.4, category=CriterionCategory.TECHNICAL_SKILL),
            EvaluationCriterion(id="c2", criterion_name="Cloud AWS", description="AWS cloud deployment", weight=0.3, category=CriterionCategory.TECHNICAL_SKILL),
            EvaluationCriterion(id="c3", criterion_name="5+ Years Experience", description="5+ years experience", weight=0.3, category=CriterionCategory.EXPERIENCE_DURATION),
        ]
        config = EvaluationConfiguration.create_default(job_id=job.id, criteria=criteria)

        record = self.evaluator.evaluate_candidate_record(
            candidate=cand,
            job=job,
            config=config,
            session_id="sess-100",
        )
        self.assertIsInstance(record, CandidateEvaluationRecord)
        self.assertGreater(record.overall_score, 50.0)
        self.assertGreater(record.evidence_coverage, 50.0)
        self.assertEqual(record.config_version, "v1.0")

        score = self.evaluator.evaluate_to_candidate_score(
            candidate=cand,
            job=job,
            config=config,
            session_id="sess-100",
        )
        self.assertEqual(score.evaluation_mode, "MULTI_LAYER")
        self.assertIn("evidence_coverage", score.criterion_scores)


class TestOrchestratorMultiLayerIntegration(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_orch_ml.db"
        self.db = Database(self.db_path)
        self.db.initialize_schema()
        self.config = AppConfig(storage_dir=Path(self.temp_dir) / "storage", db_path=self.db_path)
        self.orchestrator = ScreeningOrchestrator(self.db, self.config)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_evaluate_session_multi_layer_batch(self):
        job = self.orchestrator.job_repo.create(
            Job(
                title="Senior Fullstack Developer",
                original_description="Seeking a Senior Fullstack Developer with Python, React, and 4+ years experience. Bachelor's degree required.",
            )
        )
        session = self.orchestrator.create_session(job.id, "Multi-Layer Batch Test")

        c1 = Candidate(
            id="cand-good",
            original_filename="good_dev.pdf",
            file_type=FileType.PDF,
            file_hash="b" * 64,
            extracted_text=(
                "Jane Doe\n\n"
                "SKILLS\nPython, React, JavaScript, SQL\n\n"
                "WORK EXPERIENCE\nFull Stack Engineer at WebCorp (2019 - 2024)\n"
                "Built web applications with Python and React.\n\n"
                "EDUCATION\nBachelor of Science in Computer Science\n"
            ),
            processing_status=ProcessingStatus.COMPLETED,
        )
        c2 = Candidate(
            id="cand-conflict",
            original_filename="conflict_dev.pdf",
            file_type=FileType.PDF,
            file_hash="c" * 64,
            extracted_text=(
                "Bob Smith\n\n"
                "SKILLS\nPython, SQL, Linux\n\n"
                "WORK EXPERIENCE\nBackend Engineer at CloudCorp (2020 - 2024)\n"
                "No commercial experience with React. Built APIs with Python.\n\n"
                "EDUCATION\nBachelor of Science in Computer Science\n"
            ),
            processing_status=ProcessingStatus.COMPLETED,
        )
        self.orchestrator.candidate_repo.create(c1)
        self.orchestrator.candidate_repo.create(c2)
        self.orchestrator.candidate_repo.enroll_in_session(candidate_id=c1.id, session_id=session.id, status=ProcessingStatus.COMPLETED)
        self.orchestrator.candidate_repo.enroll_in_session(candidate_id=c2.id, session_id=session.id, status=ProcessingStatus.COMPLETED)

        result = self.orchestrator.evaluate_session_multi_layer(session.id)
        self.assertEqual(result["evaluated_in_chunk"], 2)
        self.assertEqual(result["failed_in_chunk"], 0)
        self.assertGreaterEqual(result["progress_percent"], 100.0)

        records = self.orchestrator.eval_record_repo.list_records_for_session(session.id)
        self.assertEqual(len(records), 2)
        self.assertIn("cand-good", records)
        self.assertIn("cand-conflict", records)


if __name__ == "__main__":
    unittest.main()
