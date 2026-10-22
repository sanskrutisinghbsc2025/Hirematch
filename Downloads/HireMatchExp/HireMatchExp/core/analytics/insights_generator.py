
from typing import Any, Dict, List, Optional
import numpy as np

from core.analytics.models import (
    CriterionAnalytics,
    InsightCategory,
    InsightSeverity,
    SkillCoverageItem,
    TraceableInsight,
)
from core.storage.database import Database
from core.storage.scoring_repository import ScoringRecordRepository
from core.utils.logger import logger


class TraceableInsightsGenerator:

    def __init__(self, db: Database):
        self.db = db
        self.scoring_repo = ScoringRecordRepository(db)

    def generate_insights(
        self,
        session_id: str,
        criterion_analytics: List[CriterionAnalytics],
        skill_coverage: List[SkillCoverageItem],
        total_enrolled: int,
        failed_count: int,
        valid_scores: List[float],
    ) -> List[TraceableInsight]:
        insights: List[TraceableInsight] = []

        if total_enrolled > 0 and failed_count > 0:
            fail_rate = round((failed_count / total_enrolled) * 100.0, 1)
            severity = InsightSeverity.CRITICAL if fail_rate >= 15.0 else InsightSeverity.WARNING
            insights.append(
                TraceableInsight(
                    category=InsightCategory.PROCESSING_BOTTLENECK,
                    severity=severity,
                    title="Processing Failures Affecting Screening Pool",
                    description=(
                        f"{failed_count} of {total_enrolled} enrolled resumes ({fail_rate}%) failed text extraction. "
                        f"These candidates are omitted from scoring and ranking until retried."
                    ),
                    calculation_basis=f"failed_resumes / total_enrolled = {failed_count}/{total_enrolled} ({fail_rate}%) > 0%",
                    affected_criteria=[],
                    metric_value=fail_rate,
                    benchmark_threshold=10.0,
                    suggested_recruiter_action="Navigate to the Workspace tab and click 'Retry Failed Resumes' to re-extract documents.",
                )
            )

        if len(valid_scores) >= 5:
            q25 = float(np.percentile(valid_scores, 25))
            q75 = float(np.percentile(valid_scores, 75))
            iqr = round(q75 - q25, 2)
            if iqr < 12.0:
                insights.append(
                    TraceableInsight(
                        category=InsightCategory.CLUSTERED_SCORES,
                        severity=InsightSeverity.WARNING,
                        title="Tightly Clustered Candidate Scores",
                        description=(
                            f"The middle 50% of the applicant pool spans only {iqr:.1f} score points (Q1: {q25:.1f}%, Q3: {q75:.1f}%). "
                            f"Candidates are closely grouped, making ranking highly sensitive to small point differences."
                        ),
                        calculation_basis=f"Interquartile Range (IQR) = Q3 ({q75:.1f}) - Q1 ({q25:.1f}) = {iqr:.1f} < 12.0 pts",
                        affected_criteria=[],
                        metric_value=iqr,
                        benchmark_threshold=12.0,
                        suggested_recruiter_action="Review criterion weights in the Sensitivity Simulator or add distinguishing preferred criteria to spread candidate evaluations.",
                    )
                )

        for ca in criterion_analytics:
            if ca.is_low_variation:
                insights.append(
                    TraceableInsight(
                        category=InsightCategory.LOW_SCORE_VARIATION,
                        severity=InsightSeverity.INFO,
                        title=f"Low Score Variation for '{ca.criterion_name}'",
                        description=(
                            f"Requirement '{ca.criterion_name}' produces very little differentiation across the pool "
                            f"(Standard Deviation \u03c3 = {ca.std_dev:.3f}, mean support = {ca.mean_support_value:.2f}). "
                            f"Nearly all candidates receive nearly identical points for this requirement."
                        ),
                        calculation_basis=f"Standard Deviation \u03c3 = {ca.std_dev:.3f} < 0.08 threshold across N={ca.total_evaluated} candidates",
                        affected_criteria=[ca.criterion_name],
                        metric_value=ca.std_dev,
                        benchmark_threshold=0.08,
                        suggested_recruiter_action="Verify whether this requirement is a universal baseline skill that can be given a lower weight, allowing distinguishing skills to guide rankings.",
                    )
                )

        for ca in criterion_analytics:
            if ca.insufficient_rate >= 75.0 and ca.total_evaluated >= 3:
                insights.append(
                    TraceableInsight(
                        category=InsightCategory.HIGH_EVALUATION_DIFFICULTY,
                        severity=InsightSeverity.WARNING,
                        title=f"High Evaluation Difficulty for '{ca.criterion_name}'",
                        description=(
                            f"{ca.insufficient_rate:.1f}% of candidates ({ca.insufficient_evidence_count} of {ca.total_evaluated}) "
                            f"have insufficient or unmentioned evidence for '{ca.criterion_name}'. "
                            f"This requirement may be rarely documented on resumes or difficult to capture textually."
                        ),
                        calculation_basis=f"insufficient_rate = {ca.insufficient_rate:.1f}% >= 75.0% across N={ca.total_evaluated} candidates",
                        affected_criteria=[ca.criterion_name],
                        metric_value=ca.insufficient_rate,
                        benchmark_threshold=75.0,
                        suggested_recruiter_action="Consider assessing this requirement during initial recruiter phone screens rather than using it as a strict resume screening filter.",
                    )
                )
            elif ca.insufficient_rate >= 60.0 and ca.total_evaluated >= 3:
                insights.append(
                    TraceableInsight(
                        category=InsightCategory.ACUTE_SKILL_GAP,
                        severity=InsightSeverity.INFO,
                        title=f"Acute Talent Pool Gap: '{ca.criterion_name}'",
                        description=(
                            f"{ca.insufficient_rate:.1f}% of evaluated candidates have no verified evidence for '{ca.criterion_name}'. "
                            f"This skill represents a significant deficit in the current applicant pool."
                        ),
                        calculation_basis=f"insufficient_rate = {ca.insufficient_rate:.1f}% >= 60.0% across N={ca.total_evaluated} candidates",
                        affected_criteria=[ca.criterion_name],
                        metric_value=ca.insufficient_rate,
                        benchmark_threshold=60.0,
                        suggested_recruiter_action="Review whether missing evidence policy should be set to EXCLUDE_FROM_CALCULATION if this is not a strict day-one blocker.",
                    )
                )

        for ca in criterion_analytics:
            if ca.semantic_boost_count >= 2:
                boost_pct = round((ca.semantic_boost_count / max(1, ca.total_evaluated)) * 100.0, 1)
                insights.append(
                    TraceableInsight(
                        category=InsightCategory.SEMANTIC_DISCOVERY,
                        severity=InsightSeverity.INFO,
                        title=f"Semantic AI Discovered Conceptual Evidence for '{ca.criterion_name}'",
                        description=(
                            f"Pretrained dense embeddings identified conceptual evidence for {ca.semantic_boost_count} candidates ({boost_pct}%) "
                            f"where exact keyword matching found no verbatim mention. Candidates used equivalent terminology or related project descriptions."
                        ),
                        calculation_basis=f"semantic_score >= baseline_score + 0.30 for {ca.semantic_boost_count} candidates",
                        affected_criteria=[ca.criterion_name],
                        metric_value=float(ca.semantic_boost_count),
                        benchmark_threshold=2.0,
                        suggested_recruiter_action="Inspect the Multi-Layer Evidence Breakdown in the candidate profile to verify contextual matches.",
                    )
                )

        severity_order = {
            InsightSeverity.CRITICAL: 0,
            InsightSeverity.WARNING: 1,
            InsightSeverity.INFO: 2,
        }
        insights.sort(key=lambda x: severity_order.get(x.severity, 3))
        return insights
