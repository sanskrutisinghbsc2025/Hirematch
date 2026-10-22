
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.evaluation.interfaces import IScoringService
from core.models.candidate import Candidate
from core.models.enums import CriterionType, MatchStatus, ScoreStatus
from core.models.evaluation import (
    CandidateScore,
    CriterionEvaluationResult,
    EvaluationCriterion,
    EvaluationEvidence,
)


class TransparentScoringEngine(IScoringService):

    DEFAULT_CONFIG_VERSION = "v1.0-baseline"

    def __init__(self, config_version: str = DEFAULT_CONFIG_VERSION):
        self.config_version = config_version

    def calculate_score(
        self,
        candidate: Candidate,
        criteria: List[EvaluationCriterion],
        evidence_list: List[EvaluationEvidence],
    ) -> CandidateScore:
        dummy_results: List[CriterionEvaluationResult] = []
        for crit in criteria:
            ev = next((e for e in evidence_list if e.criterion_id == crit.id), None)
            score_val = 100.0 if (ev and ev.match_type.value == "EXACT") else 50.0 if (ev and ev.match_type.value == "PARTIAL") else 0.0
            dummy_results.append(
                CriterionEvaluationResult(
                    criterion_id=crit.id,
                    criterion_name=crit.criterion_name,
                    criterion_type=crit.criterion_type,
                    weight=crit.weight,
                    match_status=MatchStatus.SUPPORTED if score_val == 100.0 else MatchStatus.NOT_FOUND,
                    score=score_val,
                    supporting_evidence=[ev.supporting_text] if ev else [],
                    explanation=ev.explanation if ev else "No evidence found.",
                )
            )

        return self.aggregate_results(candidate.id, criteria, dummy_results)

    def aggregate_results(
        self,
        candidate_id: str,
        criteria: List[EvaluationCriterion],
        criterion_results: List[CriterionEvaluationResult],
    ) -> CandidateScore:
        result_map: Dict[str, CriterionEvaluationResult] = {r.criterion_id: r for r in criterion_results}

        total_weight = 0.0
        weighted_score_sum = 0.0

        evaluated_count = 0
        unavailable_count = 0
        supported_count = 0

        req_total = 0
        req_supported = 0
        req_unmet_names = []

        pref_total = 0
        pref_supported = 0

        for crit in criteria:
            if not crit.is_enabled:
                continue

            evaluated_count += 1
            res = result_map.get(crit.id)

            if not res or res.match_status == MatchStatus.NOT_EVALUATED:
                unavailable_count += 1
                continue

            crit_score = res.score * 100.0 if res.score <= 1.0 else res.score
            total_weight += crit.weight
            weighted_score_sum += (crit.weight * crit_score)

            if res.match_status in (MatchStatus.SUPPORTED, MatchStatus.PARTIALLY_SUPPORTED):
                supported_count += 1

            if res.match_status in (MatchStatus.NOT_FOUND, MatchStatus.INSUFFICIENT_EVIDENCE):
                unavailable_count += 1

            if crit.criterion_type == CriterionType.REQUIRED:
                req_total += 1
                if res.match_status in (MatchStatus.SUPPORTED, MatchStatus.PARTIALLY_SUPPORTED):
                    req_supported += 1
                else:
                    req_unmet_names.append(crit.criterion_name)
            else:
                pref_total += 1
                if res.match_status in (MatchStatus.SUPPORTED, MatchStatus.PARTIALLY_SUPPORTED):
                    pref_supported += 1

        overall_score = round(weighted_score_sum / total_weight, 1) if total_weight > 0.0 else 0.0

        coverage_pct = round((supported_count / evaluated_count * 100.0), 1) if evaluated_count > 0 else 0.0

        if supported_count == 0:
            score_status = ScoreStatus.INSUFFICIENT_EVIDENCE
        else:
            score_status = ScoreStatus.CALCULATED

        summary_parts = [
            f"Overall match score: {overall_score:.1f}/100 based on {evaluated_count} criteria.",
            f"Evidence coverage: {coverage_pct:.1f}% ({supported_count}/{evaluated_count} criteria supported with verbatim citations).",
        ]
        if req_unmet_names:
            summary_parts.append(f"⚠️ Mandatory criteria missing evidence: {', '.join(req_unmet_names)}.")
        else:
            summary_parts.append("✅ All mandatory criteria have supporting evidence.")

        full_explanation = " ".join(summary_parts)

        criterion_scores_payload = {
            "evidence_coverage": coverage_pct,
            "evaluated_criteria_count": evaluated_count,
            "unavailable_criteria_count": unavailable_count,
            "required_supported": (len(req_unmet_names) == 0),
            "required_total_count": req_total,
            "required_supported_count": req_supported,
            "required_unmet_count": len(req_unmet_names),
            "required_unmet_names": req_unmet_names,
            "preferred_total_count": pref_total,
            "preferred_supported_count": pref_supported,
            "criteria": [r.to_dict() for r in criterion_results],
        }

        return CandidateScore(
            candidate_id=candidate_id,
            overall_score=overall_score,
            criterion_scores=criterion_scores_payload,
            score_status=score_status,
            explanation=full_explanation,
            scoring_config_version=self.config_version,
            evaluated_at=datetime.now(timezone.utc).isoformat(),
        )
