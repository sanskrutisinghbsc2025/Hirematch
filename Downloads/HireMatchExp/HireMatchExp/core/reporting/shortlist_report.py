
from typing import List, Optional
import uuid

from core.models.enums import ShortlistReviewStatus
from core.models.report_models import ShortlistReportData, ShortlistReportItem
from core.storage.database import Database
from core.storage.eval_repository import EvaluationRecordRepository
from core.storage.repositories import (
    CandidateRepository,
    JobRepository,
    SessionRepository,
)
from core.storage.scoring_repository import ScoringRecordRepository
from core.storage.shortlist_repository import ShortlistRepository
from core.utils.logger import logger


class ShortlistReportGenerator:

    def __init__(self, db: Database):
        self.db = db
        self.session_repo = SessionRepository(db)
        self.job_repo = JobRepository(db)
        self.candidate_repo = CandidateRepository(db)
        self.shortlist_repo = ShortlistRepository(db)
        self.scoring_repo = ScoringRecordRepository(db)
        self.eval_repo = EvaluationRecordRepository(db)

    def generate(
        self,
        session_id: str,
        filter_status: Optional[ShortlistReviewStatus] = None,
    ) -> ShortlistReportData:
        session = self.session_repo.get(session_id)
        if not session:
            raise ValueError(f"Screening Session '{session_id}' not found.")

        job = self.job_repo.get(session.job_id)
        job_title = job.title if job else "General Role"

        shortlist_records = self.shortlist_repo.list_by_session(session_id)
        if filter_status:
            shortlist_records = [s for s in shortlist_records if s.review_status == filter_status]

        status_counts = self.shortlist_repo.get_status_counts(session_id)

        items: List[ShortlistReportItem] = []
        for sl in shortlist_records:
            cand = self.candidate_repo.get(sl.candidate_id)
            if not cand:
                continue

            s_rec = self.scoring_repo.get_by_candidate_and_session(cand.id, session_id)
            e_rec = self.eval_repo.get_by_candidate_and_session(cand.id, session_id)

            cand_score = s_rec.overall_score if s_rec else (e_rec.overall_score if e_rec else None)
            cand_cov = s_rec.evidence_coverage if s_rec else (e_rec.evidence_coverage if e_rec else 0.0)

            highlights = []
            if s_rec:
                for cc in s_rec.criterion_contributions:
                    if cc.support_value >= 0.8:
                        highlights.append(f"Strong match for {cc.criterion_name} ({int(cc.support_value * 100)}%)")
            elif e_rec:
                for cr in e_rec.criterion_results:
                    if cr.score >= 0.8:
                        highlights.append(f"Strong match for {cr.criterion_name} ({int(cr.score * 100)}%)")

            items.append(
                ShortlistReportItem(
                    candidate_id=cand.id,
                    candidate_reference=f"Cand-{cand.id[:8].upper()}",
                    original_filename=cand.original_filename,
                    review_status=sl.review_status,
                    overall_score=cand_score,
                    evidence_coverage=cand_cov,
                    key_evidence_highlights=highlights[:4],
                    reviewer_notes=sl.reviewer_notes,
                    updated_at=sl.updated_at,
                )
            )

        def sort_key(item: ShortlistReportItem):
            is_shortlisted = item.review_status == ShortlistReviewStatus.SHORTLISTED
            score = item.overall_score if item.overall_score is not None else -1.0
            return (is_shortlisted, score)

        items.sort(key=sort_key, reverse=True)

        return ShortlistReportData(
            report_id=str(uuid.uuid4()),
            session_id=session.id,
            session_name=session.session_name,
            job_id=session.job_id,
            job_title=job_title,
            total_shortlisted_count=len(items),
            items=items,
            status_counts=status_counts,
        )
