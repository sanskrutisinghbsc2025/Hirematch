
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.models.enums import (
    RankingSortField,
    ScoreCompleteness,
    ShortlistReviewStatus,
    TieHandlingStrategy,
)
from core.models.scoring_models import (
    CandidateScoringRecord,
    RankedCandidate,
    ScoringConfiguration,
    ShortlistRecord,
)


class DeterministicCandidateRanker:

    EPSILON = 1e-4

    def rank_candidates(
        self,
        scoring_records: List[CandidateScoringRecord],
        config: ScoringConfiguration,
        candidate_meta: Optional[Dict[str, Tuple[str, str]]] = None,
        shortlist_map: Optional[Dict[str, ShortlistRecord]] = None,
        reverse_order: bool = False,
        quality_map: Optional[Dict[str, Any]] = None,
    ) -> List[RankedCandidate]:
        meta = candidate_meta or {}
        shortlist = shortlist_map or {}
        quality = quality_map or {}

        scorable: List[CandidateScoringRecord] = []
        incomplete: List[CandidateScoringRecord] = []

        for rec in scoring_records:
            if rec.overall_score is not None:
                scorable.append(rec)
            else:
                incomplete.append(rec)

        def sort_key(rec: CandidateScoringRecord):
            c_name, c_file = meta.get(rec.candidate_id, ("Unknown", "Unknown.pdf"))
            score_val = rec.overall_score or 0.0

            if config.secondary_sort == RankingSortField.EVIDENCE_COVERAGE:
                sec_val = rec.evidence_coverage
            elif config.secondary_sort == RankingSortField.REQUIRED_MET_COUNT:
                sec_val = rec.required_summary.supported_count + rec.required_summary.partially_supported_count
            else:
                sec_val = 0.0

            return (
                score_val,
                sec_val,
                c_name.lower(),
                c_file.lower(),
                rec.candidate_id,
            )

        scorable.sort(key=sort_key, reverse=not reverse_order)

        ranked_list: List[RankedCandidate] = []
        if scorable:
            current_rank = 1
            dense_rank = 1

            for i, rec in enumerate(scorable):
                c_name, c_file = meta.get(rec.candidate_id, ("Unknown Candidate", "resume.pdf"))
                s_entry = shortlist.get(rec.candidate_id)

                is_tied = False
                if i > 0 and abs((scorable[i - 1].overall_score or 0.0) - (rec.overall_score or 0.0)) <= self.EPSILON:
                    is_tied = True
                elif i < len(scorable) - 1 and abs((scorable[i + 1].overall_score or 0.0) - (rec.overall_score or 0.0)) <= self.EPSILON:
                    is_tied = True

                if i == 0:
                    assigned_rank = 1
                else:
                    prev_score = scorable[i - 1].overall_score or 0.0
                    curr_score = rec.overall_score or 0.0
                    is_same_as_prev = abs(prev_score - curr_score) <= self.EPSILON

                    if config.tie_strategy == TieHandlingStrategy.STANDARD_COMPETITION:
                        if is_same_as_prev:
                            assigned_rank = current_rank
                        else:
                            current_rank = i + 1
                            assigned_rank = current_rank
                    elif config.tie_strategy == TieHandlingStrategy.DENSE:
                        if not is_same_as_prev:
                            dense_rank += 1
                        assigned_rank = dense_rank
                    else:
                        assigned_rank = i + 1

                q_entry = quality.get(rec.candidate_id)
                q_score = q_entry.overall_score if q_entry else None
                q_label = (
                    q_entry.quality_label.value
                    if (q_entry and hasattr(q_entry, "quality_label") and hasattr(q_entry.quality_label, "value"))
                    else (q_entry.get("quality_label") if isinstance(q_entry, dict) else None)
                )

                ranked_list.append(
                    RankedCandidate(
                        rank=assigned_rank,
                        candidate_id=rec.candidate_id,
                        candidate_name=c_name,
                        filename=c_file,
                        overall_score=rec.overall_score,
                        evidence_coverage=rec.evidence_coverage,
                        completeness_status=rec.completeness_status,
                        required_summary=rec.required_summary,
                        is_tied=is_tied,
                        scoring_record_id=rec.id,
                        shortlist_status=s_entry.review_status if s_entry else None,
                        reviewer_notes=s_entry.reviewer_notes if s_entry else "",
                        resume_quality_score=q_score,
                        resume_quality_label=q_label,
                    )
                )

        for rec in incomplete:
            c_name, c_file = meta.get(rec.candidate_id, ("Unknown Candidate", "resume.pdf"))
            s_entry = shortlist.get(rec.candidate_id)
            q_entry = quality.get(rec.candidate_id)
            q_score = q_entry.overall_score if q_entry else None
            q_label = (
                q_entry.quality_label.value
                if (q_entry and hasattr(q_entry, "quality_label") and hasattr(q_entry.quality_label, "value"))
                else (q_entry.get("quality_label") if isinstance(q_entry, dict) else None)
            )

            ranked_list.append(
                RankedCandidate(
                    rank=0,
                    candidate_id=rec.candidate_id,
                    candidate_name=c_name,
                    filename=c_file,
                    overall_score=None,
                    evidence_coverage=rec.evidence_coverage,
                    completeness_status=rec.completeness_status,
                    required_summary=rec.required_summary,
                    is_tied=False,
                    scoring_record_id=rec.id,
                    shortlist_status=s_entry.review_status if s_entry else None,
                    reviewer_notes=s_entry.reviewer_notes if s_entry else "",
                    resume_quality_score=q_score,
                    resume_quality_label=q_label,
                )
            )

        return ranked_list

    def filter_candidates(
        self,
        ranked_candidates: List[RankedCandidate],
        search_query: Optional[str] = None,
        min_score: Optional[float] = None,
        max_score: Optional[float] = None,
        min_coverage: Optional[float] = None,
        shortlist_filter: Optional[str] = None,
        required_filter: Optional[str] = None,
        completeness_filter: Optional[str] = None,
    ) -> List[RankedCandidate]:
        results = ranked_candidates

        if search_query and search_query.strip():
            q = search_query.strip().lower()
            results = [
                c for c in results
                if q in c.candidate_name.lower() or q in c.filename.lower()
            ]

        if min_score is not None:
            results = [c for c in results if c.overall_score is not None and c.overall_score >= min_score]
        if max_score is not None:
            results = [c for c in results if c.overall_score is not None and c.overall_score <= max_score]

        if min_coverage is not None:
            results = [c for c in results if c.evidence_coverage >= min_coverage]

        if shortlist_filter and shortlist_filter != "ALL":
            results = [
                c for c in results
                if c.shortlist_status and c.shortlist_status.value == shortlist_filter
            ]

        if required_filter and required_filter != "ALL":
            if required_filter == "ALL_REQUIRED_MET":
                results = [c for c in results if c.required_summary.all_satisfied]
            elif required_filter == "HAS_CONFLICTS":
                results = [c for c in results if c.required_summary.conflicting_count > 0]
            elif required_filter == "HAS_UNMET_REQUIRED":
                results = [
                    c for c in results
                    if (c.required_summary.not_found_count + c.required_summary.insufficient_evidence_count) > 0
                ]

        if completeness_filter and completeness_filter != "ALL":
            results = [c for c in results if c.completeness_status.value == completeness_filter]

        return results
