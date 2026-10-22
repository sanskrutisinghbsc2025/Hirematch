
from typing import Dict, List, Optional, Tuple

from core.models.enums import (
    CriterionType,
    MatchStatus,
    MissingEvidencePolicy,
    ScoreCompleteness,
)
from core.models.evaluation import CandidateEvaluationRecord, CriterionEvaluationResult
from core.models.scoring_models import (
    CandidateScoringRecord,
    CriterionContribution,
    RequiredCriteriaSummary,
    ScoringConfiguration,
    ScoringCriterion,
)
from core.utils.logger import logger


class TransparentScoreCalculator:

    def calculate_score(
        self,
        record: CandidateEvaluationRecord,
        config: ScoringConfiguration,
        explanation_text: str = "",
    ) -> CandidateScoringRecord:
        eval_by_id: Dict[str, CriterionEvaluationResult] = {
            r.criterion_id: r for r in record.criterion_results
        }
        eval_by_name: Dict[str, CriterionEvaluationResult] = {
            r.criterion_name.strip().lower(): r for r in record.criterion_results
        }

        contributions: List[CriterionContribution] = []
        warnings: List[str] = list(record.warnings)
        has_unevaluated_enabled = False
        has_missing_evidence_flagged = False

        req_total = 0
        req_supported = 0
        req_partial = 0
        req_not_found = 0
        req_insufficient = 0
        req_conflicting = 0
        req_not_eval = 0
        req_details: Dict[str, str] = {}

        raw_items: List[Tuple[ScoringCriterion, float, bool, Optional[str], MatchStatus, str]] = []
        eligible_weight_sum = 0.0

        for crit in config.criteria:
            eval_res = eval_by_id.get(crit.id) or eval_by_name.get(crit.criterion_name.strip().lower())

            if not crit.is_enabled:
                raw_items.append(
                    (crit, 0.0, False, "Criterion is disabled in configuration", MatchStatus.NOT_EVALUATED, "")
                )
                continue

            is_required = (crit.criterion_type == CriterionType.REQUIRED)
            if is_required:
                req_total += 1

            if eval_res is None or eval_res.match_status == MatchStatus.NOT_EVALUATED:
                has_unevaluated_enabled = True
                if is_required:
                    req_not_eval += 1
                    req_details[crit.criterion_name] = MatchStatus.NOT_EVALUATED.value
                raw_items.append(
                    (crit, 0.0, False, "Criterion has not been evaluated", MatchStatus.NOT_EVALUATED, "")
                )
                continue

            if eval_res.match_status == MatchStatus.CONFLICTING_EVIDENCE:
                if is_required:
                    req_conflicting += 1
                    req_details[crit.criterion_name] = MatchStatus.CONFLICTING_EVIDENCE.value
                warnings.append(f"Criterion '{crit.criterion_name}' has conflicting evidence - 0.0 credit awarded.")
                raw_items.append(
                    (
                        crit,
                        0.0,
                        True,
                        None,
                        MatchStatus.CONFLICTING_EVIDENCE,
                        "Conflicting evidence detected across layers - 0.0 credit awarded pending review.",
                    )
                )
                eligible_weight_sum += crit.weight
                continue

            if eval_res.match_status in (MatchStatus.NOT_FOUND, MatchStatus.INSUFFICIENT_EVIDENCE):
                if eval_res.match_status == MatchStatus.NOT_FOUND:
                    if is_required:
                        req_not_found += 1
                        req_details[crit.criterion_name] = MatchStatus.NOT_FOUND.value
                else:
                    if is_required:
                        req_insufficient += 1
                        req_details[crit.criterion_name] = MatchStatus.INSUFFICIENT_EVIDENCE.value

                policy = crit.missing_evidence_policy
                if policy == MissingEvidencePolicy.EXCLUDE_FROM_CALCULATION:
                    raw_items.append(
                        (
                            crit,
                            0.0,
                            False,
                            "Missing evidence policy excluded criterion from calculation denominator",
                            eval_res.match_status,
                            "Criterion excluded from scoring due to unmentioned evidence.",
                        )
                    )
                elif policy == MissingEvidencePolicy.FLAG_FOR_REVIEW:
                    has_missing_evidence_flagged = True
                    warnings.append(f"Criterion '{crit.criterion_name}' missing evidence and flagged for review.")
                    raw_items.append(
                        (
                            crit,
                            0.0,
                            True,
                            None,
                            eval_res.match_status,
                            "Missing evidence flagged for recruiter review (0.0 points awarded).",
                        )
                    )
                    eligible_weight_sum += crit.weight
                else:
                    raw_items.append(
                        (
                            crit,
                            0.0,
                            True,
                            None,
                            eval_res.match_status,
                            "No verifiable evidence found in resume (0.0 points awarded).",
                        )
                    )
                    eligible_weight_sum += crit.weight
                continue

            raw_s = float(eval_res.score)
            if raw_s > 1.0:
                support_val = max(0.0, min(1.0, raw_s / 100.0))
            else:
                support_val = max(0.0, min(1.0, raw_s))
            if eval_res.match_status == MatchStatus.SUPPORTED:
                if is_required:
                    req_supported += 1
                    req_details[crit.criterion_name] = MatchStatus.SUPPORTED.value
                note_str = "Evidence verified in resume."
            else:
                if is_required:
                    req_partial += 1
                    req_details[crit.criterion_name] = MatchStatus.PARTIALLY_SUPPORTED.value
                note_str = "Partial evidence found."

            raw_items.append((crit, support_val, True, None, eval_res.match_status, note_str))
            eligible_weight_sum += crit.weight

        overall_score: Optional[float] = None
        if eligible_weight_sum > 0.0:
            total_points = 0.0
            for crit, s_val, is_eligible, ex_reason, m_status, note in raw_items:
                if is_eligible:
                    norm_contrib = (crit.weight * s_val / eligible_weight_sum) * 100.0
                    total_points += norm_contrib
                else:
                    norm_contrib = 0.0

                contributions.append(
                    CriterionContribution(
                        criterion_id=crit.id,
                        criterion_name=crit.criterion_name,
                        category=crit.category,
                        criterion_type=crit.criterion_type,
                        configured_weight=crit.weight,
                        support_value=round(s_val, 4),
                        normalized_contribution=round(norm_contrib, 2),
                        match_status=m_status,
                        is_eligible=is_eligible,
                        exclusion_reason=ex_reason,
                        notes=note,
                    )
                )
            overall_score = round(max(0.0, min(100.0, total_points)), 2)
        else:
            for crit, s_val, is_eligible, ex_reason, m_status, note in raw_items:
                contributions.append(
                    CriterionContribution(
                        criterion_id=crit.id,
                        criterion_name=crit.criterion_name,
                        category=crit.category,
                        criterion_type=crit.criterion_type,
                        configured_weight=crit.weight,
                        support_value=0.0,
                        normalized_contribution=0.0,
                        match_status=m_status,
                        is_eligible=False,
                        exclusion_reason=ex_reason or "Zero eligible weight available for scoring",
                        notes=note,
                    )
                )
            warnings.append("No eligible criteria available to calculate an overall score.")

        if overall_score is None or eligible_weight_sum <= 0.0:
            completeness = ScoreCompleteness.INSUFFICIENT_DATA
        elif has_unevaluated_enabled or has_missing_evidence_flagged:
            completeness = ScoreCompleteness.PARTIAL
        else:
            completeness = ScoreCompleteness.COMPLETE

        enabled_criteria_count = sum(1 for c in config.criteria if c.is_enabled)
        positive_evidence_count = sum(
            1 for c in contributions
            if c.is_eligible and c.match_status in (MatchStatus.SUPPORTED, MatchStatus.PARTIALLY_SUPPORTED)
        )
        if enabled_criteria_count > 0:
            evidence_coverage = round((positive_evidence_count / enabled_criteria_count) * 100.0, 1)
        else:
            evidence_coverage = 0.0

        req_summary = RequiredCriteriaSummary(
            total_required=req_total,
            supported_count=req_supported,
            partially_supported_count=req_partial,
            not_found_count=req_not_found,
            insufficient_evidence_count=req_insufficient,
            conflicting_count=req_conflicting,
            not_evaluated_count=req_not_eval,
            details=req_details,
        )

        return CandidateScoringRecord(
            candidate_id=record.candidate_id,
            session_id=record.session_id,
            evaluation_record_id=record.id,
            scoring_config_id=config.id,
            scoring_config_version=config.version,
            overall_score=overall_score,
            evidence_coverage=evidence_coverage,
            completeness_status=completeness,
            criterion_contributions=contributions,
            required_summary=req_summary,
            explanation=explanation_text,
            warnings=warnings,
        )
