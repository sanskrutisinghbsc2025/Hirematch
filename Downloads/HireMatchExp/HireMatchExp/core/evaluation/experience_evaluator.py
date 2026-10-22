
from datetime import datetime, timezone
import re
from typing import Any, Dict, List, Optional, Tuple

from core.evaluation.experience_matcher import ExperienceMatcher
from core.models.enums import CriterionCategory, CriterionType, MatchStatus, MatchingRuleType
from core.models.evaluation import CriterionEvaluationResult, EvaluationCriterion
from core.models.experience import WorkExperience


class ConservativeExperienceEvaluator:

    def __init__(self, base_matcher: Optional[ExperienceMatcher] = None):
        self.base_matcher = base_matcher or ExperienceMatcher()

    def evaluate(
        self,
        criterion: EvaluationCriterion,
        work_experience: List[WorkExperience],
        projects: Optional[List[Dict[str, Any]]] = None,
        job_category: Optional[str] = None,
        relevant_keywords: Optional[List[str]] = None,
    ) -> CriterionEvaluationResult:
        if not criterion.is_enabled:
            return CriterionEvaluationResult(
                criterion_id=criterion.id,
                criterion_name=criterion.criterion_name,
                criterion_type=criterion.criterion_type,
                weight=criterion.weight,
                match_status=MatchStatus.NOT_EVALUATED,
                score=0.0,
                category=CriterionCategory.EXPERIENCE_DURATION,
                explanation="Criterion disabled.",
            )

        req_years = self._extract_required_years(criterion)

        if not work_experience and not projects:
            return CriterionEvaluationResult(
                criterion_id=criterion.id,
                criterion_name=criterion.criterion_name,
                criterion_type=criterion.criterion_type,
                weight=criterion.weight,
                match_status=MatchStatus.NOT_FOUND,
                score=0.0,
                category=CriterionCategory.EXPERIENCE_DURATION,
                explanation=f"No employment or project history documented ({req_years}+ years expected).",
            )

        all_intervals: List[Tuple[float, float, str]] = []
        relevant_intervals: List[Tuple[float, float, str]] = []
        ambiguous_roles: List[str] = []
        evidence_citations: List[str] = []

        keywords = [k.lower().strip() for k in (relevant_keywords or []) if k.strip()]

        for exp in work_experience:
            start_yr, end_yr = self.base_matcher._parse_dates(exp.dates)
            role_desc = f"{exp.job_title} at {exp.employer or 'Unspecified'} ({exp.dates or 'No dates'})"
            full_role_text = f"{exp.job_title} {exp.extracted_description or ''} {exp.evidence_text or ''}".lower()

            is_relevant = True
            if keywords:
                is_relevant = any(kw in full_role_text for kw in keywords)

            if start_yr is not None and end_yr is not None:
                all_intervals.append((start_yr, end_yr, role_desc))
                if is_relevant:
                    relevant_intervals.append((start_yr, end_yr, role_desc))
                    if exp.evidence_text:
                        evidence_citations.append(exp.evidence_text)
                    else:
                        evidence_citations.append(role_desc)
            else:
                ambiguous_roles.append(role_desc)
                if exp.evidence_text:
                    evidence_citations.append(exp.evidence_text)

        project_boost = 0.0
        if projects and len(relevant_intervals) == 0:
            relevant_projs = []
            for p in projects:
                p_title = p.get("title", "") if isinstance(p, dict) else getattr(p, "title", "")
                p_desc = p.get("description", "") if isinstance(p, dict) else getattr(p, "description", "")
                p_text = f"{p_title} {p_desc}".lower()
                if not keywords or any(kw in p_text for kw in keywords):
                    relevant_projs.append(p)
                    evidence_citations.append(f"Project: {p_title or 'Project'} - {p_desc[:100]}")
            if relevant_projs:
                project_boost = min(1.5, len(relevant_projs) * 0.5)

        if not all_intervals and ambiguous_roles:
            return CriterionEvaluationResult(
                criterion_id=criterion.id,
                criterion_name=criterion.criterion_name,
                criterion_type=criterion.criterion_type,
                weight=criterion.weight,
                match_status=MatchStatus.INSUFFICIENT_EVIDENCE,
                score=40.0,
                supporting_evidence=evidence_citations[:2],
                evidence_sources=["EXPERIENCE"],
                matching_method="conservative_tenure_analysis",
                category=CriterionCategory.EXPERIENCE_DURATION,
                explanation=(
                    f"Candidate documents {len(ambiguous_roles)} roles ({', '.join([r[:40] for r in ambiguous_roles[:2]])}), "
                    "but dates are missing or ambiguous. Evaluated as INSUFFICIENT_EVIDENCE without negative penalty."
                ),
            )

        total_tenure = self.base_matcher._calculate_non_overlapping_tenure(all_intervals)
        rel_tenure = (
            self.base_matcher._calculate_non_overlapping_tenure(relevant_intervals)
            if relevant_intervals
            else total_tenure
        )
        effective_tenure = rel_tenure + project_boost

        if effective_tenure >= req_years:
            status = MatchStatus.SUPPORTED
            score = 100.0
            explanation = (
                f"Demonstrated {effective_tenure:.1f} years of non-overlapping relevant tenure "
                f"(exceeds requirement of {req_years:.1f} years across {len(relevant_intervals or all_intervals)} roles)."
            )
        elif effective_tenure >= req_years * 0.65:
            status = MatchStatus.PARTIALLY_SUPPORTED
            score = round((effective_tenure / req_years) * 100.0, 1)
            explanation = (
                f"Demonstrated {effective_tenure:.1f} years of relevant tenure ({score:.0f}% of {req_years:.1f} year expectation)."
            )
        elif effective_tenure > 0.0:
            status = MatchStatus.PARTIALLY_SUPPORTED if not criterion.criterion_type == CriterionType.REQUIRED else MatchStatus.INSUFFICIENT_EVIDENCE
            score = round((effective_tenure / req_years) * 80.0, 1)
            explanation = (
                f"Limited verified relevant tenure ({effective_tenure:.1f} years vs {req_years:.1f} years requested)."
            )
        else:
            status = MatchStatus.NOT_FOUND
            score = 0.0
            explanation = f"No relevant tenure matching domain requirements found ({req_years:.1f} years expected)."

        if ambiguous_roles and status != MatchStatus.SUPPORTED:
            explanation += f" Note: {len(ambiguous_roles)} additional role(s) lacked parseable date ranges."

        return CriterionEvaluationResult(
            criterion_id=criterion.id,
            criterion_name=criterion.criterion_name,
            criterion_type=criterion.criterion_type,
            weight=criterion.weight,
            match_status=status,
            score=score,
            supporting_evidence=evidence_citations[:3],
            evidence_sources=["EXPERIENCE"],
            matching_method="conservative_tenure_analysis",
            category=CriterionCategory.EXPERIENCE_DURATION,
            explanation=explanation,
        )

    def _extract_required_years(self, criterion: EvaluationCriterion) -> float:
        if "years" in criterion.evidence_requirements:
            try:
                return float(criterion.evidence_requirements["years"])
            except (ValueError, TypeError):
                pass

        text = f"{criterion.criterion_name} {criterion.description}"
        m = re.search(r"(\d+(?:\.\d+)?)\s*\+?\s*(?:to\s*\d+\s*)?years?", text, re.IGNORECASE)
        if m:
            return float(m.group(1))

        return 3.0
