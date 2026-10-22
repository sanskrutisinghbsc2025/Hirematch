
from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

from core.models.enums import (
    EvidenceDisagreementType,
    MatchStatus,
    MatchType,
    SemanticSimilarityTier,
)
from core.models.evaluation import (
    CriterionEvaluationResult,
    EvaluationCriterion,
    SemanticMatchResult,
)


@dataclass
class SynthesizedEvidenceCitation:

    passage_text: str
    source_section: str
    matched_by: List[str]
    confidence_score: float
    is_negated: bool = False
    char_start: int = 0
    char_end: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passage_text": self.passage_text,
            "source_section": self.source_section,
            "matched_by": self.matched_by,
            "confidence_score": round(self.confidence_score, 4),
            "is_negated": self.is_negated,
            "char_start": self.char_start,
            "char_end": self.char_end,
        }


@dataclass
class SynthesizedCriterionEvaluation:

    criterion_id: str
    criterion_name: str
    match_status: MatchStatus
    synthesized_score: float
    disagreement_type: EvidenceDisagreementType
    conflict_explanation: str
    citations: List[SynthesizedEvidenceCitation]
    explanation: str
    baseline_score: float
    semantic_score: float
    is_negative_context: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "criterion_id": self.criterion_id,
            "criterion_name": self.criterion_name,
            "match_status": self.match_status.value,
            "synthesized_score": round(self.synthesized_score, 1),
            "disagreement_type": self.disagreement_type.value,
            "conflict_explanation": self.conflict_explanation,
            "citations": [c.to_dict() for c in self.citations],
            "explanation": self.explanation,
            "baseline_score": round(self.baseline_score, 1),
            "semantic_score": round(self.semantic_score, 1),
            "is_negative_context": self.is_negative_context,
        }


class MultiLayerEvidenceSynthesizer:

    @classmethod
    def synthesize_criterion(
        cls,
        criterion: EvaluationCriterion,
        baseline_result: Optional[CriterionEvaluationResult],
        semantic_result: Optional[CriterionEvaluationResult],
        structured_entities: Optional[List[Dict[str, Any]]] = None,
        baseline_weight: float = 0.5,
        semantic_weight: float = 0.5,
    ) -> SynthesizedCriterionEvaluation:
        b_res = baseline_result
        s_res = semantic_result

        b_score = b_res.score if b_res else 0.0
        s_score = s_res.score if s_res else 0.0
        b_negated = b_res.is_negative_context if b_res else False
        s_sim = s_res.semantic_score if s_res else 0.0

        citations = cls._deduplicate_citations(
            baseline_result=b_res,
            semantic_result=s_res,
            structured_entities=structured_entities,
        )

        disagreement_type = EvidenceDisagreementType.NONE
        conflict_explanation = ""
        synthesized_status = MatchStatus.NOT_FOUND
        synthesized_score = 0.0
        explanation_parts = []

        if b_negated and s_sim and s_sim >= 0.50:
            disagreement_type = EvidenceDisagreementType.KEYWORD_NEGATED_IN_CONTEXT
            synthesized_status = MatchStatus.CONFLICTING_EVIDENCE
            synthesized_score = 0.0
            conflict_explanation = (
                f"Conflict detected: Resume text states negative context ('{b_res.explanation}'), "
                f"which contradicts dense semantic topical similarity ({s_sim:.2f}). "
                "Flagged as conflicting evidence for mandatory recruiter review."
            )
            explanation_parts.append(f"⚠️ {conflict_explanation}")

        elif (b_score == 0.0 or (b_res and b_res.match_status == MatchStatus.NOT_FOUND)) and (s_sim and s_sim >= 0.55):
            disagreement_type = EvidenceDisagreementType.SEMANTIC_WITHOUT_KEYWORD
            if s_sim >= 0.70:
                synthesized_status = MatchStatus.SUPPORTED
                synthesized_score = s_score * 0.90
            else:
                synthesized_status = MatchStatus.PARTIALLY_SUPPORTED
                synthesized_score = s_score * 0.75

            explanation_parts.append(
                f"Contextual match discovered via semantic AI (similarity: {s_sim:.2f}) "
                "despite absence of literal keyword in structured resume."
            )
            if s_res and s_res.explanation:
                explanation_parts.append(s_res.explanation)

        elif b_score >= 50.0 and (s_sim is None or s_sim < 0.35):
            synthesized_status = MatchStatus.PARTIALLY_SUPPORTED
            synthesized_score = b_score * 0.80
            explanation_parts.append(
                f"Baseline: Keyword identified in resume ({b_res.explanation if b_res else ''}), "
                "but lacked detailed descriptive passages for semantic corroboration."
            )

        elif b_score >= 50.0 and s_score >= 50.0:
            synthesized_status = (
                MatchStatus.SUPPORTED
                if (b_score >= 75.0 or s_score >= 75.0)
                else MatchStatus.PARTIALLY_SUPPORTED
            )
            synthesized_score = (baseline_weight * b_score) + (semantic_weight * s_score)
            explanation_parts.append("Both rule-based baseline and semantic AI confirm supporting evidence.")
            if b_res and b_res.explanation:
                explanation_parts.append(f"Baseline: {b_res.explanation}")
            if s_res and s_res.explanation:
                explanation_parts.append(f"Semantic AI: {s_res.explanation}")

        elif b_score > 0.0 and (s_res is None or s_res.match_status == MatchStatus.NOT_EVALUATED):
            synthesized_status = b_res.match_status if b_res else MatchStatus.PARTIALLY_SUPPORTED
            synthesized_score = b_score
            if b_res and b_res.explanation:
                explanation_parts.append(b_res.explanation)

        else:
            synthesized_status = MatchStatus.NOT_FOUND
            synthesized_score = 0.0
            explanation_parts.append(f"No verifiable evidence found for '{criterion.criterion_name}' across evaluation layers.")

        full_explanation = " ".join(explanation_parts)

        return SynthesizedCriterionEvaluation(
            criterion_id=criterion.id,
            criterion_name=criterion.criterion_name,
            match_status=synthesized_status,
            synthesized_score=synthesized_score,
            disagreement_type=disagreement_type,
            conflict_explanation=conflict_explanation,
            citations=citations,
            explanation=full_explanation,
            baseline_score=b_score,
            semantic_score=s_score,
            is_negative_context=b_negated,
        )

    @classmethod
    def _deduplicate_citations(
        cls,
        baseline_result: Optional[CriterionEvaluationResult],
        semantic_result: Optional[CriterionEvaluationResult],
        structured_entities: Optional[List[Dict[str, Any]]],
    ) -> List[SynthesizedEvidenceCitation]:
        raw_candidates: List[Tuple[str, str, str, float, bool, int, int]] = []

        if baseline_result and baseline_result.supporting_evidence:
            for idx, text in enumerate(baseline_result.supporting_evidence):
                src = (
                    baseline_result.evidence_sources[idx]
                    if idx < len(baseline_result.evidence_sources)
                    else "general"
                )
                raw_candidates.append(
                    (text, src, "baseline", baseline_result.confidence, baseline_result.is_negative_context, 0, len(text))
                )

        if semantic_result and semantic_result.top_passages:
            for p in semantic_result.top_passages:
                text = p.get("passage_text", "")
                src = p.get("source_section", "general")
                score = float(p.get("similarity_score", 0.0))
                c_start = int(p.get("char_start", 0))
                c_end = int(p.get("char_end", 0))
                if text.strip():
                    raw_candidates.append(
                        (text, src, "semantic", score, False, c_start, c_end)
                    )

        if structured_entities:
            for e in structured_entities:
                ev_text = e.get("evidence_text") or e.get("extracted_description") or ""
                src = e.get("source_location") or "structured"
                if ev_text.strip():
                    raw_candidates.append(
                        (ev_text, src, "structured", 1.0, False, 0, len(ev_text))
                    )

        deduped: List[SynthesizedEvidenceCitation] = []

        for text, src, layer, conf, is_neg, c_start, c_end in raw_candidates:
            clean_text = text.strip()
            if not clean_text:
                continue

            merged = False
            for existing in deduped:
                if (
                    clean_text.lower() in existing.passage_text.lower()
                    or existing.passage_text.lower() in clean_text.lower()
                ):
                    if layer not in existing.matched_by:
                        existing.matched_by.append(layer)
                    existing.confidence_score = max(existing.confidence_score, conf)
                    existing.is_negated = existing.is_negated or is_neg
                    if len(clean_text) > len(existing.passage_text):
                        existing.passage_text = clean_text
                        existing.source_section = src
                        existing.char_start = c_start
                        existing.char_end = c_end
                    merged = True
                    break

            if not merged:
                deduped.append(
                    SynthesizedEvidenceCitation(
                        passage_text=clean_text,
                        source_section=src,
                        matched_by=[layer],
                        confidence_score=conf,
                        is_negated=is_neg,
                        char_start=c_start,
                        char_end=c_end,
                    )
                )

        return deduped
