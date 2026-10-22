
from datetime import datetime, timezone
import re
from typing import Any, Dict, List, Optional, Tuple

from core.models.enums import CriterionType, MatchStatus, MatchingRuleType
from core.models.evaluation import CriterionEvaluationResult, EvaluationCriterion
from core.models.experience import WorkExperience


class ExperienceMatcher:

    DATE_RANGE_PATTERN = re.compile(
        r"\b(19\d\d|20\d\d)\b(?:\s*(?:-|–|—|to)\s*(?:present|current|now|\b(19\d\d|20\d\d)\b))?",
        re.IGNORECASE,
    )

    def evaluate_criterion(
        self,
        criterion: EvaluationCriterion,
        work_experience: List[WorkExperience],
        job_category: Optional[str] = None,
    ) -> CriterionEvaluationResult:
        if not criterion.is_enabled:
            return CriterionEvaluationResult(
                criterion_id=criterion.id,
                criterion_name=criterion.criterion_name,
                criterion_type=criterion.criterion_type,
                weight=criterion.weight,
                match_status=MatchStatus.NOT_EVALUATED,
                score=0.0,
                explanation="Criterion disabled in scoring configuration.",
            )

        required_years = self._extract_required_years(criterion)

        if not work_experience:
            return CriterionEvaluationResult(
                criterion_id=criterion.id,
                criterion_name=criterion.criterion_name,
                criterion_type=criterion.criterion_type,
                weight=criterion.weight,
                match_status=MatchStatus.NOT_FOUND,
                score=0.0,
                explanation=f"No employment history documented in resume ({required_years}+ years expected).",
            )

        intervals: List[Tuple[float, float, str]] = []
        has_undated_roles = False
        evidence_excerpts = []

        current_year = float(datetime.now(timezone.utc).year)

        for exp in work_experience:
            start_yr, end_yr = self._parse_dates(exp.dates)
            role_label = f"{exp.job_title} at {exp.employer or 'Unspecified'} ({exp.dates or 'No dates'})"

            if start_yr is not None and end_yr is not None:
                intervals.append((start_yr, end_yr, role_label))
                if exp.evidence_text:
                    evidence_excerpts.append(exp.evidence_text)
                else:
                    evidence_excerpts.append(role_label)
            else:
                has_undated_roles = True
                if exp.evidence_text:
                    evidence_excerpts.append(exp.evidence_text)

        if not intervals:
            return CriterionEvaluationResult(
                criterion_id=criterion.id,
                criterion_name=criterion.criterion_name,
                criterion_type=criterion.criterion_type,
                weight=criterion.weight,
                match_status=MatchStatus.INSUFFICIENT_EVIDENCE,
                score=30.0 if len(work_experience) >= 2 else 15.0,
                supporting_evidence=evidence_excerpts[:2],
                evidence_sources=["EXPERIENCE"],
                matching_method=MatchingRuleType.EXPERIENCE_YEARS.value,
                explanation=(
                    f"Candidate documents {len(work_experience)} employment role(s), "
                    f"but exact dates could not be verified ({required_years}+ years required)."
                ),
                confidence=0.5,
            )

        merged_duration = self._calculate_non_overlapping_tenure(intervals)

        if required_years <= 0:
            score = 100.0
            status = MatchStatus.SUPPORTED
            explanation = f"Documented {merged_duration:.1f} years across {len(intervals)} verified role(s)."
        elif merged_duration >= required_years:
            score = 100.0
            status = MatchStatus.SUPPORTED
            explanation = (
                f"Documented {merged_duration:.1f} years of verified experience, "
                f"satisfying the {required_years}+ years requirement."
            )
        elif merged_duration >= required_years * 0.5:
            score = round((merged_duration / required_years) * 100.0, 1)
            status = MatchStatus.PARTIALLY_SUPPORTED
            explanation = (
                f"Documented {merged_duration:.1f} years of verified experience, "
                f"partially meeting the {required_years}+ years requirement."
            )
        else:
            score = round((merged_duration / required_years) * 100.0, 1)
            status = MatchStatus.NOT_FOUND
            explanation = (
                f"Documented {merged_duration:.1f} years of verified experience, "
                f"which is below the {required_years}+ years requirement."
            )

        if has_undated_roles:
            explanation += " (Note: Some additional roles lacked verifiable dates)."

        matched_roles = [inv[2] for inv in intervals]

        return CriterionEvaluationResult(
            criterion_id=criterion.id,
            criterion_name=criterion.criterion_name,
            criterion_type=criterion.criterion_type,
            weight=criterion.weight,
            match_status=status,
            score=score,
            matched_terms=matched_roles,
            supporting_evidence=evidence_excerpts[:3],
            evidence_sources=["EXPERIENCE"],
            matching_method=MatchingRuleType.EXPERIENCE_YEARS.value,
            explanation=explanation,
            confidence=0.9 if not has_undated_roles else 0.75,
        )

    def _extract_required_years(self, criterion: EvaluationCriterion) -> int:
        if "min_years" in criterion.matching_config:
            try:
                return int(criterion.matching_config["min_years"])
            except (ValueError, TypeError):
                pass

        combined = f"{criterion.criterion_name} {criterion.description}"
        m = re.search(r"(\d+)\+?\s*years?", combined, re.IGNORECASE)
        if m:
            try:
                return int(m.group(1))
            except ValueError:
                pass

        return 3

    def _parse_dates(self, date_str: Optional[str]) -> Tuple[Optional[float], Optional[float]]:
        if not date_str or not date_str.strip():
            return None, None

        current_year = float(datetime.now(timezone.utc).year)
        years = re.findall(r"\b(19\d\d|20\d\d)\b", date_str)

        if not years:
            return None, None

        start_yr = float(years[0])

        if len(years) >= 2:
            end_yr = float(years[1])
        elif any(k in date_str.lower() for k in ["present", "current", "now"]):
            end_yr = current_year
        else:
            end_yr = start_yr + 1.0

        if end_yr < start_yr:
            end_yr, start_yr = start_yr, end_yr

        return start_yr, end_yr

    def _calculate_non_overlapping_tenure(self, intervals: List[Tuple[float, float, str]]) -> float:
        if not intervals:
            return 0.0

        sorted_inv = sorted([(i[0], i[1]) for i in intervals], key=lambda x: x[0])
        merged = []

        curr_start, curr_end = sorted_inv[0]
        for s, e in sorted_inv[1:]:
            if s <= curr_end:
                curr_end = max(curr_end, e)
            else:
                merged.append((curr_start, curr_end))
                curr_start, curr_end = s, e
        merged.append((curr_start, curr_end))

        total_tenure = sum(max(0.0, e - s) for s, e in merged)
        return total_tenure
