
import json
from typing import Any, Dict, List, Optional
import numpy as np

from core.analytics.models import SessionComparisonAnalytics
from core.storage.database import Database
from core.storage.eval_repository import EvaluationRecordRepository
from core.storage.repositories import CandidateRepository, JobRepository, SessionRepository
from core.storage.scoring_repository import ScoringRecordRepository
from core.storage.shortlist_repository import ShortlistRepository
from core.utils.logger import logger


class SessionComparisonAnalyticsService:

    def __init__(self, db: Database):
        self.db = db
        self.session_repo = SessionRepository(db)
        self.job_repo = JobRepository(db)
        self.candidate_repo = CandidateRepository(db)
        self.scoring_repo = ScoringRecordRepository(db)
        self.eval_repo = EvaluationRecordRepository(db)
        self.shortlist_repo = ShortlistRepository(db)

    def compare_sessions(self, session_ids: List[str]) -> SessionComparisonAnalytics:
        if not session_ids or len(session_ids) < 2:
            raise ValueError("Session comparison requires at least 2 sessions.")
        if len(session_ids) > 5:
            raise ValueError("Session comparison supports up to 5 sessions simultaneously.")

        sessions = [self.session_repo.get(sid) for sid in session_ids]
        missing = [sid for sid, s in zip(session_ids, sessions) if not s]
        if missing:
            raise ValueError(f"Screening Sessions not found: {missing}")

        session_names = {s.id: s.session_name for s in sessions}
        job_ids = {s.id: s.job_id for s in sessions}
        jobs = {s.id: self.job_repo.get(s.job_id) for s in sessions}
        job_titles = {s.id: jobs[s.id].title if jobs[s.id] else "General Position" for s in sessions}

        warnings: List[str] = []
        unique_jobs = set(job_ids.values())
        if len(unique_jobs) > 1:
            warnings.append(
                f"Cross-Job Warning: Compared sessions evaluate {len(unique_jobs)} different job requisitions "
                f"({', '.join(set(job_titles.values()))}). Criteria and baseline scores reflect different role expectations."
            )

        session_scoring: Dict[str, List[Any]] = {}
        session_configs: Dict[str, str] = {}
        for s in sessions:
            recs = self.scoring_repo.list_by_session(s.id)
            session_scoring[s.id] = recs
            if recs:
                session_configs[s.id] = recs[0].scoring_config_version
            else:
                session_configs[s.id] = "v1.0"

        unique_versions = set(session_configs.values())
        if len(unique_versions) > 1:
            warnings.append(
                f"Config Version Discrepancy: Sessions were evaluated with different scoring configuration versions "
                f"({', '.join(unique_versions)}). Direct numerical point comparisons may have different weight bases."
            )

        is_compatible = (len(unique_jobs) == 1) and (len(unique_versions) == 1)

        comparison_rows: List[Dict[str, Any]] = []
        all_criteria_by_session: Dict[str, Dict[str, List[float]]] = {}

        for s in sessions:
            sc_recs = session_scoring[s.id]
            valid_scores = [r.overall_score for r in sc_recs if r.overall_score is not None]
            coverage_vals = [r.evidence_coverage for r in sc_recs]

            shortlist_counts = self.shortlist_repo.get_status_counts(s.id)
            shortlisted_count = shortlist_counts.get("SHORTLISTED", 0)

            total_enrolled = s.candidate_count
            conversion_pct = (
                round((shortlisted_count / max(1, total_enrolled)) * 100.0, 1)
                if total_enrolled > 0
                else 0.0
            )

            comparison_rows.append({
                "session_id": s.id,
                "session_name": s.session_name,
                "job_title": job_titles[s.id],
                "total_enrolled": total_enrolled,
                "scored_count": len(valid_scores),
                "mean_score": round(float(np.mean(valid_scores)), 2) if valid_scores else 0.0,
                "median_score": round(float(np.median(valid_scores)), 2) if valid_scores else 0.0,
                "mean_coverage": round(float(np.mean(coverage_vals)), 1) if coverage_vals else 0.0,
                "shortlisted_count": shortlisted_count,
                "shortlist_conversion_rate": conversion_pct,
                "config_version": session_configs[s.id],
            })

            all_criteria_by_session[s.id] = {}
            for r in sc_recs:
                for cc in r.criterion_contributions:
                    c_name = cc.criterion_name
                    if c_name not in all_criteria_by_session[s.id]:
                        all_criteria_by_session[s.id][c_name] = []
                    all_criteria_by_session[s.id][c_name].append(cc.support_value)

        all_crit_names: set = set()
        for s_id, c_dict in all_criteria_by_session.items():
            all_crit_names.update(c_dict.keys())

        aligned_support_rates: Dict[str, Dict[str, float]] = {}
        for c_name in sorted(all_crit_names):
            aligned_support_rates[c_name] = {}
            for s in sessions:
                vals = all_criteria_by_session[s.id].get(c_name, [])
                if vals:
                    supp_rate = round((sum(1 for v in vals if v >= 0.5) / len(vals)) * 100.0, 1)
                    aligned_support_rates[c_name][s.id] = supp_rate
                else:
                    aligned_support_rates[c_name][s.id] = 0.0

        return SessionComparisonAnalytics(
            session_ids=session_ids,
            session_names=session_names,
            job_titles=job_titles,
            is_compatible=is_compatible,
            compatibility_warnings=warnings,
            comparison_summary_table=comparison_rows,
            aligned_criteria_support_rates=aligned_support_rates,
        )
