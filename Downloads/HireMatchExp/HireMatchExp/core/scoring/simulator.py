
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import uuid

from core.models.evaluation import CandidateEvaluationRecord
from core.models.scoring_models import (
    CandidateScoringRecord,
    RankedCandidate,
    ScoringConfiguration,
    ScoringCriterion,
)
from core.scoring.calculator import TransparentScoreCalculator
from core.scoring.ranker import DeterministicCandidateRanker
from core.utils.logger import logger


class RankingSensitivitySimulator:

    def __init__(
        self,
        calculator: Optional[TransparentScoreCalculator] = None,
        ranker: Optional[DeterministicCandidateRanker] = None,
    ):
        self.calculator = calculator or TransparentScoreCalculator()
        self.ranker = ranker or DeterministicCandidateRanker()

    def simulate_weight_changes(
        self,
        base_config: ScoringConfiguration,
        evaluation_records: List[CandidateEvaluationRecord],
        new_weights: Dict[str, float],
        candidate_meta: Optional[Dict[str, Tuple[str, str]]] = None,
    ) -> Dict[str, Any]:
        sim_config = deepcopy(base_config)
        sim_config.id = f"sim_{uuid.uuid4().hex[:8]}"
        sim_config.name = f"{base_config.name} (Simulation)"

        for crit in sim_config.criteria:
            if crit.id in new_weights:
                crit.weight = max(0.0, float(new_weights[crit.id]))
            elif crit.criterion_name in new_weights:
                crit.weight = max(0.0, float(new_weights[crit.criterion_name]))

        validation_errors = sim_config.validate_configuration()
        if validation_errors:
            return {
                "success": False,
                "errors": validation_errors,
                "simulated_candidates": [],
                "rank_changers_count": 0,
            }

        orig_scoring_records = [
            self.calculator.calculate_score(rec, base_config)
            for rec in evaluation_records
        ]
        orig_ranked = self.ranker.rank_candidates(
            scoring_records=orig_scoring_records,
            config=base_config,
            candidate_meta=candidate_meta,
        )
        orig_rank_map = {c.candidate_id: c.rank for c in orig_ranked}
        orig_score_map = {c.candidate_id: c.overall_score for c in orig_ranked}

        sim_scoring_records = [
            self.calculator.calculate_score(rec, sim_config)
            for rec in evaluation_records
        ]
        sim_ranked = self.ranker.rank_candidates(
            scoring_records=sim_scoring_records,
            config=sim_config,
            candidate_meta=candidate_meta,
        )

        simulated_candidates: List[Dict[str, Any]] = []
        rank_changers = 0

        for cand in sim_ranked:
            cid = cand.candidate_id
            orig_r = orig_rank_map.get(cid, 0)
            sim_r = cand.rank
            orig_s = orig_score_map.get(cid)
            sim_s = cand.overall_score

            if orig_r > 0 and sim_r > 0:
                rank_delta = orig_r - sim_r
            else:
                rank_delta = 0

            score_delta = round((sim_s - orig_s), 2) if (sim_s is not None and orig_s is not None) else 0.0

            if rank_delta != 0:
                rank_changers += 1

            simulated_candidates.append({
                "candidate_id": cid,
                "candidate_name": cand.candidate_name,
                "filename": cand.filename,
                "original_rank": orig_r,
                "simulated_rank": sim_r,
                "rank_delta": rank_delta,
                "original_score": orig_s,
                "simulated_score": sim_s,
                "score_delta": score_delta,
                "evidence_coverage": cand.evidence_coverage,
                "is_tied": cand.is_tied,
            })

        gainers = sorted([c for c in simulated_candidates if c["rank_delta"] > 0], key=lambda x: x["rank_delta"], reverse=True)
        droppers = sorted([c for c in simulated_candidates if c["rank_delta"] < 0], key=lambda x: x["rank_delta"])

        return {
            "success": True,
            "simulated_config": sim_config,
            "simulated_candidates": simulated_candidates,
            "rank_changers_count": rank_changers,
            "total_candidates": len(simulated_candidates),
            "biggest_gainers": gainers[:5],
            "biggest_droppers": droppers[:5],
        }

    def create_new_version_from_simulation(
        self,
        base_config: ScoringConfiguration,
        simulated_weights: Dict[str, float],
        new_version_label: str,
        notes: str = "",
    ) -> ScoringConfiguration:
        new_config = deepcopy(base_config)
        new_config.id = str(uuid.uuid4())
        new_config.version = new_version_label
        new_config.name = f"{base_config.name} ({new_version_label})"
        new_config.notes = notes
        new_config.created_at = datetime.now(timezone.utc).isoformat()

        for crit in new_config.criteria:
            if crit.id in simulated_weights:
                crit.weight = max(0.0, float(simulated_weights[crit.id]))
            elif crit.criterion_name in simulated_weights:
                crit.weight = max(0.0, float(simulated_weights[crit.criterion_name]))
            crit.config_version = new_version_label

        return new_config
