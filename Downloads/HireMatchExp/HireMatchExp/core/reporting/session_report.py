
import statistics
from typing import Any, Dict, List, Optional
import uuid

from core.models.enums import ProcessingStatus, ShortlistReviewStatus
from core.models.report_models import SessionSummaryReportData
from core.storage.database import Database
from core.storage.eval_repository import EvaluationConfigurationRepository, EvaluationRecordRepository
from core.storage.quality_repository import ResumeQualityRepository
from core.storage.repositories import (
    CandidateRepository,
    JobRepository,
    SessionRepository,
)
from core.storage.scoring_repository import ScoringRecordRepository
from core.storage.shortlist_repository import ShortlistRepository
from core.utils.logger import logger


class SessionSummaryReportGenerator:

    def __init__(self, db: Database):
        self.db = db
        self.session_repo = SessionRepository(db)
        self.job_repo = JobRepository(db)
        self.candidate_repo = CandidateRepository(db)
        self.eval_repo = EvaluationRecordRepository(db)
        self.scoring_repo = ScoringRecordRepository(db)
        self.shortlist_repo = ShortlistRepository(db)
        self.eval_config_repo = EvaluationConfigurationRepository(db)
        self.quality_repo = ResumeQualityRepository(db)

    def generate(self, session_id: str) -> SessionSummaryReportData:
        session = self.session_repo.get(session_id)
        if not session:
            raise ValueError(f"Screening Session '{session_id}' not found.")

        job = self.job_repo.get(session.job_id)
        job_title = job.title if job else "General Role"
        department = job.department if job else "General"

        enrolled_items = self.candidate_repo.list_by_session(session_id)
        total_enrolled = len(enrolled_items)

        completed_proc = 0
        failed_proc = 0
        pending_proc = 0
        duplicate_proc = 0

        for item in enrolled_items:
            status = item.get("session_status")
            cand = item.get("candidate")
            if (status is None or status == ProcessingStatus.PENDING) and cand:
                if cand.processing_status != ProcessingStatus.PENDING:
                    status = cand.processing_status
            if status in (ProcessingStatus.COMPLETED, ProcessingStatus.EVALUATED):
                completed_proc += 1
            elif status == ProcessingStatus.FAILED:
                failed_proc += 1
            elif status == ProcessingStatus.DUPLICATE:
                duplicate_proc += 1
            else:
                pending_proc += 1

        coverage_warning = None
        if completed_proc < total_enrolled:
            coverage_warning = (
                f"Coverage Limitation: {completed_proc} of {total_enrolled} enrolled resumes "
                f"have completed text extraction ({failed_proc} failed, {pending_proc} pending, {duplicate_proc} duplicate). "
                f"Aggregated metrics reflect only processed files."
            )

        scoring_records = self.scoring_repo.list_by_session(session_id)
        eval_records = self.eval_repo.list_by_session(session_id)
        shortlist_records = {s.candidate_id: s for s in self.shortlist_repo.list_by_session(session_id)}
        quality_map = self.quality_repo.get_session_map(session_id)

        scoring_by_cand = {s.candidate_id: s for s in scoring_records}
        eval_by_cand = {e.candidate_id: e for e in eval_records}

        completed_eval_count = len(scoring_records) if scoring_records else len(eval_records)

        scoring_cfg_id = scoring_records[0].scoring_config_id if scoring_records else "default"
        scoring_cfg_version = scoring_records[0].scoring_config_version if scoring_records else "v1.0"

        methods_used = ["Structured Extraction", "Baseline Rules"]
        if eval_records:
            methods_used.append("Semantic Embeddings")
            methods_used.append("Multi-Layer Conflict Synthesis")

        valid_scores = [s.overall_score for s in scoring_records if s.overall_score is not None]
        if not valid_scores and eval_records:
            valid_scores = [e.overall_score for e in eval_records if e.overall_score is not None]

        score_distribution: Dict[str, Any] = {
            "total_scored": len(valid_scores),
            "unscorable_count": completed_eval_count - len(valid_scores),
            "mean": round(statistics.mean(valid_scores), 2) if valid_scores else None,
            "median": round(statistics.median(valid_scores), 2) if valid_scores else None,
            "std_dev": round(statistics.stdev(valid_scores), 2) if len(valid_scores) > 1 else 0.0,
            "min": round(min(valid_scores), 2) if valid_scores else None,
            "max": round(max(valid_scores), 2) if valid_scores else None,
            "tiers": {
                "High Alignment (>= 80)": sum(1 for s in valid_scores if s >= 80.0),
                "Moderate Alignment (60 - 79)": sum(1 for s in valid_scores if 60.0 <= s < 80.0),
                "Low Alignment (< 60)": sum(1 for s in valid_scores if s < 60.0),
                "Insufficient Data": completed_eval_count - len(valid_scores),
            },
        }

        crit_aggregates: Dict[str, Dict[str, Any]] = {}
        for s_rec in scoring_records:
            for cc in s_rec.criterion_contributions:
                c_name = cc.criterion_name
                if c_name not in crit_aggregates:
                    crit_aggregates[c_name] = {
                        "criterion_name": c_name,
                        "category": cc.category.value if hasattr(cc.category, "value") else str(cc.category),
                        "criterion_type": cc.criterion_type.value if hasattr(cc.criterion_type, "value") else str(cc.criterion_type),
                        "total_evaluated": 0,
                        "supported_count": 0,
                        "partial_count": 0,
                        "insufficient_count": 0,
                        "conflicting_count": 0,
                    }
                crit_aggregates[c_name]["total_evaluated"] += 1
                st_val = cc.match_status.value if hasattr(cc.match_status, "value") else str(cc.match_status)
                if st_val == "SUPPORTED":
                    crit_aggregates[c_name]["supported_count"] += 1
                elif st_val == "PARTIALLY_SUPPORTED":
                    crit_aggregates[c_name]["partial_count"] += 1
                elif st_val in ("NOT_FOUND", "INSUFFICIENT_EVIDENCE"):
                    crit_aggregates[c_name]["insufficient_count"] += 1
                elif st_val == "CONFLICTING_EVIDENCE":
                    crit_aggregates[c_name]["conflicting_count"] += 1

        criterion_performance: List[Dict[str, Any]] = []
        for c_data in crit_aggregates.values():
            tot = c_data["total_evaluated"]
            if tot > 0:
                c_data["supported_pct"] = round((c_data["supported_count"] / tot) * 100.0, 1)
                c_data["partial_pct"] = round((c_data["partial_count"] / tot) * 100.0, 1)
                c_data["insufficient_pct"] = round((c_data["insufficient_count"] / tot) * 100.0, 1)
                c_data["conflicting_pct"] = round((c_data["conflicting_count"] / tot) * 100.0, 1)
            else:
                c_data["supported_pct"] = 0.0
                c_data["partial_pct"] = 0.0
                c_data["insufficient_pct"] = 0.0
                c_data["conflicting_pct"] = 0.0
            criterion_performance.append(c_data)

        criterion_performance.sort(key=lambda x: x["supported_pct"], reverse=True)

        shortlist_counts = {
            ShortlistReviewStatus.NEEDS_REVIEW.value: 0,
            ShortlistReviewStatus.IN_REVIEW.value: 0,
            ShortlistReviewStatus.SHORTLISTED.value: 0,
            ShortlistReviewStatus.NOT_SHORTLISTED.value: 0,
            ShortlistReviewStatus.ON_HOLD.value: 0,
        }
        for sl in shortlist_records.values():
            st_key = sl.review_status.value if hasattr(sl.review_status, "value") else str(sl.review_status)
            shortlist_counts[st_key] = shortlist_counts.get(st_key, 0) + 1

        candidate_summaries: List[Dict[str, Any]] = []
        for item in enrolled_items:
            cand = item["candidate"]
            s_rec = scoring_by_cand.get(cand.id)
            e_rec = eval_by_cand.get(cand.id)
            sl_rec = shortlist_records.get(cand.id)

            cand_score = s_rec.overall_score if s_rec else (e_rec.overall_score if e_rec else None)
            cand_cov = s_rec.evidence_coverage if s_rec else (e_rec.evidence_coverage if e_rec else 0.0)
            cand_status = sl_rec.review_status.value if sl_rec else "NEEDS_REVIEW"
            cand_notes = sl_rec.reviewer_notes if sl_rec else ""

            q_rec = quality_map.get(cand.id)
            cand_q_score = q_rec.overall_score if q_rec else None
            cand_q_label = q_rec.quality_label.value if q_rec else None

            candidate_summaries.append({
                "candidate_id": cand.id,
                "candidate_reference": f"Cand-{cand.id[:8].upper()}",
                "original_filename": cand.original_filename,
                "processing_status": item["session_status"].value if hasattr(item["session_status"], "value") else str(item["session_status"]),
                "overall_score": cand_score,
                "evidence_coverage": cand_cov,
                "review_status": cand_status,
                "reviewer_notes": cand_notes,
                "resume_quality_score": cand_q_score,
                "resume_quality_label": cand_q_label,
            })

        candidate_summaries.sort(key=lambda x: (x["overall_score"] is not None, x["overall_score"] or 0.0), reverse=True)

        warnings = []
        if failed_proc > 0:
            warnings.append(f"{failed_proc} document(s) failed during parsing and require re-upload or inspection.")
        if pending_proc > 0:
            warnings.append(f"{pending_proc} document(s) remain queued for processing.")
        if duplicate_proc > 0:
            warnings.append(f"{duplicate_proc} document(s) were flagged as duplicates.")

        return SessionSummaryReportData(
            report_id=str(uuid.uuid4()),
            session_id=session.id,
            session_name=session.session_name,
            job_id=session.job_id,
            job_title=job_title,
            department=department,
            session_created_at=session.created_at,
            max_resume_count=session.max_resume_count,
            total_resumes_enrolled=total_enrolled,
            completed_processing_count=completed_proc,
            failed_processing_count=failed_proc,
            pending_processing_count=pending_proc,
            duplicate_count=duplicate_proc,
            coverage_limitation_warning=coverage_warning,
            completed_evaluation_count=completed_eval_count,
            scoring_config_id=scoring_cfg_id,
            scoring_config_version=scoring_cfg_version,
            evaluation_methods_used=methods_used,
            score_distribution=score_distribution,
            criterion_performance=criterion_performance,
            shortlist_summary=shortlist_counts,
            candidate_summaries=candidate_summaries,
            warnings=warnings,
        )
