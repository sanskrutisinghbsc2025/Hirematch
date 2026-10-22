
import unittest

from core.models.enums import (
    CriterionCategory,
    CriterionType,
    MatchStatus,
    MissingEvidencePolicy,
    RankingSortField,
    ScoreCompleteness,
    TieHandlingStrategy,
)
from core.models.evaluation import CandidateEvaluationRecord, CriterionEvaluationResult
from core.models.scoring_models import (
    CandidateScoringRecord,
    ScoringConfiguration,
    ScoringCriterion,
)
from core.scoring.calculator import TransparentScoreCalculator
from core.scoring.ranker import DeterministicCandidateRanker


class TestScoringRobustnessAndBoundaries(unittest.TestCase):

    def setUp(self):
        self.calculator = TransparentScoreCalculator()
        self.ranker = DeterministicCandidateRanker()

    def test_weight_normalization_over_eligible_criteria(self):
        criteria = [
            ScoringCriterion(
                id="c1",
                criterion_name="Criterion 1",
                weight=0.1,
                criterion_type=CriterionType.REQUIRED,
            ),
            ScoringCriterion(
                id="c2",
                criterion_name="Criterion 2",
                weight=0.3,
                criterion_type=CriterionType.PREFERRED,
            ),
        ]
        cfg = ScoringConfiguration(job_id="job-1", version="v1.0", criteria=criteria)

        eval_record = CandidateEvaluationRecord(
            candidate_id="cand-1",
            session_id="sess-1",
            config_id="cfg-1",
            config_version="v1.0",
            overall_score=0.0,
            evidence_coverage=0.0,
            criterion_results=[
                CriterionEvaluationResult(
                    criterion_id="c1",
                    criterion_name="Criterion 1",
                    criterion_type=CriterionType.REQUIRED,
                    weight=0.1,
                    match_status=MatchStatus.SUPPORTED,
                    score=1.0,
                ),
                CriterionEvaluationResult(
                    criterion_id="c2",
                    criterion_name="Criterion 2",
                    criterion_type=CriterionType.PREFERRED,
                    weight=0.3,
                    match_status=MatchStatus.SUPPORTED,
                    score=1.0,
                ),
            ],
        )

        score_rec = self.calculator.calculate_score(eval_record, cfg)
        self.assertEqual(score_rec.overall_score, 100.0)

        contribs = {c.criterion_id: c.normalized_contribution for c in score_rec.criterion_contributions}
        self.assertEqual(contribs["c1"], 25.0)
        self.assertEqual(contribs["c2"], 75.0)

    def test_invalid_weight_boundaries_rejected(self):
        with self.assertRaises(ValueError):
            ScoringCriterion(id="c1", criterion_name="C1", weight=-0.1)

        with self.assertRaises(ValueError):
            ScoringCriterion(id="c1", criterion_name="C1", weight=1.2)

    def test_empty_criteria_and_all_disabled_configuration(self):
        cfg_empty = ScoringConfiguration(job_id="job-1", version="v1.0", criteria=[])
        errors = cfg_empty.validate_configuration()
        self.assertTrue(any("at least one" in e.lower() for e in errors))

        disabled_crit = ScoringCriterion(id="c1", criterion_name="C1", weight=0.5, is_enabled=False)
        cfg_disabled = ScoringConfiguration(job_id="job-1", version="v1.0", criteria=[disabled_crit])

        eval_record = CandidateEvaluationRecord(
            candidate_id="cand-1",
            session_id="sess-1",
            config_id="cfg-1",
            config_version="v1.0",
            overall_score=0.0,
            evidence_coverage=0.0,
            criterion_results=[],
        )
        score_rec = self.calculator.calculate_score(eval_record, cfg_disabled)
        self.assertIsNone(score_rec.overall_score)
        self.assertEqual(score_rec.completeness_status, ScoreCompleteness.INSUFFICIENT_DATA)

    def test_required_vs_optional_criteria_summary(self):
        criteria = [
            ScoringCriterion(id="c1", criterion_name="Req 1", weight=0.5, criterion_type=CriterionType.REQUIRED),
            ScoringCriterion(id="c2", criterion_name="Pref 1", weight=0.5, criterion_type=CriterionType.PREFERRED),
        ]
        cfg = ScoringConfiguration(job_id="job-1", version="v1.0", criteria=criteria)

        eval_record = CandidateEvaluationRecord(
            candidate_id="cand-1",
            session_id="sess-1",
            config_id="cfg-1",
            config_version="v1.0",
            overall_score=0.0,
            evidence_coverage=0.0,
            criterion_results=[
                CriterionEvaluationResult(
                    criterion_id="c1",
                    criterion_name="Req 1",
                    criterion_type=CriterionType.REQUIRED,
                    weight=0.5,
                    match_status=MatchStatus.NOT_FOUND,
                    score=0.0,
                ),
                CriterionEvaluationResult(
                    criterion_id="c2",
                    criterion_name="Pref 1",
                    criterion_type=CriterionType.PREFERRED,
                    weight=0.5,
                    match_status=MatchStatus.SUPPORTED,
                    score=1.0,
                ),
            ],
        )

        score_rec = self.calculator.calculate_score(eval_record, cfg)
        self.assertFalse(score_rec.required_summary.all_satisfied)
        self.assertEqual(score_rec.required_summary.total_required, 1)
        self.assertEqual(score_rec.required_summary.supported_count, 0)
        self.assertIn("Req 1", score_rec.required_summary.details)

    def test_missing_evidence_policies(self):
        crit_exclude = ScoringCriterion(
            id="c1",
            criterion_name="Optional Cloud Skill",
            weight=0.4,
            criterion_type=CriterionType.PREFERRED,
            missing_evidence_policy=MissingEvidencePolicy.EXCLUDE_FROM_CALCULATION,
        )
        crit_standard = ScoringCriterion(
            id="c2",
            criterion_name="Core Python",
            weight=0.6,
            criterion_type=CriterionType.REQUIRED,
        )
        cfg = ScoringConfiguration(job_id="job-1", version="v1.0", criteria=[crit_exclude, crit_standard])

        eval_rec = CandidateEvaluationRecord(
            candidate_id="cand-1",
            session_id="sess-1",
            config_id="cfg-1",
            config_version="v1.0",
            overall_score=0.0,
            evidence_coverage=0.0,
            criterion_results=[
                CriterionEvaluationResult(
                    criterion_id="c1",
                    criterion_name="Optional Cloud Skill",
                    criterion_type=CriterionType.PREFERRED,
                    weight=0.4,
                    match_status=MatchStatus.NOT_FOUND,
                    score=0.0,
                ),
                CriterionEvaluationResult(
                    criterion_id="c2",
                    criterion_name="Core Python",
                    criterion_type=CriterionType.REQUIRED,
                    weight=0.6,
                    match_status=MatchStatus.SUPPORTED,
                    score=1.0,
                ),
            ],
        )

        score_rec = self.calculator.calculate_score(eval_rec, cfg)
        self.assertEqual(score_rec.overall_score, 100.0)

    def test_deterministic_ranking_and_tie_strategies(self):
        from core.models.scoring_models import CandidateScoringRecord, RequiredCriteriaSummary

        records = [
            CandidateScoringRecord(
                id="rec-b",
                candidate_id="cand-b",
                session_id="sess-1",
                evaluation_record_id="eval-b",
                scoring_config_id="cfg-1",
                scoring_config_version="v1.0",
                overall_score=80.0,
                evidence_coverage=75.0,
                completeness_status=ScoreCompleteness.COMPLETE,
                required_summary=RequiredCriteriaSummary(total_required=1, supported_count=1),
            ),
            CandidateScoringRecord(
                id="rec-a",
                candidate_id="cand-a",
                session_id="sess-1",
                evaluation_record_id="eval-a",
                scoring_config_id="cfg-1",
                scoring_config_version="v1.0",
                overall_score=80.0,
                evidence_coverage=90.0,
                completeness_status=ScoreCompleteness.COMPLETE,
                required_summary=RequiredCriteriaSummary(total_required=1, supported_count=1),
            ),
            CandidateScoringRecord(
                id="rec-c",
                candidate_id="cand-c",
                session_id="sess-1",
                evaluation_record_id="eval-c",
                scoring_config_id="cfg-1",
                scoring_config_version="v1.0",
                overall_score=70.0,
                evidence_coverage=60.0,
                completeness_status=ScoreCompleteness.COMPLETE,
                required_summary=RequiredCriteriaSummary(total_required=1, supported_count=1),
            ),
        ]

        cfg = ScoringConfiguration(
            job_id="job-1",
            version="v1.0",
            tie_strategy=TieHandlingStrategy.STANDARD_COMPETITION,
            secondary_sort=RankingSortField.EVIDENCE_COVERAGE,
        )

        ranked_1 = self.ranker.rank_candidates(records, cfg)
        order_1 = [r.candidate_id for r in ranked_1]

        shuffled = [records[1], records[2], records[0]]
        ranked_2 = self.ranker.rank_candidates(shuffled, cfg)
        order_2 = [r.candidate_id for r in ranked_2]

        self.assertEqual(order_1, order_2)
        self.assertEqual(order_1[0], "cand-a")
        self.assertEqual(order_1[1], "cand-b")
        self.assertEqual(order_1[2], "cand-c")


if __name__ == "__main__":
    unittest.main()
