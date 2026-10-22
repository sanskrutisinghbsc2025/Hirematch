
from datetime import datetime
import json
from typing import Any, Dict, List, Optional
import numpy as np

from core.analytics.criterion_service import CriterionAnalyticsService
from core.analytics.insights_generator import TraceableInsightsGenerator
from core.analytics.models import (
    AnalyticsFilter,
    SessionAnalytics,
)
from core.analytics.skill_service import SkillCoverageAnalyticsService
from core.storage.database import Database
from core.storage.eval_repository import EvaluationRecordRepository
from core.storage.repositories import CandidateRepository, JobRepository, SessionRepository
from core.storage.scoring_repository import ScoringRecordRepository
from core.storage.shortlist_repository import ShortlistRepository
from core.utils.logger import logger


class SessionAnalyticsService:

    def __init__(self, db: Database):
        self.db = db
        self.session_repo = SessionRepository(db)
        self.job_repo = JobRepository(db)
        self.candidate_repo = CandidateRepository(db)
        self.scoring_repo = ScoringRecordRepository(db)
        self.eval_repo = EvaluationRecordRepository(db)
        self.shortlist_repo = ShortlistRepository(db)

        self.skill_service = SkillCoverageAnalyticsService(db)
        self.criterion_service = CriterionAnalyticsService(db)
        self.insights_generator = TraceableInsightsGenerator(db)

    def get_session_analytics(
        self, session_id: str, filters: Optional[AnalyticsFilter] = None
    ) -> SessionAnalytics:
        session = self.session_repo.get(session_id)
        if not session:
            raise ValueError(f"Screening Session '{session_id}' not found.")

        job = self.job_repo.get(session.job_id)
        job_title = job.title if job else "General Position"

        enrolled_items = self.candidate_repo.list_by_session(session_id)
        total_enrolled = len(enrolled_items)

        failed_count = sum(1 for c in enrolled_items if c.get("session_status") == "FAILED")

        scoring_records = self.scoring_repo.list_by_session(session_id)
        eval_records = self.eval_repo.list_by_session(session_id)

        config_version = scoring_records[0].scoring_config_version if scoring_records else "v1.0"

        shortlist_records = {s.candidate_id: s for s in self.shortlist_repo.list_by_session(session_id)}

        filtered_scoring = []
        for s_rec in scoring_records:
            cid = s_rec.candidate_id
            score = s_rec.overall_score

            if filters:
                if filters.min_score is not None and score is not None and score < filters.min_score:
                    continue
                if filters.max_score is not None and score is not None and score > filters.max_score:
                    continue
                if filters.shortlist_status:
                    sl = shortlist_records.get(cid)
                    status_val = sl.review_status.value if sl else "NEEDS_REVIEW"
                    if status_val != filters.shortlist_status:
                        continue

            filtered_scoring.append(s_rec)

        valid_scores = [s.overall_score for s in filtered_scoring if s.overall_score is not None]
        if not valid_scores and not scoring_records and eval_records:
            valid_scores = [e.overall_score for e in eval_records if e.overall_score is not None]

        total_scored = len(valid_scores)
        unscorable_count = total_enrolled - total_scored

        score_mean = round(float(np.mean(valid_scores)), 2) if valid_scores else None
        score_median = round(float(np.median(valid_scores)), 2) if valid_scores else None
        score_std = round(float(np.std(valid_scores)), 2) if len(valid_scores) > 1 else 0.0
        score_var = round(float(np.var(valid_scores)), 2) if len(valid_scores) > 1 else 0.0

        score_iqr = 0.0
        is_clustered = False
        if len(valid_scores) >= 5:
            q25 = float(np.percentile(valid_scores, 25))
            q75 = float(np.percentile(valid_scores, 75))
            score_iqr = round(q75 - q25, 2)
            is_clustered = score_iqr < 12.0

        score_buckets = {"0-19": 0, "20-39": 40, "40-59": 0, "60-79": 0, "80-100": 0}
        score_buckets = {k: 0 for k in score_buckets}
        for sc in valid_scores:
            if sc < 20.0:
                score_buckets["0-19"] += 1
            elif sc < 40.0:
                score_buckets["20-39"] += 1
            elif sc < 60.0:
                score_buckets["40-59"] += 1
            elif sc < 80.0:
                score_buckets["60-79"] += 1
            else:
                score_buckets["80-100"] += 1

        coverages = [s.evidence_coverage for s in filtered_scoring]
        mean_coverage = round(float(np.mean(coverages)), 1) if coverages else 0.0

        cov_buckets = {"0-24%": 0, "25-49%": 0, "50-74%": 0, "75-100%": 0}
        for cv in coverages:
            if cv < 25.0:
                cov_buckets["0-24%"] += 1
            elif cv < 50.0:
                cov_buckets["25-49%"] += 1
            elif cv < 75.0:
                cov_buckets["50-74%"] += 1
            else:
                cov_buckets["75-100%"] += 1

        skill_coverage = self.skill_service.analyze_session_skills(session_id)
        criterion_analytics = self.criterion_service.analyze_session_criteria(session_id)

        insights = self.insights_generator.generate_insights(
            session_id=session_id,
            criterion_analytics=criterion_analytics,
            skill_coverage=skill_coverage,
            total_enrolled=total_enrolled,
            failed_count=failed_count,
            valid_scores=valid_scores,
        )

        shortlist_counts = self.shortlist_repo.get_status_counts(session_id)

        avg_proc_seconds = None
        c_at = session.created_at
        comp_at = session.completed_at
        if c_at and comp_at:
            try:
                dt_start = datetime.fromisoformat(c_at.replace("Z", "+00:00"))
                dt_end = datetime.fromisoformat(comp_at.replace("Z", "+00:00"))
                dur = (dt_end - dt_start).total_seconds()
                if dur > 0 and total_enrolled > 0:
                    avg_proc_seconds = round(dur / total_enrolled, 2)
            except Exception:
                pass

        return SessionAnalytics(
            session_id=session_id,
            session_name=session.session_name,
            job_id=session.job_id,
            job_title=job_title,
            total_enrolled=total_enrolled,
            total_scored=total_scored,
            unscorable_count=unscorable_count,
            score_mean=score_mean,
            score_median=score_median,
            score_std_dev=score_std,
            score_variance=score_var,
            score_iqr=score_iqr,
            is_tightly_clustered=is_clustered,
            score_buckets=score_buckets,
            evidence_coverage_mean=mean_coverage,
            coverage_buckets=cov_buckets,
            criterion_analytics=criterion_analytics,
            skill_coverage=skill_coverage,
            insights=insights,
            shortlist_counts=shortlist_counts,
            average_processing_seconds=avg_proc_seconds,
            scoring_config_version=config_version,
        )
