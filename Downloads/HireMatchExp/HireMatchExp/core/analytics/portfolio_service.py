
from datetime import datetime
import json
import sqlite3
from typing import Any, Dict, List, Optional
import numpy as np

from core.analytics.models import (
    AnalyticsFilter,
    PortfolioAnalytics,
    TimeSeriesPoint,
)
from core.models.enums import ProcessingStatus, ShortlistReviewStatus
from core.storage.database import Database
from core.utils.logger import logger


class PortfolioAnalyticsService:

    def __init__(self, db: Database):
        self.db = db

    def get_portfolio_analytics(
        self, filters: Optional[AnalyticsFilter] = None
    ) -> PortfolioAnalytics:
        filters = filters or AnalyticsFilter()

        query_sess = "SELECT * FROM screening_sessions WHERE 1=1"
        sess_params: List[Any] = []

        if filters.start_date:
            query_sess += " AND created_at >= ?"
            sess_params.append(filters.start_date)
        if filters.end_date:
            query_sess += " AND created_at <= ?"
            end_val = filters.end_date if "T" in filters.end_date else f"{filters.end_date}T23:59:59"
            sess_params.append(end_val)
        if filters.job_id:
            query_sess += " AND job_id = ?"
            sess_params.append(filters.job_id)
        if filters.session_ids:
            placeholders = ",".join("?" for _ in filters.session_ids)
            query_sess += f" AND id IN ({placeholders})"
            sess_params.extend(filters.session_ids)

        query_sess += " ORDER BY created_at ASC;"

        with self.db.get_connection() as conn:
            cursor = conn.execute(query_sess, tuple(sess_params))
            session_rows = cursor.fetchall()

        total_sessions = len(session_rows)
        matched_session_ids = [r["id"] for r in session_rows]

        with self.db.get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(DISTINCT job_id) as cnt FROM screening_sessions;")
            active_jobs_count = cursor.fetchone()["cnt"] if session_rows else 0

        if not matched_session_ids:
            return PortfolioAnalytics(
                total_sessions=0,
                total_resumes_enrolled=0,
                total_resumes_processed=0,
                completed_processing_count=0,
                partial_processing_count=0,
                failed_processing_count=0,
                duplicate_processing_count=0,
                active_jobs_count=active_jobs_count,
            )

        sc_placeholders = ",".join("?" for _ in matched_session_ids)
        query_candidates = f"""
        SELECT sc.session_id, sc.candidate_id, sc.processing_status, c.processing_status as cand_proc_status
        FROM session_candidates sc
        LEFT JOIN candidates c ON sc.candidate_id = c.id
        WHERE sc.session_id IN ({sc_placeholders});
        """
        with self.db.get_connection() as conn:
            cursor = conn.execute(query_candidates, tuple(matched_session_ids))
            candidate_links = cursor.fetchall()

        total_resumes_enrolled = len(candidate_links)
        completed_count = 0
        failed_count = 0
        duplicate_count = 0
        partial_count = 0

        for r in candidate_links:
            status = r["processing_status"]
            if status == "PENDING" and r["cand_proc_status"] and r["cand_proc_status"] != "PENDING":
                status = r["cand_proc_status"]

            if status in ("COMPLETED", "EVALUATED"):
                completed_count += 1
            elif status == "FAILED":
                failed_count += 1
            elif status == "DUPLICATE":
                duplicate_count += 1
            else:
                partial_count += 1

        total_resumes_processed = completed_count + failed_count + duplicate_count

        session_durations: List[float] = []
        for r in session_rows:
            c_at = r["created_at"]
            comp_at = r["completed_at"]
            if c_at and comp_at:
                try:
                    dt_start = datetime.fromisoformat(c_at.replace("Z", "+00:00"))
                    dt_end = datetime.fromisoformat(comp_at.replace("Z", "+00:00"))
                    diff = (dt_end - dt_start).total_seconds()
                    if diff > 0:
                        session_durations.append(diff)
                except Exception:
                    pass

        avg_session_seconds = round(float(np.mean(session_durations)), 2) if session_durations else None
        avg_resume_seconds = None
        if avg_session_seconds and total_resumes_processed > 0:
            avg_resume_seconds = round(sum(session_durations) / max(1, total_resumes_processed), 2)

        query_scores = f"""
        SELECT overall_score
        FROM candidate_scoring_records
        WHERE session_id IN ({sc_placeholders})
        AND overall_score IS NOT NULL;
        """
        with self.db.get_connection() as conn:
            cursor = conn.execute(query_scores, tuple(matched_session_ids))
            score_rows = cursor.fetchall()

        valid_scores = [float(r["overall_score"]) for r in score_rows]
        overall_mean = round(float(np.mean(valid_scores)), 2) if valid_scores else None
        overall_median = round(float(np.median(valid_scores)), 2) if valid_scores else None

        score_quartiles = {
            "q1": round(float(np.percentile(valid_scores, 25)), 2) if valid_scores else 0.0,
            "q2": overall_median or 0.0,
            "q3": round(float(np.percentile(valid_scores, 75)), 2) if valid_scores else 0.0,
        }

        time_series_map: Dict[str, Dict[str, Any]] = {}
        query_ts_scores = f"""
        SELECT s.created_at, csr.overall_score
        FROM candidate_scoring_records csr
        JOIN screening_sessions s ON csr.session_id = s.id
        WHERE s.id IN ({sc_placeholders}) AND csr.overall_score IS NOT NULL;
        """
        with self.db.get_connection() as conn:
            cursor = conn.execute(query_ts_scores, tuple(matched_session_ids))
            ts_scores = cursor.fetchall()

        for s_row in session_rows:
            raw_date = s_row["created_at"][:10]
            try:
                dt = datetime.fromisoformat(s_row["created_at"].replace("Z", "+00:00"))
                period = f"{dt.year}-W{dt.isocalendar()[1]:02d}"
            except Exception:
                period = raw_date[:7]

            if period not in time_series_map:
                time_series_map[period] = {
                    "session_count": 0,
                    "resume_count": 0,
                    "scores": [],
                    "shortlist_count": 0,
                }
            time_series_map[period]["session_count"] += 1
            time_series_map[period]["resume_count"] += s_row["candidate_count"]

        for ts in ts_scores:
            try:
                dt = datetime.fromisoformat(ts["created_at"].replace("Z", "+00:00"))
                period = f"{dt.year}-W{dt.isocalendar()[1]:02d}"
            except Exception:
                period = ts["created_at"][:7]

            if period in time_series_map:
                time_series_map[period]["scores"].append(float(ts["overall_score"]))

        query_shortlists = f"""
        SELECT sl.review_status, s.created_at
        FROM shortlist_records sl
        JOIN screening_sessions s ON sl.session_id = s.id
        WHERE sl.session_id IN ({sc_placeholders});
        """
        shortlist_totals: Dict[str, int] = {st.value: 0 for st in ShortlistReviewStatus}
        with self.db.get_connection() as conn:
            cursor = conn.execute(query_shortlists, tuple(matched_session_ids))
            for sl_row in cursor.fetchall():
                st_val = sl_row["review_status"]
                shortlist_totals[st_val] = shortlist_totals.get(st_val, 0) + 1
                if st_val == ShortlistReviewStatus.SHORTLISTED.value:
                    try:
                        dt = datetime.fromisoformat(sl_row["created_at"].replace("Z", "+00:00"))
                        period = f"{dt.year}-W{dt.isocalendar()[1]:02d}"
                    except Exception:
                        period = sl_row["created_at"][:7]
                    if period in time_series_map:
                        time_series_map[period]["shortlist_count"] += 1

        time_series_trends = []
        for period in sorted(time_series_map.keys()):
            p_data = time_series_map[period]
            sc_list = p_data["scores"]
            p_avg = round(float(np.mean(sc_list)), 2) if sc_list else None
            time_series_trends.append(
                TimeSeriesPoint(
                    period=period,
                    session_count=p_data["session_count"],
                    resume_count=p_data["resume_count"],
                    avg_score=p_avg,
                    shortlist_count=p_data["shortlist_count"],
                )
            )

        return PortfolioAnalytics(
            total_sessions=total_sessions,
            total_resumes_enrolled=total_resumes_enrolled,
            total_resumes_processed=total_resumes_processed,
            completed_processing_count=completed_count,
            partial_processing_count=partial_count,
            failed_processing_count=failed_count,
            duplicate_processing_count=duplicate_count,
            average_session_processing_seconds=avg_session_seconds,
            average_resume_processing_seconds=avg_resume_seconds,
            overall_mean_score=overall_mean,
            overall_median_score=overall_median,
            score_quartiles=score_quartiles,
            time_series_trends=time_series_trends,
            shortlist_funnel_totals=shortlist_totals,
            active_jobs_count=active_jobs_count,
        )
