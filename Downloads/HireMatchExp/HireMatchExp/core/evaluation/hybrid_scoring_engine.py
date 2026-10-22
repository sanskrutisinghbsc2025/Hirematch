
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from core.evaluation.baseline_evaluator import BaselineCandidateEvaluator
from core.evaluation.scoring_engine import TransparentScoringEngine
from core.evaluation.semantic_evaluator import SemanticCandidateEvaluator
from core.models.candidate import Candidate
from core.models.enums import CriterionType, EvaluationMode, MatchStatus, ScoreStatus, SemanticSimilarityTier
from core.models.evaluation import (
    CandidateScore,
    CriterionEvaluationResult,
    EvaluationCriterion,
    EvaluationEvidence,
)
from core.models.job import Job
from core.utils.logger import logger


class HybridScoringEngine:

    def __init__(
        self,
        baseline_evaluator: Optional[BaselineCandidateEvaluator] = None,
        semantic_evaluator: Optional[SemanticCandidateEvaluator] = None,
        scoring_engine: Optional[TransparentScoringEngine] = None,
        baseline_weight: float = 0.5,
        config_version: str = "v2.0-hybrid",
    ):
        self.baseline_evaluator = baseline_evaluator or BaselineCandidateEvaluator()
        self.semantic_evaluator = semantic_evaluator
        self.scoring_engine = scoring_engine or TransparentScoringEngine(config_version=config_version)
        self.baseline_weight = max(0.0, min(1.0, baseline_weight))
        self.config_version = config_version

    def evaluate_candidate(
        self,
        candidate: Candidate,
        job: Job,
        criteria: List[EvaluationCriterion],
        mode: EvaluationMode = EvaluationMode.COMBINED,
        structured_data: Optional[Dict[str, Any]] = None,
        semantic_model_name: str = "all-MiniLM-L6-v2",
    ) -> Tuple[CandidateScore, List[EvaluationEvidence]]:
        if mode in (EvaluationMode.SEMANTIC, EvaluationMode.COMBINED) and self.semantic_evaluator is None:
            logger.warning(
                f"Semantic evaluator is not configured. Falling back from {mode.value} to BASELINE mode."
            )
            mode = EvaluationMode.BASELINE

        if mode == EvaluationMode.BASELINE:
            return self._evaluate_baseline_mode(
                candidate=candidate,
                job=job,
                criteria=criteria,
                structured_data=structured_data,
            )
        elif mode == EvaluationMode.SEMANTIC:
            return self._evaluate_semantic_mode(
                candidate=candidate,
                job=job,
                criteria=criteria,
                structured_data=structured_data,
                semantic_model_name=semantic_model_name,
            )
        else:
            return self._evaluate_combined_mode(
                candidate=candidate,
                job=job,
                criteria=criteria,
                structured_data=structured_data,
                semantic_model_name=semantic_model_name,
            )

    def _evaluate_baseline_mode(
        self,
        candidate: Candidate,
        job: Job,
        criteria: List[EvaluationCriterion],
        structured_data: Optional[Dict[str, Any]] = None,
    ) -> Tuple[CandidateScore, List[EvaluationEvidence]]:
        crit_results, evidence = self.baseline_evaluator.evaluate_candidate_detailed(
            candidate=candidate,
            job=job,
            criteria=criteria,
            structured_data=structured_data,
        )
        score = self.scoring_engine.aggregate_results(
            candidate_id=candidate.id,
            criteria=criteria,
            criterion_results=crit_results,
        )
        score.criterion_scores["evaluation_mode"] = EvaluationMode.BASELINE.value
        score.criterion_scores["baseline_score"] = score.overall_score
        return score, evidence

    def _evaluate_semantic_mode(
        self,
        candidate: Candidate,
        job: Job,
        criteria: List[EvaluationCriterion],
        structured_data: Optional[Dict[str, Any]],
        semantic_model_name: str,
    ) -> Tuple[CandidateScore, List[EvaluationEvidence]]:
        crit_results, evidence = self.semantic_evaluator.evaluate_candidate_detailed(
            candidate=candidate,
            job=job,
            criteria=criteria,
            structured_data=structured_data,
        )
        score = self.scoring_engine.aggregate_results(
            candidate_id=candidate.id,
            criteria=criteria,
            criterion_results=crit_results,
        )
        score.criterion_scores["evaluation_mode"] = EvaluationMode.SEMANTIC.value
        score.criterion_scores["semantic_score"] = score.overall_score
        score.criterion_scores["semantic_model"] = semantic_model_name
        return score, evidence

    def _evaluate_combined_mode(
        self,
        candidate: Candidate,
        job: Job,
        criteria: List[EvaluationCriterion],
        structured_data: Optional[Dict[str, Any]],
        semantic_model_name: str,
    ) -> Tuple[CandidateScore, List[EvaluationEvidence]]:
        base_results, base_evidence = self.baseline_evaluator.evaluate_candidate_detailed(
            candidate=candidate,
            job=job,
            criteria=criteria,
            structured_data=structured_data,
        )
        sem_results, sem_evidence = self.semantic_evaluator.evaluate_candidate_detailed(
            candidate=candidate,
            job=job,
            criteria=criteria,
            structured_data=structured_data,
        )

        base_map = {r.criterion_id: r for r in base_results}
        sem_map = {r.criterion_id: r for r in sem_results}

        combined_crit_results: List[CriterionEvaluationResult] = []
        all_evidence: List[EvaluationEvidence] = list(base_evidence)

        existing_keys = {(e.criterion_id, e.supporting_text[:50]) for e in all_evidence}
        for se in sem_evidence:
            k = (se.criterion_id, se.supporting_text[:50])
            if k not in existing_keys:
                all_evidence.append(se)
                existing_keys.add(k)

        w_base = self.baseline_weight
        w_sem = 1.0 - w_base

        for crit in criteria:
            if not crit.is_enabled:
                continue

            b_res = base_map.get(crit.id)
            s_res = sem_map.get(crit.id)

            b_score = b_res.score if b_res else 0.0
            s_score = s_res.score if s_res else 0.0

            fused_score = (w_base * b_score) + (w_sem * s_score)

            if fused_score >= 70.0 or (b_res and b_res.match_status == MatchStatus.SUPPORTED):
                fused_status = MatchStatus.SUPPORTED
            elif fused_score >= 45.0 or (b_res and b_res.match_status == MatchStatus.PARTIALLY_SUPPORTED):
                fused_status = MatchStatus.PARTIALLY_SUPPORTED
            elif fused_score > 0.0:
                fused_status = MatchStatus.INSUFFICIENT_EVIDENCE
            else:
                fused_status = MatchStatus.NOT_FOUND

            sup_ev = []
            ev_sources = []
            matched_terms = []
            if b_res:
                sup_ev.extend(b_res.supporting_evidence)
                ev_sources.extend(b_res.evidence_sources)
                matched_terms.extend(b_res.matched_terms)
            if s_res:
                for p in s_res.supporting_evidence:
                    if p not in sup_ev:
                        sup_ev.append(p)
                for src in s_res.evidence_sources:
                    if src not in ev_sources:
                        ev_sources.append(src)

            exp_parts = []
            if b_res and b_res.score > 0:
                exp_parts.append(f"Baseline: {b_res.explanation}")
            if s_res and s_res.semantic_score and s_res.semantic_score > 0.30:
                exp_parts.append(f"Semantic AI: {s_res.explanation}")
            if not exp_parts:
                merged_exp = f"No evidence found across baseline keywords or semantic embeddings for '{crit.criterion_name}'."
            else:
                merged_exp = " | ".join(exp_parts)

            combined_crit_results.append(
                CriterionEvaluationResult(
                    criterion_id=crit.id,
                    criterion_name=crit.criterion_name,
                    criterion_type=crit.criterion_type,
                    weight=crit.weight,
                    match_status=fused_status,
                    score=round(fused_score, 1),
                    matched_terms=list(set(matched_terms)),
                    supporting_evidence=sup_ev,
                    evidence_sources=list(set(ev_sources)),
                    matching_method="hybrid_fusion",
                    explanation=merged_exp,
                    confidence=max((b_res.confidence if b_res else 0.0), (s_res.confidence if s_res else 0.0)),
                    semantic_score=s_res.semantic_score if s_res else None,
                    similarity_tier=s_res.similarity_tier if s_res else None,
                    top_passages=s_res.top_passages if s_res else [],
                )
            )

        base_cand_score = self.scoring_engine.aggregate_results(candidate.id, criteria, base_results)
        sem_cand_score = self.scoring_engine.aggregate_results(candidate.id, criteria, sem_results)
        final_cand_score = self.scoring_engine.aggregate_results(candidate.id, criteria, combined_crit_results)

        final_cand_score.criterion_scores["evaluation_mode"] = EvaluationMode.COMBINED.value
        final_cand_score.criterion_scores["baseline_score"] = base_cand_score.overall_score
        final_cand_score.criterion_scores["semantic_score"] = sem_cand_score.overall_score
        final_cand_score.criterion_scores["combined_score"] = final_cand_score.overall_score
        final_cand_score.criterion_scores["semantic_model"] = semantic_model_name

        return final_cand_score, all_evidence
