
from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from core.evaluation.negation_detector import NegationDetector
from core.models.enums import CriterionType, MatchStatus, MatchingRuleType
from core.models.evaluation import CriterionEvaluationResult, EvaluationCriterion
from core.models.skills import ExtractedSkill
from core.processing.cleaner import TextCleaner
from core.processing.skill_normalizer import SkillTaxonomyNormalizer


@dataclass
class MatchHit:
    target_term: str
    matched_term: str
    canonical_name: str
    evidence_text: str
    source_section: str
    confidence: float
    rule_type: MatchingRuleType
    is_negated: bool = False
    negation_cue: Optional[str] = None


class SectionAwareKeywordMatcher:

    SECTION_WEIGHTS = {
        "SKILLS": 1.0,
        "EXPERIENCE": 0.95,
        "PROJECTS": 0.85,
        "SUMMARY": 0.80,
        "EDUCATION": 0.70,
        "CERTIFICATIONS": 0.90,
        "HEADER": 0.50,
        "UNCLASSIFIED": 0.65,
        "GENERAL": 0.70,
    }

    def __init__(
        self,
        normalizer: Optional[SkillTaxonomyNormalizer] = None,
        negation_detector: Optional[NegationDetector] = None,
    ):
        self.normalizer = normalizer or SkillTaxonomyNormalizer()
        self.negation_detector = negation_detector or NegationDetector()

    def evaluate_criterion(
        self,
        criterion: EvaluationCriterion,
        candidate_skills: List[ExtractedSkill],
        candidate_sections: Dict[str, str],
        candidate_raw_text: str,
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

        target_skills = self._extract_target_terms(criterion)

        if not target_skills:
            target_skills = [criterion.criterion_name.strip()]

        hits: List[MatchHit] = []
        negated_hits: List[MatchHit] = []

        skill_map: Dict[str, ExtractedSkill] = {
            s.normalized_skill_name.lower(): s for s in candidate_skills
        }

        for target in target_skills:
            target_lower = target.lower().strip()
            canonical_target, _ = self.normalizer.normalize(target)

            matched_skill = skill_map.get(canonical_target.lower()) or skill_map.get(target_lower)
            if matched_skill:
                is_neg, cue = self.negation_detector.is_negated(
                    matched_skill.evidence_text, matched_skill.skill_name
                )
                hit = MatchHit(
                    target_term=target,
                    matched_term=matched_skill.skill_name,
                    canonical_name=matched_skill.normalized_skill_name,
                    evidence_text=matched_skill.evidence_text,
                    source_section=matched_skill.source_location,
                    confidence=self.SECTION_WEIGHTS.get(matched_skill.source_location.upper(), 0.8),
                    rule_type=(
                        MatchingRuleType.EXACT
                        if target_lower == matched_skill.skill_name.lower()
                        else MatchingRuleType.TAXONOMY_ALIAS
                    ),
                    is_negated=is_neg,
                    negation_cue=cue,
                )
                if is_neg:
                    negated_hits.append(hit)
                else:
                    hits.append(hit)
                continue

            found_in_sections = False
            for sec_name, sec_content in candidate_sections.items():
                match_res = self._scan_text_for_term(sec_content, target, canonical_target, sec_name)
                if match_res:
                    if match_res.is_negated:
                        negated_hits.append(match_res)
                    else:
                        hits.append(match_res)
                    found_in_sections = True
                    break

            if not found_in_sections and candidate_raw_text:
                full_hit = self._scan_text_for_term(candidate_raw_text, target, canonical_target, "GENERAL")
                if full_hit:
                    if full_hit.is_negated:
                        negated_hits.append(full_hit)
                    else:
                        hits.append(full_hit)

        total_targets = len(target_skills)
        positive_count = len(hits)

        if positive_count == 0:
            if negated_hits:
                explanation = (
                    f"Mentioned in resume, but detected in negative context: "
                    f"'{negated_hits[0].negation_cue}' found near '{negated_hits[0].matched_term}'."
                )
                return CriterionEvaluationResult(
                    criterion_id=criterion.id,
                    criterion_name=criterion.criterion_name,
                    criterion_type=criterion.criterion_type,
                    weight=criterion.weight,
                    match_status=MatchStatus.NOT_FOUND,
                    score=0.0,
                    matched_terms=[nh.matched_term for nh in negated_hits],
                    supporting_evidence=[nh.evidence_text for nh in negated_hits],
                    evidence_sources=[nh.source_section for nh in negated_hits],
                    matching_method="negation_detected",
                    explanation=explanation,
                    confidence=1.0,
                    is_negative_context=True,
                )
            else:
                return CriterionEvaluationResult(
                    criterion_id=criterion.id,
                    criterion_name=criterion.criterion_name,
                    criterion_type=criterion.criterion_type,
                    weight=criterion.weight,
                    match_status=MatchStatus.NOT_FOUND,
                    score=0.0,
                    explanation=f"No positive evidence found for '{criterion.criterion_name}' in resume.",
                )

        match_ratio = min(1.0, positive_count / total_targets)
        avg_confidence = sum(h.confidence for h in hits) / len(hits)
        score = round(match_ratio * avg_confidence * 100.0, 1)

        match_status = MatchStatus.SUPPORTED if match_ratio >= 0.8 else MatchStatus.PARTIALLY_SUPPORTED

        matched_names = [h.canonical_name for h in hits]
        supporting_excerpts = [h.evidence_text for h in hits]
        sources = list(dict.fromkeys(h.source_section for h in hits))

        explanation_parts = [
            f"Matched {positive_count}/{total_targets} terms ({', '.join(matched_names)})",
            f"found across {', '.join(sources)} sections.",
        ]
        if negated_hits:
            neg_terms = [nh.matched_term for nh in negated_hits]
            explanation_parts.append(f"Note: {', '.join(neg_terms)} excluded due to negative context.")

        return CriterionEvaluationResult(
            criterion_id=criterion.id,
            criterion_name=criterion.criterion_name,
            criterion_type=criterion.criterion_type,
            weight=criterion.weight,
            match_status=match_status,
            score=score,
            matched_terms=matched_names,
            supporting_evidence=supporting_excerpts[:3],
            evidence_sources=sources,
            matching_method=hits[0].rule_type.value,
            explanation=" ".join(explanation_parts),
            confidence=avg_confidence,
            is_negative_context=bool(negated_hits),
        )

    def _extract_target_terms(self, criterion: EvaluationCriterion) -> List[str]:
        targets = []
        combined_text = f"{criterion.criterion_name} {criterion.description}"

        cfg_terms = criterion.matching_config.get("target_skills") or criterion.matching_config.get("keywords")
        if cfg_terms and isinstance(cfg_terms, list):
            return [str(t).strip() for t in cfg_terms if str(t).strip()]

        skills = self.normalizer.extract_and_normalize(combined_text)
        if skills:
            targets = [s.canonical_name for s in skills]

        if not targets and criterion.description:
            phrases = re.split(r"[,;•|/]", criterion.description)
            for p in phrases:
                cp = p.strip()
                if 2 <= len(cp) <= 40:
                    targets.append(cp)

        return list(dict.fromkeys(targets))

    def _scan_text_for_term(
        self, text: str, term: str, canonical_term: str, section_name: str
    ) -> Optional[MatchHit]:
        if not text or not term:
            return None

        escaped_term = re.escape(term.strip().lower())
        pattern = r"(?<!\w)" + escaped_term + r"(?!\w)"

        match = re.search(pattern, text, re.IGNORECASE)
        rule_type = MatchingRuleType.EXACT

        if not match and canonical_term != term:
            escaped_canonical = re.escape(canonical_term.strip().lower())
            pattern = r"(?<!\w)" + escaped_canonical + r"(?!\w)"
            match = re.search(pattern, text, re.IGNORECASE)
            rule_type = MatchingRuleType.TAXONOMY_ALIAS

        if not match:
            return None

        verbatim = match.group(0)

        sentences = re.split(r"(?<=[.!?\n])\s+", text)
        evidence = verbatim
        for s in sentences:
            if verbatim in s or term.lower() in s.lower():
                evidence = s.strip()
                break

        is_neg, cue = self.negation_detector.is_negated(evidence, verbatim)

        return MatchHit(
            target_term=term,
            matched_term=verbatim,
            canonical_name=canonical_term,
            evidence_text=evidence,
            source_section=section_name,
            confidence=self.SECTION_WEIGHTS.get(section_name.upper(), 0.7),
            rule_type=rule_type,
            is_negated=is_neg,
            negation_cue=cue,
        )


KeywordMatcher = SectionAwareKeywordMatcher
