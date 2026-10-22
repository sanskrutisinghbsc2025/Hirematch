
from typing import Any, Dict, List, Optional
import numpy as np

from core.models.enums import ShortlistReviewStatus
from core.storage.database import Database
from core.storage.eval_repository import EvaluationRecordRepository
from core.storage.repositories import CandidateRepository, SessionRepository
from core.storage.scoring_repository import ScoringRecordRepository
from core.storage.shortlist_repository import ShortlistRepository
from core.utils.logger import logger


class RecruitmentInsightsService:

    def __init__(self, db: Database):
        self.db = db
        self.session_repo = SessionRepository(db)
        self.candidate_repo = CandidateRepository(db)
        self.scoring_repo = ScoringRecordRepository(db)
        self.eval_repo = EvaluationRecordRepository(db)
        self.shortlist_repo = ShortlistRepository(db)

    def get_session_insights(self, session_id: str) -> Dict[str, Any]:
        session = self.session_repo.get(session_id)
        if not session:
            raise ValueError(f"Screening Session '{session_id}' not found.")

        enrolled = self.candidate_repo.list_by_session(session_id)
        total_enrolled = len(enrolled)
        extracted_count = sum(1 for c in enrolled if c.get("session_status") in ("COMPLETED", "EVALUATED"))
        failed_count = sum(1 for c in enrolled if c.get("session_status") == "FAILED")

        scoring_records = self.scoring_repo.list_by_session(session_id)
        eval_records = self.eval_repo.list_by_session(session_id)

        valid_scores = [s.overall_score for s in scoring_records if s.overall_score is not None]
        if not valid_scores and eval_records:
            valid_scores = [e.overall_score for e in eval_records if e.overall_score is not None]

        score_stats: Dict[str, Any] = {
            "total_scored": len(valid_scores),
            "unscorable_count": total_enrolled - len(valid_scores),
            "mean": round(float(np.mean(valid_scores)), 2) if valid_scores else 0.0,
            "median": round(float(np.median(valid_scores)), 2) if valid_scores else 0.0,
            "percentiles": {
                "p25": round(float(np.percentile(valid_scores, 25)), 2) if valid_scores else 0.0,
                "p50": round(float(np.percentile(valid_scores, 50)), 2) if valid_scores else 0.0,
                "p75": round(float(np.percentile(valid_scores, 75)), 2) if valid_scores else 0.0,
                "p90": round(float(np.percentile(valid_scores, 90)), 2) if valid_scores else 0.0,
            },
        }

        crit_stats: Dict[str, Dict[str, Any]] = {}
        for s_rec in scoring_records:
            for cc in s_rec.criterion_contributions:
                c_name = cc.criterion_name
                if c_name not in crit_stats:
                    crit_stats[c_name] = {"supported": 0, "insufficient": 0, "conflicting": 0, "total": 0}
                crit_stats[c_name]["total"] += 1
                status_str = cc.match_status.value if hasattr(cc.match_status, "value") else str(cc.match_status)
                if status_str in ("SUPPORTED", "PARTIALLY_SUPPORTED"):
                    crit_stats[c_name]["supported"] += 1
                elif status_str in ("NOT_FOUND", "INSUFFICIENT_EVIDENCE"):
                    crit_stats[c_name]["insufficient"] += 1
                elif status_str == "CONFLICTING_EVIDENCE":
                    crit_stats[c_name]["conflicting"] += 1

        top_strengths = []
        top_gaps = []
        for name, stats in crit_stats.items():
            tot = stats["total"]
            if tot > 0:
                supp_pct = round((stats["supported"] / tot) * 100.0, 1)
                gap_pct = round((stats["insufficient"] / tot) * 100.0, 1)
                top_strengths.append({"criterion_name": name, "rate": supp_pct, "count": stats["supported"]})
                top_gaps.append({"criterion_name": name, "rate": gap_pct, "count": stats["insufficient"]})

        top_strengths.sort(key=lambda x: x["rate"], reverse=True)
        top_gaps.sort(key=lambda x: x["rate"], reverse=True)

        agreement_count = 0
        semantic_boost_count = 0
        conflict_detected_count = 0
        total_eval_crit_points = 0

        for e_rec in eval_records:
            for cr in e_rec.criterion_results:
                total_eval_crit_points += 1
                b_score = cr.baseline_score
                s_score = cr.semantic_score
                m_stat = cr.match_status.value if hasattr(cr.match_status, "value") else str(cr.match_status)

                if m_stat == "CONFLICTING_EVIDENCE":
                    conflict_detected_count += 1
                elif b_score is not None and s_score is not None:
                    if abs(b_score - s_score) < 0.20:
                        agreement_count += 1
                    elif s_score > b_score + 0.30:
                        semantic_boost_count += 1

        layer_agreement = {
            "total_evaluated_criteria_points": total_eval_crit_points,
            "layer_agreement_rate": round((agreement_count / max(1, total_eval_crit_points)) * 100.0, 1),
            "latent_semantic_discoveries": semantic_boost_count,
            "conflicts_flagged_for_review": conflict_detected_count,
        }

        shortlist_counts = self.shortlist_repo.get_status_counts(session_id)
        funnel = {
            "enrolled": total_enrolled,
            "extracted": extracted_count,
            "evaluated": len(valid_scores),
            "in_review": shortlist_counts.get(ShortlistReviewStatus.IN_REVIEW.value, 0),
            "shortlisted": shortlist_counts.get(ShortlistReviewStatus.SHORTLISTED.value, 0),
            "on_hold": shortlist_counts.get(ShortlistReviewStatus.ON_HOLD.value, 0),
            "not_shortlisted": shortlist_counts.get(ShortlistReviewStatus.NOT_SHORTLISTED.value, 0),
        }

        return {
            "session_id": session_id,
            "session_name": session.session_name,
            "score_statistics": score_stats,
            "top_candidate_strengths": top_strengths[:5],
            "top_pool_skill_gaps": top_gaps[:5],
            "layer_agreement_metrics": layer_agreement,
            "recruitment_funnel": funnel,
            "responsible_ai_disclaimer": (
                "Recruitment insights represent aggregate applicant pool distributions. "
                "They describe pool trends for this specific screening session and must not be interpreted "
                "as predictive candidate performance or demographic analytics."
            ),
        }
