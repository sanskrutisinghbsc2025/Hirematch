
import re
from typing import Any, Dict, List, Optional, Tuple

from core.models.education import EducationRecord
from core.models.enums import CriterionType, MatchStatus, MatchingRuleType
from core.models.evaluation import CriterionEvaluationResult, EvaluationCriterion


class EducationMatcher:

    TIER_SCORES = {
        "NONE": 0,
        "HIGH_SCHOOL": 1,
        "ASSOCIATE": 2,
        "BACHELOR": 3,
        "MASTER": 4,
        "DOCTORATE": 5,
    }

    DEGREE_PATTERNS = [
        (re.compile(r"\b(ph\.?d\.?|doctor(?:ate)?)\b", re.IGNORECASE), "DOCTORATE", "Doctorate / Ph.D."),
        (re.compile(r"\b(master(?:\s+of\s+\w+|'?s)?|m\.?s\.?|m\.?tech|m\.?a\.?|mba|m\.?sc)\b", re.IGNORECASE), "MASTER", "Master's Degree"),
        (re.compile(r"\b(bachelor(?:\s+of\s+\w+|'?s)?|b\.?s\.?|b\.?tech|b\.?e\.?|b\.?a\.?|b\.?sc|undergraduate)\b", re.IGNORECASE), "BACHELOR", "Bachelor's Degree"),
        (re.compile(r"\b(associate(?:\s+of\s+\w+|'?s|\s+degree)?|a\.?s\.?|a\.?a\.?)\b", re.IGNORECASE), "ASSOCIATE", "Associate Degree"),
        (re.compile(r"\b(high\s+school|diploma|ged)\b", re.IGNORECASE), "HIGH_SCHOOL", "High School / Diploma"),
    ]

    def evaluate_criterion(
        self,
        criterion: EvaluationCriterion,
        education_records: List[EducationRecord],
        candidate_certifications: Optional[List[str]] = None,
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

        req_tier_key, req_tier_name = self._determine_target_tier(criterion)
        req_tier_val = self.TIER_SCORES.get(req_tier_key, 3)

        if not education_records:
            certs = candidate_certifications or []
            if certs:
                return CriterionEvaluationResult(
                    criterion_id=criterion.id,
                    criterion_name=criterion.criterion_name,
                    criterion_type=criterion.criterion_type,
                    weight=criterion.weight,
                    match_status=MatchStatus.PARTIALLY_SUPPORTED,
                    score=40.0,
                    matched_terms=certs,
                    supporting_evidence=[f"Certifications: {', '.join(certs[:3])}"],
                    evidence_sources=["CERTIFICATIONS"],
                    matching_method=MatchingRuleType.EDUCATION_DEGREE.value,
                    explanation=(
                        f"No formal academic degrees extracted, but {len(certs)} professional credential(s) found. "
                        f"(Target: {req_tier_name})"
                    ),
                    confidence=0.7,
                )
            else:
                return CriterionEvaluationResult(
                    criterion_id=criterion.id,
                    criterion_name=criterion.criterion_name,
                    criterion_type=criterion.criterion_type,
                    weight=criterion.weight,
                    match_status=MatchStatus.NOT_FOUND,
                    score=0.0,
                    explanation=(
                        f"No degree or academic qualification documented in resume. "
                        f"This does not confirm absence of qualifications (Target: {req_tier_name})."
                    ),
                )

        classified_degrees: List[Tuple[str, str, int, EducationRecord]] = []

        for edu in education_records:
            deg_text = getattr(edu, "degree", "") or edu.qualification or ""
            tier_k, tier_n = self._classify_text(deg_text)
            tier_v = self.TIER_SCORES.get(tier_k, 0)
            classified_degrees.append((tier_k, tier_n, tier_v, edu))

        highest = max(classified_degrees, key=lambda x: x[2])
        best_tier_key, best_tier_name, best_tier_val, best_record = highest

        qual_str = getattr(best_record, "degree", "") or best_record.qualification
        evidence_str = (
            f"{qual_str} from "
            f"{best_record.institution or 'Unspecified'} ({best_record.dates or 'No date'})"
        )
        matched_terms = [best_tier_name]
        evidence_list = [evidence_str]

        if best_tier_val >= req_tier_val:
            score = 100.0
            status = MatchStatus.SUPPORTED
            if best_tier_val > req_tier_val:
                explanation = f"Exceeds requirement: Candidate holds {best_tier_name}, surpassing the {req_tier_name} requirement."
            else:
                explanation = f"Directly satisfies requirement: Candidate holds verified {best_tier_name}."
        elif best_tier_val == req_tier_val - 1:
            score = 60.0
            status = MatchStatus.PARTIALLY_SUPPORTED
            explanation = f"Partially satisfies: Candidate holds {best_tier_name} (Target: {req_tier_name})."
        else:
            score = 30.0
            status = MatchStatus.NOT_FOUND
            explanation = f"Candidate degree ({best_tier_name}) does not meet the specified {req_tier_name} tier."

        return CriterionEvaluationResult(
            criterion_id=criterion.id,
            criterion_name=criterion.criterion_name,
            criterion_type=criterion.criterion_type,
            weight=criterion.weight,
            match_status=status,
            score=score,
            matched_terms=matched_terms,
            supporting_evidence=evidence_list,
            evidence_sources=["EDUCATION"],
            matching_method=MatchingRuleType.EDUCATION_DEGREE.value,
            explanation=explanation,
            confidence=0.95,
        )

    def _determine_target_tier(self, criterion: EvaluationCriterion) -> Tuple[str, str]:
        cfg_tier = criterion.matching_config.get("target_tier") or criterion.matching_config.get("required_level")
        if cfg_tier:
            k, n = self._classify_text(str(cfg_tier))
            if k != "NONE":
                return k, n
            if str(cfg_tier).upper() in self.TIER_SCORES:
                return str(cfg_tier).upper(), str(cfg_tier).title()

        combined = f"{criterion.criterion_name} {criterion.description}"
        return self._classify_text(combined)

    def _classify_text(self, text: str) -> Tuple[str, str]:
        for pattern, tier_key, tier_name in self.DEGREE_PATTERNS:
            if pattern.search(text):
                return tier_key, tier_name
        return "NONE", "Unclassified Qualification"
