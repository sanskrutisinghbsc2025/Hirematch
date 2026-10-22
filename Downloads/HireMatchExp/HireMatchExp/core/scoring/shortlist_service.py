
from datetime import datetime, timezone
from typing import Dict, List, Optional
import uuid

from core.models.enums import ShortlistReviewStatus
from core.models.scoring_models import ShortlistRecord
from core.storage.shortlist_repository import ShortlistRepository
from core.utils.logger import logger


class ShortlistService:

    def __init__(self, shortlist_repo: ShortlistRepository):
        self.repo = shortlist_repo

    def set_review_status(
        self,
        session_id: str,
        candidate_id: str,
        status: ShortlistReviewStatus,
        reviewer_notes: Optional[str] = None,
        scoring_record_id: Optional[str] = None,
        scoring_config_id: str = "default",
        scoring_config_version: str = "v1.0",
    ) -> ShortlistRecord:
        existing = self.repo.get(session_id, candidate_id)
        now_iso = datetime.now(timezone.utc).isoformat()

        if existing:
            existing.review_status = status
            if reviewer_notes is not None:
                existing.reviewer_notes = reviewer_notes
            if scoring_record_id:
                existing.scoring_record_id = scoring_record_id
            existing.scoring_config_id = scoring_config_id
            existing.scoring_config_version = scoring_config_version
            existing.updated_at = now_iso
            record = existing
        else:
            record = ShortlistRecord(
                id=str(uuid.uuid4()),
                session_id=session_id,
                candidate_id=candidate_id,
                review_status=status,
                reviewer_notes=reviewer_notes or "",
                scoring_record_id=scoring_record_id,
                scoring_config_id=scoring_config_id,
                scoring_config_version=scoring_config_version,
                created_at=now_iso,
                updated_at=now_iso,
            )

        self.repo.save(record)
        logger.info(
            f"Recruiter updated review status to {status.value} for candidate {candidate_id} in session {session_id}"
        )
        return record

    def add_reviewer_note(
        self, session_id: str, candidate_id: str, note_text: str
    ) -> Optional[ShortlistRecord]:
        existing = self.repo.get(session_id, candidate_id)
        if existing:
            existing.reviewer_notes = note_text
            existing.updated_at = datetime.now(timezone.utc).isoformat()
            self.repo.save(existing)
            return existing
        else:
            return self.set_review_status(
                session_id=session_id,
                candidate_id=candidate_id,
                status=ShortlistReviewStatus.NEEDS_REVIEW,
                reviewer_notes=note_text,
            )

    def remove_from_shortlist(self, session_id: str, candidate_id: str) -> bool:
        deleted = self.repo.delete(session_id, candidate_id)
        if deleted:
            logger.info(f"Removed candidate {candidate_id} from shortlist in session {session_id}")
        return deleted

    def get_candidate_shortlist_entry(
        self, session_id: str, candidate_id: str
    ) -> Optional[ShortlistRecord]:
        return self.repo.get(session_id, candidate_id)

    def list_session_shortlist(
        self, session_id: str, status: Optional[ShortlistReviewStatus] = None
    ) -> List[ShortlistRecord]:
        return self.repo.list_by_session(session_id, status=status)

    def get_status_counts(self, session_id: str) -> Dict[str, int]:
        return self.repo.count_by_status(session_id)
