
import json
from typing import Any, Dict, List, Optional
import numpy as np

from core.analytics.models import CriterionAnalytics
from core.storage.database import Database
from core.storage.eval_repository import EvaluationRecordRepository
from core.storage.scoring_repository import ScoringRecordRepository
from core.utils.logger import logger


class CriterionAnalyticsService:

    def __init__(self, db: Database):
        self.db = db
        self.scoring_repo = ScoringRecordRepository(db)
        self.eval_repo = EvaluationRecordRepository(db)

    def analyze_session_criteria(self, session_id: str) -> List[CriterionAnalytics]:
        scoring_records = self.scoring_repo.list_by_session(session_id)
        eval_records = self.eval_repo.list_by_session(session_id)

        if not scoring_records and not eval_records:
            return []

        eval_divergence_map: Dict[str, Dict[str, Dict[str, float]]] = {}
        for e_rec in eval_records:
            cid = e_rec.candidate_id
            eval_divergence_map[cid] = {}
            for cr in e_rec.criterion_results:
                c_key = cr.criterion_name.strip().lower()
                eval_divergence_map[cid][c_key] = {
                    "baseline": cr.baseline_score,
                    "semantic": cr.semantic_score,
                }

        crit_groups: Dict[str, Dict[str, Any]] = {}

        for s_rec in scoring_records:
            cid = s_rec.candidate_id
            for cc in s_rec.criterion_contributions:
                c_id = cc.criterion_id
                c_name = cc.criterion_name
                c_key = c_name.strip().lower()

                if c_id not in crit_groups:
                    crit_groups[c_id] = {
                        "criterion_id": c_id,
                        "criterion_name": c_name,
                        "category": cc.category.value if hasattr(cc.category, "value") else str(cc.category),
                        "criterion_type": cc.criterion_type.value if hasattr(cc.criterion_type, "value") else str(cc.criterion_type),
                        "configured_weight": cc.configured_weight,
                        "support_values": [],
                        "normalized_points": [],
                        "supported_count": 0,
                        "partially_supported_count": 0,
                        "insufficient_count": 0,
                        "conflicting_count": 0,
                        "divergences": [],
                        "semantic_boosts": 0,
                    }

                group = crit_groups[c_id]
                group["support_values"].append(cc.support_value)
                group["normalized_points"].append(cc.normalized_contribution)

                m_stat = cc.match_status.value if hasattr(cc.match_status, "value") else str(cc.match_status)
                if m_stat == "SUPPORTED":
                    group["supported_count"] += 1
                elif m_stat == "PARTIALLY_SUPPORTED":
                    group["partially_supported_count"] += 1
                elif m_stat in ("NOT_FOUND", "INSUFFICIENT_EVIDENCE"):
                    group["insufficient_count"] += 1
                elif m_stat == "CONFLICTING_EVIDENCE":
                    group["conflicting_count"] += 1

                div_info = eval_divergence_map.get(cid, {}).get(c_key)
                if div_info:
                    b_sc = div_info.get("baseline")
                    s_sc = div_info.get("semantic")
                    if b_sc is not None and s_sc is not None:
                        diff = abs(b_sc - s_sc)
                        group["divergences"].append(diff)
                        if s_sc >= b_sc + 0.30:
                            group["semantic_boosts"] += 1

        if not crit_groups and eval_records:
            for e_rec in eval_records:
                for cr in e_rec.criterion_results:
                    c_id = cr.criterion_id
                    c_name = cr.criterion_name
                    if c_id not in crit_groups:
                        crit_groups[c_id] = {
                            "criterion_id": c_id,
                            "criterion_name": c_name,
                            "category": "TECHNICAL_SKILL",
                            "criterion_type": "REQUIRED",
                            "configured_weight": cr.weight,
                            "support_values": [],
                            "normalized_points": [],
                            "supported_count": 0,
                            "partially_supported_count": 0,
                            "insufficient_count": 0,
                            "conflicting_count": 0,
                            "divergences": [],
                            "semantic_boosts": 0,
                        }
                    group = crit_groups[c_id]
                    s_val = getattr(cr, "score", getattr(cr, "synthesized_score", 0.0))
                    group["support_values"].append(s_val)
                    group["normalized_points"].append(s_val * cr.weight * 100.0)
                    m_stat = cr.match_status.value if hasattr(cr.match_status, "value") else str(cr.match_status)
                    if m_stat == "SUPPORTED":
                        group["supported_count"] += 1
                    elif m_stat == "PARTIALLY_SUPPORTED":
                        group["partially_supported_count"] += 1
                    elif m_stat in ("NOT_FOUND", "INSUFFICIENT_EVIDENCE"):
                        group["insufficient_count"] += 1
                    elif m_stat == "CONFLICTING_EVIDENCE":
                        group["conflicting_count"] += 1

                    b_sc = getattr(cr, "baseline_score", None)
                    s_sc = getattr(cr, "semantic_score", None)
                    if b_sc is not None and s_sc is not None:
                        diff = abs(b_sc - s_sc)
                        group["divergences"].append(diff)
                        if s_sc >= b_sc + 0.30:
                            group["semantic_boosts"] += 1

        results: List[CriterionAnalytics] = []
        for c_id, g in crit_groups.items():
            sup_vals = g["support_values"]
            tot = len(sup_vals)
            if tot == 0:
                continue

            mean_sup = round(float(np.mean(sup_vals)), 3)
            mean_pts = round(float(np.mean(g["normalized_points"])), 2)
            std = round(float(np.std(sup_vals)), 4)
            var = round(float(np.var(sup_vals)), 4)

            is_low_var = (std < 0.08) and (tot >= 3)

            cov_rate = round(((g["supported_count"] + g["partially_supported_count"]) / tot) * 100.0, 1)
            insuff_rate = round((g["insufficient_count"] / tot) * 100.0, 1)

            avg_div = round(float(np.mean(g["divergences"])), 3) if g["divergences"] else 0.0

            results.append(
                CriterionAnalytics(
                    criterion_id=c_id,
                    criterion_name=g["criterion_name"],
                    category=g["category"],
                    criterion_type=g["criterion_type"],
                    configured_weight=g["configured_weight"],
                    total_evaluated=tot,
                    mean_support_value=mean_sup,
                    mean_normalized_points=mean_pts,
                    std_dev=std,
                    variance=var,
                    is_low_variation=is_low_var,
                    supported_count=g["supported_count"],
                    partially_supported_count=g["partially_supported_count"],
                    insufficient_evidence_count=g["insufficient_count"],
                    conflicting_evidence_count=g["conflicting_count"],
                    evidence_coverage_rate=cov_rate,
                    insufficient_rate=insuff_rate,
                    keyword_vs_semantic_divergence=avg_div,
                    semantic_boost_count=g["semantic_boosts"],
                )
            )

        results.sort(key=lambda x: (x.configured_weight, x.variance), reverse=True)
        return results
