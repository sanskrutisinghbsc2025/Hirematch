
from datetime import datetime, timezone
import tempfile
import unittest
from pathlib import Path

from core.models.candidate import Candidate
from core.models.enums import (
    CriterionCategory,
    CriterionType,
    FileType,
    MatchStatus,
    MissingEvidencePolicy,
    RankingSortField,
    ScoreCompleteness,
    ShortlistReviewStatus,
    TieHandlingStrategy,
)
from core.models.evaluation import CandidateEvaluationRecord, CriterionEvaluationResult
from core.models.job import Job
from core.models.session import ScreeningSession
from core.models.scoring_models import (
    CandidateScoringRecord,
    ScoringConfiguration,
    ScoringCriterion,
    ShortlistRecord,
)
from core.scoring.calculator import TransparentScoreCalculator
from core.scoring.explanation import ScoreExplanationGenerator
from core.scoring.ranker import DeterministicCandidateRanker
from core.scoring.scoring_service import ScoringService
from core.scoring.shortlist_service import ShortlistService
from core.scoring.simulator import RankingSensitivitySimulator
from core.storage.database import Database
from core.storage.eval_repository import EvaluationRecordRepository
from core.storage.repositories import CandidateRepository, JobRepository, SessionRepository
from core.storage.scoring_repository import ScoringRecordRepository
from core.storage.shortlist_repository import ShortlistRepository


class TestTransparentScoreCalculator(unittest.TestCase):

    def setUp(self):
        self.calculator = TransparentScoreCalculator()

    def test_formula_correctness_with_worked_synthetic_case(self):
        c1 = ScoringCriterion(id="crit_1", criterion_name="Python", weight=0.4, criterion_type=CriterionType.REQUIRED)
        c2 = ScoringCriterion(id="crit_2", criterion_name="AWS", weight=0.3, criterion_type=CriterionType.PREFERRED)
        c3 = ScoringCriterion(id="crit_3", criterion_name="Degree", weight=0.3, criterion_type=CriterionType.REQUIRED, missing_evidence_policy=MissingEvidencePolicy.ZERO_CREDIT)

        config = ScoringConfiguration(job_id="job_test", criteria=[c1, c2, c3])

        r1 = CriterionEvaluationResult(criterion_id="crit_1", criterion_name="Python", criterion_type=CriterionType.REQUIRED, weight=0.4, match_status=MatchStatus.SUPPORTED, score=1.0)
        r2 = CriterionEvaluationResult(criterion_id="crit_2", criterion_name="AWS", criterion_type=CriterionType.PREFERRED, weight=0.3, match_status=MatchStatus.PARTIALLY_SUPPORTED, score=0.5)
        r3 = CriterionEvaluationResult(criterion_id="crit_3", criterion_name="Degree", criterion_type=CriterionType.REQUIRED, weight=0.3, match_status=MatchStatus.NOT_FOUND, score=0.0)

        eval_rec = CandidateEvaluationRecord(
            candidate_id="cand_1", session_id="sess_1", config_id="cfg_1",
            config_version="v1.0", overall_score=0.0, evidence_coverage=0.0,
            evaluation_status="EVALUATED", criterion_results=[r1, r2, r3]
        )

        score_rec = self.calculator.calculate_score(eval_rec, config)

        self.assertIsNotNone(score_rec.overall_score)
        self.assertAlmostEqual(score_rec.overall_score, 55.0, places=1)
        self.assertAlmostEqual(score_rec.evidence_coverage, 66.7, places=1)
        self.assertEqual(score_rec.completeness_status, ScoreCompleteness.COMPLETE)

    def test_missing_evidence_exclude_policy(self):
        c1 = ScoringCriterion(id="crit_1", criterion_name="Python", weight=0.6)
        c2 = ScoringCriterion(
            id="crit_2", criterion_name="Kubernetes", weight=0.4,
            missing_evidence_policy=MissingEvidencePolicy.EXCLUDE_FROM_CALCULATION
        )
        config = ScoringConfiguration(job_id="job_test", criteria=[c1, c2])

        r1 = CriterionEvaluationResult(criterion_id="crit_1", criterion_name="Python", criterion_type=CriterionType.REQUIRED, weight=0.6, match_status=MatchStatus.SUPPORTED, score=1.0)
        r2 = CriterionEvaluationResult(criterion_id="crit_2", criterion_name="Kubernetes", criterion_type=CriterionType.REQUIRED, weight=0.4, match_status=MatchStatus.NOT_FOUND, score=0.0)

        eval_rec = CandidateEvaluationRecord(
            candidate_id="cand_1", session_id="sess_1", config_id="cfg_1",
            config_version="v1.0", overall_score=0.0, evidence_coverage=0.0,
            evaluation_status="EVALUATED", criterion_results=[r1, r2]
        )

        score_rec = self.calculator.calculate_score(eval_rec, config)
        self.assertAlmostEqual(score_rec.overall_score, 100.0, places=1)
        k8s_contrib = next(c for c in score_rec.criterion_contributions if c.criterion_id == "crit_2")
        self.assertFalse(k8s_contrib.is_eligible)
        self.assertIn("excluded", k8s_contrib.exclusion_reason.lower())

    def test_conflicting_evidence_zero_points_no_average(self):
        c1 = ScoringCriterion(id="crit_1", criterion_name="Python", weight=0.5)
        c2 = ScoringCriterion(id="crit_2", criterion_name="React", weight=0.5)
        config = ScoringConfiguration(job_id="job_test", criteria=[c1, c2])

        r1 = CriterionEvaluationResult(criterion_id="crit_1", criterion_name="Python", criterion_type=CriterionType.REQUIRED, weight=0.5, match_status=MatchStatus.SUPPORTED, score=1.0)
        r2 = CriterionEvaluationResult(criterion_id="crit_2", criterion_name="React", criterion_type=CriterionType.REQUIRED, weight=0.5, match_status=MatchStatus.CONFLICTING_EVIDENCE, score=0.0)

        eval_rec = CandidateEvaluationRecord(
            candidate_id="cand_1", session_id="sess_1", config_id="cfg_1",
            config_version="v1.0", overall_score=0.0, evidence_coverage=0.0,
            evaluation_status="EVALUATED", criterion_results=[r1, r2]
        )

        score_rec = self.calculator.calculate_score(eval_rec, config)
        self.assertAlmostEqual(score_rec.overall_score, 50.0, places=1)
        self.assertTrue(any("conflicting" in w.lower() for w in score_rec.warnings))

    def test_insufficient_data_yields_unavailable_score(self):
        c1 = ScoringCriterion(id="crit_1", criterion_name="Python", weight=0.5, is_enabled=False)
        config = ScoringConfiguration(job_id="job_test", criteria=[c1])

        eval_rec = CandidateEvaluationRecord(
            candidate_id="cand_1", session_id="sess_1", config_id="cfg_1",
            config_version="v1.0", overall_score=0.0, evidence_coverage=0.0,
            evaluation_status="EVALUATED", criterion_results=[]
        )

        score_rec = self.calculator.calculate_score(eval_rec, config)
        self.assertIsNone(score_rec.overall_score)
        self.assertEqual(score_rec.completeness_status, ScoreCompleteness.INSUFFICIENT_DATA)


class TestDeterministicCandidateRanker(unittest.TestCase):

    def setUp(self):
        self.ranker = DeterministicCandidateRanker()
        self.c1 = ScoringCriterion(id="crit_1", criterion_name="Python", weight=1.0)
        self.config = ScoringConfiguration(
            job_id="job_test",
            criteria=[self.c1],
            tie_strategy=TieHandlingStrategy.STANDARD_COMPETITION,
            secondary_sort=RankingSortField.EVIDENCE_COVERAGE,
        )

    def test_standard_competition_tie_handling(self):
        rA = CandidateScoringRecord(candidate_id="cA", session_id="s", evaluation_record_id="e", scoring_config_id="c", scoring_config_version="v1", overall_score=90.0, evidence_coverage=80.0, completeness_status=ScoreCompleteness.COMPLETE)
        rB = CandidateScoringRecord(candidate_id="cB", session_id="s", evaluation_record_id="e", scoring_config_id="c", scoring_config_version="v1", overall_score=85.0, evidence_coverage=70.0, completeness_status=ScoreCompleteness.COMPLETE)
        rC = CandidateScoringRecord(candidate_id="cC", session_id="s", evaluation_record_id="e", scoring_config_id="c", scoring_config_version="v1", overall_score=85.0, evidence_coverage=70.0, completeness_status=ScoreCompleteness.COMPLETE)
        rD = CandidateScoringRecord(candidate_id="cD", session_id="s", evaluation_record_id="e", scoring_config_id="c", scoring_config_version="v1", overall_score=75.0, evidence_coverage=60.0, completeness_status=ScoreCompleteness.COMPLETE)

        meta = {
            "cA": ("Alice", "alice.pdf"),
            "cB": ("Bob", "bob.pdf"),
            "cC": ("Charlie", "charlie.pdf"),
            "cD": ("David", "david.pdf"),
        }

        ranked = self.ranker.rank_candidates([rA, rB, rC, rD], self.config, meta)

        ranks = {c.candidate_id: (c.rank, c.is_tied) for c in ranked}
        self.assertEqual(ranks["cA"], (1, False))
        self.assertEqual(ranks["cB"][0], 2)
        self.assertTrue(ranks["cB"][1])
        self.assertEqual(ranks["cC"][0], 2)
        self.assertTrue(ranks["cC"][1])
        self.assertEqual(ranks["cD"], (4, False))

    def test_dense_tie_handling(self):
        self.config.tie_strategy = TieHandlingStrategy.DENSE

        rA = CandidateScoringRecord(candidate_id="cA", session_id="s", evaluation_record_id="e", scoring_config_id="c", scoring_config_version="v1", overall_score=90.0, evidence_coverage=80.0, completeness_status=ScoreCompleteness.COMPLETE)
        rB = CandidateScoringRecord(candidate_id="cB", session_id="s", evaluation_record_id="e", scoring_config_id="c", scoring_config_version="v1", overall_score=85.0, evidence_coverage=70.0, completeness_status=ScoreCompleteness.COMPLETE)
        rC = CandidateScoringRecord(candidate_id="cC", session_id="s", evaluation_record_id="e", scoring_config_id="c", scoring_config_version="v1", overall_score=85.0, evidence_coverage=70.0, completeness_status=ScoreCompleteness.COMPLETE)
        rD = CandidateScoringRecord(candidate_id="cD", session_id="s", evaluation_record_id="e", scoring_config_id="c", scoring_config_version="v1", overall_score=75.0, evidence_coverage=60.0, completeness_status=ScoreCompleteness.COMPLETE)

        meta = {"cA": ("Alice", "a.pdf"), "cB": ("Bob", "b.pdf"), "cC": ("Charlie", "c.pdf"), "cD": ("David", "d.pdf")}
        ranked = self.ranker.rank_candidates([rA, rB, rC, rD], self.config, meta)

        ranks = {c.candidate_id: c.rank for c in ranked}
        self.assertEqual(ranks["cA"], 1)
        self.assertEqual(ranks["cB"], 2)
        self.assertEqual(ranks["cC"], 2)
        self.assertEqual(ranks["cD"], 3)

    def test_incomplete_candidate_isolation(self):
        rA = CandidateScoringRecord(candidate_id="cA", session_id="s", evaluation_record_id="e", scoring_config_id="c", scoring_config_version="v1", overall_score=95.0, evidence_coverage=90.0, completeness_status=ScoreCompleteness.COMPLETE)
        rIncomplete = CandidateScoringRecord(candidate_id="cInc", session_id="s", evaluation_record_id="e", scoring_config_id="c", scoring_config_version="v1", overall_score=None, evidence_coverage=0.0, completeness_status=ScoreCompleteness.INSUFFICIENT_DATA)

        meta = {"cA": ("Alice", "a.pdf"), "cInc": ("Inc", "inc.pdf")}
        ranked = self.ranker.rank_candidates([rA, rIncomplete], self.config, meta)

        self.assertEqual(len(ranked), 2)
        self.assertEqual(ranked[0].candidate_id, "cA")
        self.assertEqual(ranked[0].rank, 1)
        self.assertEqual(ranked[1].candidate_id, "cInc")
        self.assertEqual(ranked[1].rank, 0)
        self.assertEqual(ranked[1].completeness_status, ScoreCompleteness.INSUFFICIENT_DATA)


class TestShortlistServiceAndReviewWorkflow(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_sl.db"
        self.db = Database(self.db_path)
        self.db.initialize_schema()

        self.job_repo = JobRepository(self.db)
        self.sess_repo = SessionRepository(self.db)
        self.cand_repo = CandidateRepository(self.db)

        job_obj = Job(
            title="Software Engineer",
            department="Engineering",
            original_description="Python developer job description",
            parsed_requirements={"skills": ["Python"]},
        )
        job = self.job_repo.create(job_obj)
        sess_obj = ScreeningSession(job_id=job.id, session_name="Batch 1", max_resume_count=100)
        self.session = self.sess_repo.create(sess_obj)
        self.cand = self.cand_repo.create(
            Candidate(original_filename="resume_test.pdf", file_type=FileType.PDF, file_hash="a" * 64)
        )
        self.cand_repo.enroll_in_session(self.cand.id, self.session.id)

        self.shortlist_repo = ShortlistRepository(self.db)
        self.shortlist_service = ShortlistService(self.shortlist_repo)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_shortlist_state_lifecycle(self):
        rec = self.shortlist_service.set_review_status(
            session_id=self.session.id,
            candidate_id=self.cand.id,
            status=ShortlistReviewStatus.NEEDS_REVIEW,
            reviewer_notes="Strong Python experience, check cloud background.",
        )
        self.assertEqual(rec.review_status, ShortlistReviewStatus.NEEDS_REVIEW)
        self.assertEqual(rec.reviewer_notes, "Strong Python experience, check cloud background.")

        rec2 = self.shortlist_service.set_review_status(
            session_id=self.session.id,
            candidate_id=self.cand.id,
            status=ShortlistReviewStatus.SHORTLISTED,
            reviewer_notes="Approved for technical interview.",
        )
        self.assertEqual(rec2.review_status, ShortlistReviewStatus.SHORTLISTED)

        fetched = self.shortlist_service.get_candidate_shortlist_entry(self.session.id, self.cand.id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.review_status, ShortlistReviewStatus.SHORTLISTED)

        deleted = self.shortlist_service.remove_from_shortlist(self.session.id, self.cand.id)
        self.assertTrue(deleted)
        self.assertIsNone(self.shortlist_service.get_candidate_shortlist_entry(self.session.id, self.cand.id))


class TestRankingSensitivitySimulator(unittest.TestCase):

    def setUp(self):
        self.simulator = RankingSensitivitySimulator()
        self.c1 = ScoringCriterion(id="crit_py", criterion_name="Python", weight=0.7)
        self.c2 = ScoringCriterion(id="crit_sql", criterion_name="SQL", weight=0.3)
        self.base_config = ScoringConfiguration(job_id="job_test", criteria=[self.c1, self.c2])

        rA1 = CriterionEvaluationResult(criterion_id="crit_py", criterion_name="Python", criterion_type=CriterionType.REQUIRED, weight=0.7, match_status=MatchStatus.SUPPORTED, score=1.0)
        rA2 = CriterionEvaluationResult(criterion_id="crit_sql", criterion_name="SQL", criterion_type=CriterionType.REQUIRED, weight=0.3, match_status=MatchStatus.PARTIALLY_SUPPORTED, score=0.2)
        self.recA = CandidateEvaluationRecord(
            candidate_id="cand_A", session_id="s", config_id="c", config_version="v1",
            overall_score=0.0, evidence_coverage=0.0, evaluation_status="EVALUATED",
            criterion_results=[rA1, rA2]
        )

        rB1 = CriterionEvaluationResult(criterion_id="crit_py", criterion_name="Python", criterion_type=CriterionType.REQUIRED, weight=0.7, match_status=MatchStatus.PARTIALLY_SUPPORTED, score=0.3)
        rB2 = CriterionEvaluationResult(criterion_id="crit_sql", criterion_name="SQL", criterion_type=CriterionType.REQUIRED, weight=0.3, match_status=MatchStatus.SUPPORTED, score=1.0)
        self.recB = CandidateEvaluationRecord(
            candidate_id="cand_B", session_id="s", config_id="c", config_version="v1",
            overall_score=0.0, evidence_coverage=0.0, evaluation_status="EVALUATED",
            criterion_results=[rB1, rB2]
        )

    def test_weight_shift_reorders_candidates(self):
        new_weights = {"crit_py": 0.1, "crit_sql": 0.9}
        meta = {"cand_A": ("Alice", "a.pdf"), "cand_B": ("Bob", "b.pdf")}

        res = self.simulator.simulate_weight_changes(
            base_config=self.base_config,
            evaluation_records=[self.recA, self.recB],
            new_weights=new_weights,
            candidate_meta=meta,
        )

        self.assertTrue(res["success"])
        self.assertEqual(res["rank_changers_count"], 2)

        cands = {c["candidate_id"]: c for c in res["simulated_candidates"]}
        self.assertEqual(cands["cand_B"]["simulated_rank"], 1)
        self.assertEqual(cands["cand_B"]["original_rank"], 2)
        self.assertEqual(cands["cand_B"]["rank_delta"], 1)

        self.assertEqual(cands["cand_A"]["simulated_rank"], 2)
        self.assertEqual(cands["cand_A"]["original_rank"], 1)
        self.assertEqual(cands["cand_A"]["rank_delta"], -1)


class Test100ResumePerformanceAndEndToEnd(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_perf.db"
        self.db = Database(self.db_path)
        self.db.initialize_schema()

        self.job_repo = JobRepository(self.db)
        self.sess_repo = SessionRepository(self.db)
        self.cand_repo = CandidateRepository(self.db)
        self.eval_record_repo = EvaluationRecordRepository(self.db)
        self.scoring_service = ScoringService(self.db)

        job_obj = Job(
            title="Scale Test Job",
            department="IT",
            original_description="Python Cloud SQL scale test",
            parsed_requirements={"skills": ["Python", "Cloud", "SQL"]},
        )
        self.job = self.job_repo.create(job_obj)
        sess_obj = ScreeningSession(job_id=self.job.id, session_name="100 Resumes Test", max_resume_count=100)
        self.session = self.sess_repo.create(sess_obj)

        eval_records = []
        for i in range(100):
            cand_obj = Candidate(
                original_filename=f"candidate_{i:03d}.pdf",
                file_type=FileType.PDF,
                file_hash=f"{i:03d}".ljust(64, "0"),
            )
            cand = self.cand_repo.create(cand_obj)
            self.cand_repo.enroll_in_session(cand.id, self.session.id)

            r1 = CriterionEvaluationResult(criterion_id="crit_1", criterion_name="Python", criterion_type=CriterionType.REQUIRED, weight=0.4, match_status=MatchStatus.SUPPORTED if (i % 10) > 0 else MatchStatus.NOT_FOUND, score=(i % 10) / 10.0)
            r2 = CriterionEvaluationResult(criterion_id="crit_2", criterion_name="Cloud", criterion_type=CriterionType.REQUIRED, weight=0.3, match_status=MatchStatus.PARTIALLY_SUPPORTED, score=((i + 3) % 10) / 10.0)
            r3 = CriterionEvaluationResult(criterion_id="crit_3", criterion_name="SQL", criterion_type=CriterionType.REQUIRED, weight=0.3, match_status=MatchStatus.SUPPORTED, score=((i + 7) % 10) / 10.0)

            eval_rec = CandidateEvaluationRecord(
                candidate_id=cand.id,
                session_id=self.session.id,
                config_id="perf_cfg",
                config_version="v1.0",
                overall_score=50.0,
                evidence_coverage=66.7,
                evaluation_status="EVALUATED",
                criterion_results=[r1, r2, r3]
            )
            eval_records.append(eval_rec)

        self.eval_record_repo.save_batch(eval_records)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_score_and_rank_100_resumes_subsecond(self):
        import time
        start_time = time.time()

        res = self.scoring_service.score_session(self.session.id)

        duration = time.time() - start_time

        self.assertEqual(res["total_evaluated"], 100)
        self.assertEqual(res["scored_count"], 100)
        self.assertEqual(len(res["ranked_candidates"]), 100)
        top_cand = res["ranked_candidates"][0]
        self.assertEqual(top_cand.rank, 1)
        self.assertIsNotNone(top_cand.overall_score)

        self.assertLess(duration, 5.0, f"100 resumes took {duration:.3f}s, expected < 5.0s")


if __name__ == "__main__":
    unittest.main()
