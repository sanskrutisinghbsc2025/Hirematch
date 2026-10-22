
from typing import Any, Dict, List, Optional, Tuple

from core.evaluation.interfaces import ICandidateEvaluator
from core.evaluation.semantic_matcher import SemanticMatcher
from core.evaluation.text_chunker import DocumentChunk, SectionAwareTextChunker
from core.models.candidate import Candidate
from core.models.enums import CriterionType, MatchStatus, MatchType, SemanticSimilarityTier
from core.models.evaluation import (
    CriterionEvaluationResult,
    EvaluationCriterion,
    EvaluationEvidence,
    SemanticMatchResult,
)
from core.models.job import Job
from core.utils.logger import logger


class SemanticCandidateEvaluator(ICandidateEvaluator):

    def __init__(
        self,
        semantic_matcher: SemanticMatcher,
        chunker: Optional[SectionAwareTextChunker] = None,
        top_k: int = 3,
        threshold: float = 0.35,
    ):
        self.matcher = semantic_matcher
        self.chunker = chunker or SectionAwareTextChunker()
        self.top_k = top_k
        self.threshold = threshold

    def evaluate(
        self,
        candidate: Candidate,
        job: Job,
        criteria: List[EvaluationCriterion],
        structured_data: Optional[Dict[str, Any]] = None,
    ) -> List[EvaluationEvidence]:
        _, evidence_list = self.evaluate_candidate_detailed(
            candidate=candidate,
            job=job,
            criteria=criteria,
            structured_data=structured_data,
        )
        return evidence_list

    def evaluate_candidate_detailed(
        self,
        candidate: Candidate,
        job: Job,
        criteria: List[EvaluationCriterion],
        structured_data: Optional[Dict[str, Any]] = None,
    ) -> Tuple[List[CriterionEvaluationResult], List[EvaluationEvidence]]:
        text = candidate.extracted_text or ""
        chunks = self.chunker.chunk_candidate(text, structured_data=structured_data)

        if not chunks:
            empty_results = []
            for crit in criteria:
                empty_results.append(
                    CriterionEvaluationResult(
                        criterion_id=crit.id,
                        criterion_name=crit.criterion_name,
                        criterion_type=crit.criterion_type,
                        weight=crit.weight,
                        match_status=MatchStatus.NOT_FOUND,
                        score=0.0,
                        matched_terms=[],
                        supporting_evidence=[],
                        evidence_sources=[],
                        matching_method="semantic_similarity",
                        explanation="No resume text available for semantic evaluation.",
                        confidence=1.0,
                        semantic_score=0.0,
                        similarity_tier=SemanticSimilarityTier.INSUFFICIENT,
                        top_passages=[],
                    )
                )
            return empty_results, []

        passage_texts = [c.text for c in chunks]
        passage_embeddings = self.matcher.provider.encode_passages(passage_texts, normalize=True)

        criterion_results: List[CriterionEvaluationResult] = []
        evidence_records: List[EvaluationEvidence] = []

        for crit in criteria:
            if not crit.is_enabled:
                continue

            query = crit.criterion_name
            if crit.description and crit.description.strip():
                query = f"{crit.criterion_name}: {crit.description.strip()}"

            top_matches: List[SemanticMatchResult] = self.matcher.match_criterion(
                query=query,
                chunks=chunks,
                passage_embeddings=passage_embeddings,
                top_k=self.top_k,
                threshold=self.threshold,
            )

            best_match = top_matches[0] if top_matches else None
            best_score = best_match.similarity_score if best_match else 0.0
            best_tier = best_match.similarity_tier if best_match else SemanticSimilarityTier.INSUFFICIENT

            if best_tier == SemanticSimilarityTier.STRONG:
                match_status = MatchStatus.SUPPORTED
                scaled_score = min(100.0, best_score * 100.0)
            elif best_tier == SemanticSimilarityTier.POSSIBLE:
                match_status = MatchStatus.PARTIALLY_SUPPORTED
                scaled_score = best_score * 100.0
            elif best_tier == SemanticSimilarityTier.WEAK:
                match_status = MatchStatus.INSUFFICIENT_EVIDENCE
                scaled_score = best_score * 50.0
            else:
                match_status = MatchStatus.NOT_FOUND
                scaled_score = 0.0

            top_passages_dicts = [m.to_dict() for m in top_matches]
            supporting_texts = [m.passage_text for m in top_matches if m.similarity_score >= self.threshold]

            if best_match and best_match.similarity_score >= self.threshold:
                explanation = (
                    f"Contextual similarity: {best_score:.2f} ({best_tier.value.upper()}) "
                    f"in [{best_match.source_section}] section: \"{best_match.passage_text[:120]}...\""
                )
            else:
                explanation = f"No contextual evidence found above threshold {self.threshold:.2f} (best similarity: {best_score:.2f})."

            criterion_results.append(
                CriterionEvaluationResult(
                    criterion_id=crit.id,
                    criterion_name=crit.criterion_name,
                    criterion_type=crit.criterion_type,
                    weight=crit.weight,
                    match_status=match_status,
                    score=round(scaled_score, 1),
                    matched_terms=[crit.criterion_name] if best_tier in (SemanticSimilarityTier.STRONG, SemanticSimilarityTier.POSSIBLE) else [],
                    supporting_evidence=supporting_texts,
                    evidence_sources=[best_match.source_section] if best_match else [],
                    matching_method="semantic_similarity",
                    explanation=explanation,
                    confidence=best_score,
                    semantic_score=best_score,
                    similarity_tier=best_tier,
                    top_passages=top_passages_dicts,
                )
            )

            if best_match and best_match.similarity_score >= self.threshold:
                match_type_enum = (
                    MatchType.EXACT if best_tier == SemanticSimilarityTier.STRONG else MatchType.PARTIAL
                )
                evidence_records.append(
                    EvaluationEvidence(
                        candidate_id=candidate.id,
                        criterion_id=crit.id,
                        supporting_text=best_match.passage_text,
                        match_type=match_type_enum,
                        evidence_source=best_match.source_section,
                        evaluation_status="EVALUATED",
                        explanation=explanation,
                    )
                )

        return criterion_results, evidence_records
