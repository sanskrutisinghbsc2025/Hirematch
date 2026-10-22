
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from backend.app.api.deps import get_orchestrator
from backend.app.api.schemas.analytics_schemas import (
    FunnelMetric,
    PortfolioAnalyticsResponse,
    ScoreDistributionMetrics,
    SessionAnalyticsResponse,
    SessionCompareRequest,
    SessionCompareResponse,
    SkillCoverageItem as SkillCoverageItemSchema,
)
from core.models.report_models import ExportFormat
from core.services.session_orchestrator import ScreeningOrchestrator
from core.utils.logger import logger

router = APIRouter(tags=["Recruitment Analytics"])


@router.get("/analytics/overview", response_model=PortfolioAnalyticsResponse)
def get_portfolio_analytics(
    orchestrator: ScreeningOrchestrator = Depends(get_orchestrator),
):
    try:
        port = orchestrator.get_portfolio_analytics()

        enrolled = port.total_resumes_enrolled
        processed = port.total_resumes_processed
        shortlisted = port.shortlist_funnel_totals.get("SHORTLISTED", 0)

        funnel = [
            FunnelMetric(
                stage_name="Uploaded Resumes",
                count=enrolled,
                conversion_rate=1.0 if enrolled > 0 else 0.0,
                dropoff_rate=0.0,
            ),
            FunnelMetric(
                stage_name="Processed & Evaluated",
                count=processed,
                conversion_rate=round(processed / max(1, enrolled), 2),
                dropoff_rate=round((enrolled - processed) / max(1, enrolled), 2),
            ),
            FunnelMetric(
                stage_name="Shortlisted",
                count=shortlisted,
                conversion_rate=round(shortlisted / max(1, processed), 2),
                dropoff_rate=round(max(0, processed - shortlisted) / max(1, processed), 2),
            ),
        ]

        top_skills = []
        try:
            with orchestrator.db.get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT criterion_name, COUNT(*) as frequency
                    FROM evaluation_criteria
                    GROUP BY LOWER(criterion_name)
                    ORDER BY frequency DESC
                    LIMIT 10;
                    """
                )
                top_skills = [{"skill": row["criterion_name"], "count": row["frequency"]} for row in cursor.fetchall()]
        except Exception as e:
            logger.warning(f"Failed to fetch top demanded skills: {e}")

        time_series = [
            {
                "period": t.period,
                "session_count": t.session_count,
                "resume_count": t.resume_count,
                "avg_score": t.avg_score or 0.0,
                "shortlist_count": t.shortlist_count,
            }
            for t in port.time_series_trends
        ]

        outcomes = {
            "COMPLETED": port.completed_processing_count,
            "PARTIAL": port.partial_processing_count,
            "FAILED": port.failed_processing_count,
            "DUPLICATE": port.duplicate_processing_count,
        }

        shortlist_rate = (shortlisted / max(1, processed)) if processed > 0 else 0.0

        strong_matches_count = 0
        potential_matches_count = 0
        strong_match_rate = 0.0
        potential_match_rate = 0.0
        portfolio_avg_score = round(port.overall_mean_score or 0.0, 1)

        try:
            with orchestrator.db.get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT overall_score
                    FROM (
                        SELECT csr.overall_score,
                               ROW_NUMBER() OVER (PARTITION BY sc.session_id, sc.candidate_id ORDER BY csr.id DESC) as rn
                        FROM session_candidates sc
                        JOIN candidate_scoring_records csr ON sc.session_id = csr.session_id AND sc.candidate_id = csr.candidate_id
                        WHERE csr.overall_score IS NOT NULL
                    )
                    WHERE rn = 1;
                    """
                )
                score_rows = cursor.fetchall()
                if score_rows:
                    active_scores = [float(r["overall_score"]) for r in score_rows]
                    portfolio_avg_score = round(sum(active_scores) / len(active_scores), 1)
                    strong_matches_count = sum(1 for s in active_scores if s >= 80.0)
                    potential_matches_count = sum(1 for s in active_scores if 60.0 <= s < 80.0)
                    strong_match_rate = round(strong_matches_count / len(active_scores), 3)
                    potential_match_rate = round(potential_matches_count / len(active_scores), 3)
        except Exception as e:
            logger.warning(f"Failed to fetch portfolio tier metrics: {e}")

        return PortfolioAnalyticsResponse(
            total_sessions=port.total_sessions,
            total_resumes=port.total_resumes_enrolled,
            total_candidates=port.total_resumes_enrolled,
            evaluated_resumes=port.total_resumes_processed,
            avg_composite_score=portfolio_avg_score,
            avg_shortlist_rate=round(shortlist_rate, 3),
            strong_match_rate=strong_match_rate,
            strong_matches_count=strong_matches_count,
            potential_match_rate=potential_match_rate,
            potential_matches_count=potential_matches_count,
            avg_evidence_coverage=75.0,
            overall_funnel=funnel,
            shortlist_distribution=port.shortlist_funnel_totals,
            top_demanded_skills=top_skills,
            time_series_batches=time_series,
            processing_outcomes=outcomes,
        )
    except Exception as e:
        logger.error(f"Error computing portfolio analytics: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to compute portfolio analytics: {str(e)}",
        )


@router.get("/sessions/{session_id}/analytics", response_model=SessionAnalyticsResponse)
def get_session_analytics(
    session_id: str,
    orchestrator: ScreeningOrchestrator = Depends(get_orchestrator),
):
    try:
        analytics = orchestrator.get_session_analytics_profile(session_id=session_id)

        enrolled = analytics.total_enrolled
        scored = analytics.total_scored
        shortlisted = analytics.shortlist_counts.get("SHORTLISTED", 0)

        funnel = [
            FunnelMetric(
                stage_name="Uploaded Resumes",
                count=enrolled,
                conversion_rate=1.0 if enrolled > 0 else 0.0,
                dropoff_rate=0.0,
            ),
            FunnelMetric(
                stage_name="Scored Candidates",
                count=scored,
                conversion_rate=round(scored / max(1, enrolled), 2),
                dropoff_rate=round(analytics.unscorable_count / max(1, enrolled), 2),
            ),
            FunnelMetric(
                stage_name="Shortlisted",
                count=shortlisted,
                conversion_rate=round(shortlisted / max(1, scored), 2),
                dropoff_rate=round(max(0, scored - shortlisted) / max(1, scored), 2),
            ),
        ]

        median = analytics.score_median or 0.0
        iqr = analytics.score_iqr or 0.0
        p25 = max(0.0, round(median - (iqr / 2.0), 1))
        p75 = min(100.0, round(p25 + iqr, 1))

        dist = ScoreDistributionMetrics(
            mean=analytics.score_mean or 0.0,
            median=median,
            std_dev=analytics.score_std_dev or 0.0,
            p25=p25,
            p75=p75,
            iqr=iqr,
            min=0.0,
            max=100.0,
        )

        histogram = [{"range": k, "count": v} for k, v in analytics.score_buckets.items()]

        skill_items = [
            SkillCoverageItemSchema(
                canonical_name=s.canonical_name,
                pool_coverage_percentage=s.pool_coverage_percentage,
                candidate_evidence_count=s.candidate_evidence_count,
                requirement_type=s.requirement_type,
                category=s.category,
                gap_status=s.gap_status.value if hasattr(s.gap_status, "value") else str(s.gap_status),
            )
            for s in analytics.skill_coverage
        ]

        acute_gaps = [
            s.canonical_name
            for s in analytics.skill_coverage
            if getattr(s.gap_status, "value", str(s.gap_status)) == "ACUTE_GAP"
        ]

        strong_matches = 0
        potential_matches = 0
        under_review = 0
        avg_score = round(analytics.score_mean or 0.0, 1)

        try:
            with orchestrator.db.get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT overall_score
                    FROM (
                        SELECT csr.overall_score,
                               ROW_NUMBER() OVER (PARTITION BY csr.candidate_id ORDER BY csr.id DESC) as rn
                        FROM candidate_scoring_records csr
                        WHERE csr.session_id = ? AND csr.overall_score IS NOT NULL
                    )
                    WHERE rn = 1;
                    """,
                    (session_id,),
                )
                rows = cursor.fetchall()
                if not rows:
                    cursor = conn.execute(
                        """
                        SELECT s.overall_score
                        FROM session_candidates sc
                        JOIN candidates c ON sc.candidate_id = c.id
                        LEFT JOIN candidate_scores s ON c.id = s.candidate_id
                        WHERE sc.session_id = ? AND s.overall_score IS NOT NULL;
                        """,
                        (session_id,),
                    )
                    rows = cursor.fetchall()

                if rows:
                    scores_list = [float(row["overall_score"]) for row in rows]
                    avg_score = round(sum(scores_list) / len(scores_list), 1)
                    strong_matches = sum(1 for sc in scores_list if sc >= 80.0)
                    potential_matches = sum(1 for sc in scores_list if 60.0 <= sc < 80.0)
                    under_review = sum(1 for sc in scores_list if sc < 60.0)
        except Exception as e:
            logger.warning(f"Could not compute candidate tier counts: {e}")

        insights_list = [i.to_dict() if hasattr(i, "to_dict") else i for i in (analytics.insights or [])]

        return SessionAnalyticsResponse(
            session_id=analytics.session_id,
            session_name=analytics.session_name,
            job_title=analytics.job_title,
            scoring_config_version=analytics.scoring_config_version,
            total_candidates=analytics.total_enrolled,
            evaluated_candidates=analytics.total_scored,
            funnel_metrics=funnel,
            score_distribution=dist,
            score_histogram=histogram,
            shortlist_counts=analytics.shortlist_counts,
            skill_coverage=skill_items,
            acute_gaps=acute_gaps,
            discrepancy_count=len(acute_gaps),
            conflicting_candidates_count=0,
            traceable_insights=insights_list,
            average_score=avg_score,
            strong_matches=strong_matches,
            potential_matches=potential_matches,
            under_review=under_review,
        )
    except ValueError as e:
        logger.warning(f"Session not found for analytics: {e}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error computing session analytics: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to compute session analytics: {str(e)}",
        )


@router.get("/sessions/{session_id}/criterion-analytics")
def get_criterion_analytics(
    session_id: str,
    orchestrator: ScreeningOrchestrator = Depends(get_orchestrator),
):
    try:
        items = orchestrator.get_criterion_analytics(session_id=session_id)
        return [item.to_dict() if hasattr(item, "to_dict") else item for item in items]
    except Exception as e:
        logger.error(f"Error computing criterion analytics: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to compute criterion analytics: {str(e)}",
        )


@router.get("/sessions/{session_id}/skill-coverage")
def get_skill_coverage(
    session_id: str,
    orchestrator: ScreeningOrchestrator = Depends(get_orchestrator),
):
    try:
        items = orchestrator.get_skill_coverage_analytics(session_id=session_id)
        return [
            SkillCoverageItemSchema(
                canonical_name=s.canonical_name,
                pool_coverage_percentage=s.pool_coverage_percentage,
                candidate_evidence_count=s.candidate_evidence_count,
                requirement_type=s.requirement_type,
                category=s.category,
                gap_status=s.gap_status.value if hasattr(s.gap_status, "value") else str(s.gap_status),
            )
            for s in items
        ]
    except Exception as e:
        logger.error(f"Error computing skill coverage: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to compute skill coverage: {str(e)}",
        )


@router.post("/analytics/compare-sessions", response_model=SessionCompareResponse)
def compare_sessions(
    payload: SessionCompareRequest,
    orchestrator: ScreeningOrchestrator = Depends(get_orchestrator),
):
    try:
        comp = orchestrator.compare_sessions_analytics(session_ids=payload.session_ids)
        return SessionCompareResponse(
            is_compatible=comp.is_compatible,
            compatibility_warnings=comp.compatibility_warnings,
            comparison_summary_table=comp.comparison_summary_table,
            aligned_criteria_support_rates=comp.aligned_criteria_support_rates,
            session_names=comp.session_names,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error comparing sessions: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to compare sessions: {str(e)}",
        )


@router.get("/analytics/export")
def export_analytics(
    session_id: Optional[str] = Query(None),
    format: str = Query("csv", pattern="^(csv|xlsx)$"),
    orchestrator: ScreeningOrchestrator = Depends(get_orchestrator),
):
    try:
        exp_fmt = ExportFormat.XLSX if format.lower() == "xlsx" else ExportFormat.CSV
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if exp_fmt == ExportFormat.XLSX else "text/csv"

        if session_id:
            content, filename = orchestrator.export_session_analytics(session_id=session_id, export_format=exp_fmt)
        else:
            content, filename = orchestrator.export_portfolio_analytics()

        return Response(
            content=content,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error exporting analytics: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export analytics: {str(e)}",
        )
