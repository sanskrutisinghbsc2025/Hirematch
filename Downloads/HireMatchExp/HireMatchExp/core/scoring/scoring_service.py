
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from core.evaluation.criteria_validator import ResponsibleAICriteriaValidator
from core.models.enums import CriterionCategory, CriterionType, MissingEvidencePolicy, ScoreCompleteness, ScoreStatus
from core.models.evaluation import CandidateEvaluationRecord, CandidateScore
from core.models.scoring_models import (
    CandidateScoringRecord,
    RankedCandidate,
    RankingSnapshot,
    ScoringConfiguration,
    ScoringCriterion,
)
from core.scoring.calculator import TransparentScoreCalculator
from core.scoring.explanation import ScoreExplanationGenerator
from core.scoring.ranker import DeterministicCandidateRanker
from core.storage.database import Database
from core.storage.eval_repository import EvaluationConfigurationRepository, EvaluationRecordRepository
from core.storage.quality_repository import ResumeQualityRepository
from core.storage.repositories import CandidateRepository, CriterionRepository, JobRepository, ScoreRepository, SessionRepository
from core.storage.scoring_repository import RankingSnapshotRepository, ScoringRecordRepository
from core.storage.shortlist_repository import ShortlistRepository
from core.utils.logger import logger


class ScoringService:

    def __init__(self, db: Database):
        self.db = db
        self.session_repo = SessionRepository(db)
        self.job_repo = JobRepository(db)
        self.cand_repo = CandidateRepository(db)
        self.crit_repo = CriterionRepository(db)
        self.eval_record_repo = EvaluationRecordRepository(db)
        self.eval_config_repo = EvaluationConfigurationRepository(db)
        self.scoring_repo = ScoringRecordRepository(db)
        self.score_repo = ScoreRepository(db)
        self.shortlist_repo = ShortlistRepository(db)
        self.ranking_repo = RankingSnapshotRepository(db)
        self.quality_repo = ResumeQualityRepository(db)

        self.calculator = TransparentScoreCalculator()
        self.ranker = DeterministicCandidateRanker()
        self.explainer = ScoreExplanationGenerator()
        self.validator = ResponsibleAICriteriaValidator()

    def get_or_create_scoring_config(self, job_id: str, session_id: Optional[str] = None) -> ScoringConfiguration:
        latest_eval_cfg = self.eval_config_repo.get_latest_by_job(job_id)
        if latest_eval_cfg and latest_eval_cfg.criteria:
            scoring_criteria = [
                ScoringCriterion(
                    id=c.id,
                    criterion_name=c.criterion_name,
                    description=c.description,
                    category=c.category,
                    weight=c.weight,
                    criterion_type=c.criterion_type,
                    is_enabled=c.is_enabled,
                    config_version=latest_eval_cfg.version,
                )
                for c in latest_eval_cfg.criteria
            ]
            return ScoringConfiguration(
                job_id=job_id,
                version=latest_eval_cfg.version,
                name=latest_eval_cfg.name,
                criteria=scoring_criteria,
            )

        if session_id:
            eval_recs = self.eval_record_repo.list_by_session(session_id)
            if eval_recs and eval_recs[0].criterion_results:
                seen_ids = set()
                scoring_criteria = []
                for cr in eval_recs[0].criterion_results:
                    if cr.criterion_id not in seen_ids:
                        seen_ids.add(cr.criterion_id)
                        scoring_criteria.append(
                            ScoringCriterion(
                                id=cr.criterion_id,
                                criterion_name=cr.criterion_name,
                                category=getattr(cr, "category", CriterionCategory.TECHNICAL_SKILL),
                                weight=cr.weight if cr.weight > 0 else 1.0 / len(eval_recs[0].criterion_results),
                                criterion_type=cr.criterion_type,
                                is_enabled=True,
                                config_version="v1.0",
                            )
                        )
                if scoring_criteria:
                    return ScoringConfiguration(
                        job_id=job_id,
                        version="v1.0",
                        name="Session Inferred Scoring Configuration",
                        criteria=scoring_criteria,
                    )

        job_crits = self.crit_repo.list_by_job(job_id)
        if not job_crits:
            job_crits_models = [
                ScoringCriterion(
                    id=f"default_tech_{job_id[:6]}",
                    criterion_name="Technical Qualifications",
                    category=CriterionCategory.TECHNICAL_SKILL,
                    weight=0.5,
                    criterion_type=CriterionType.REQUIRED,
                ),
                ScoringCriterion(
                    id=f"default_exp_{job_id[:6]}",
                    criterion_name="Relevant Experience",
                    category=CriterionCategory.EXPERIENCE_DURATION,
                    weight=0.5,
                    criterion_type=CriterionType.REQUIRED,
                ),
            ]
        else:
            job_crits_models = [
                ScoringCriterion(
                    id=c.id,
                    criterion_name=c.criterion_name,
                    description=c.description,
                    category=c.category,
                    weight=c.weight,
                    criterion_type=c.criterion_type,
                    is_enabled=c.is_enabled,
                    config_version="v1.0",
                )
                for c in job_crits
            ]

        return ScoringConfiguration(
            job_id=job_id,
            version="v1.0",
            name="Default Scoring Configuration",
            criteria=job_crits_models,
        )

    def save_scoring_config(self, config: ScoringConfiguration) -> ScoringConfiguration:
        errs = config.validate_configuration()
        if errs:
            raise ValueError(f"Invalid scoring configuration: {'; '.join(errs)}")

        crit_names = [c.criterion_name for c in config.criteria]
        val_res = self.validator.validate_criteria_names(crit_names)
        if not val_res.is_valid:
            violations = "; ".join(val_res.blocked_criteria)
            raise ValueError(f"Responsible AI criteria validation failed: Blocked {violations}")

        from core.models.eval_config import EvaluationConfiguration
        from core.models.evaluation import EvaluationCriterion

        eval_criteria = [
            EvaluationCriterion(
                id=c.id,
                criterion_name=c.criterion_name,
                description=c.description,
                weight=c.weight,
                criterion_type=c.criterion_type,
                category=c.category,
                is_enabled=c.is_enabled,
            )
            for c in config.criteria
        ]
        eval_cfg = EvaluationConfiguration(
            id=config.id,
            job_id=config.job_id,
            version=config.version,
            name=config.name,
            criteria=eval_criteria,
            notes=config.notes,
            created_at=config.created_at,
        )
        self.eval_config_repo.save(eval_cfg)
        logger.info(f"Saved ScoringConfiguration {config.id} (version {config.version}) for job {config.job_id}")
        return config

    def score_session(
        self, session_id: str, config: Optional[ScoringConfiguration] = None
    ) -> Dict[str, Any]:
        session = self.session_repo.get(session_id)
        if not session:
            raise ValueError(f"Screening session '{session_id}' not found.")

        eval_records = self.eval_record_repo.list_by_session(session_id)
        if not eval_records:
            logger.warning(f"No candidate evaluation records found for session {session_id}.")
            return {
                "scored_count": 0,
                "incomplete_count": 0,
                "scoring_config_version": "None",
                "records": [],
            }

        active_config = config or self.get_or_create_scoring_config(session.job_id, session_id=session_id)

        validation_errors = active_config.validate_configuration()
        if validation_errors:
            raise ValueError(f"Scoring configuration validation failed: {'; '.join(validation_errors)}")

        scoring_records: List[CandidateScoringRecord] = []
        for eval_rec in eval_records:
            score_rec = self.calculator.calculate_score(eval_rec, active_config)
            score_rec.explanation = self.explainer.generate_narrative_explanation(score_rec)
            scoring_records.append(score_rec)

        candidates = self.cand_repo.list_by_session(session_id)
        cand_meta = {}
        for item in candidates:
            if isinstance(item, dict) and "candidate" in item:
                c_obj = item["candidate"]
                cand_meta[c_obj.id] = (c_obj.original_filename, c_obj.original_filename)
            elif hasattr(item, "id"):
                cand_meta[item.id] = (item.original_filename, item.original_filename)
        shortlist_entries = {s.candidate_id: s for s in self.shortlist_repo.list_by_session(session_id)}
        quality_map = self.quality_repo.get_session_map(session_id)

        ranked_candidates = self.ranker.rank_candidates(
            scoring_records=scoring_records,
            config=active_config,
            candidate_meta=cand_meta,
            shortlist_map=shortlist_entries,
            quality_map=quality_map,
        )

        self.scoring_repo.save_batch(scoring_records)

        scores_to_save: List[CandidateScore] = []
        for s_rec in scoring_records:
            if s_rec.overall_score is not None:
                crit_scores = {
                    c.criterion_name: c.normalized_contribution
                    for c in s_rec.criterion_contributions
                }
                status_val = (
                    ScoreStatus.CALCULATED
                    if s_rec.completeness_status == ScoreCompleteness.COMPLETE
                    else ScoreStatus.PARTIAL
                )
                cand_score = CandidateScore(
                    candidate_id=s_rec.candidate_id,
                    overall_score=s_rec.overall_score,
                    criterion_scores=crit_scores,
                    score_status=status_val,
                    explanation=s_rec.explanation,
                    scoring_config_version=active_config.version,
                    evaluated_at=s_rec.created_at,
                )
                scores_to_save.append(cand_score)

        if hasattr(self.score_repo, "save_scores_batch"):
            self.score_repo.save_scores_batch(scores_to_save)
        else:
            for cand_score in scores_to_save:
                self.score_repo.save_score(cand_score)

        snapshot = RankingSnapshot(
            session_id=session_id,
            scoring_config_id=active_config.id,
            scoring_config_version=active_config.version,
            ranked_items=[c.to_dict() for c in ranked_candidates],
        )
        self.ranking_repo.save(snapshot)

        scored_count = sum(1 for r in scoring_records if r.overall_score is not None)
        incomplete_count = len(scoring_records) - scored_count

        logger.info(
            f"Scored session {session_id}: {scored_count} scored, {incomplete_count} incomplete "
            f"under configuration {active_config.version}"
        )

        return {
            "session_id": session_id,
            "scoring_config_id": active_config.id,
            "scoring_config_version": active_config.version,
            "total_evaluated": len(scoring_records),
            "scored_count": scored_count,
            "incomplete_count": incomplete_count,
            "records": scoring_records,
            "ranked_candidates": ranked_candidates,
        }

    def get_ranked_candidates(
        self,
        session_id: str,
        config: Optional[ScoringConfiguration] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[RankedCandidate]:
        session = self.session_repo.get(session_id)
        if not session:
            return []

        active_config = config or self.get_or_create_scoring_config(session.job_id, session_id=session_id)

        scoring_records = self.scoring_repo.list_by_session(session_id, scoring_config_id=active_config.id)
        if not scoring_records:
            res = self.score_session(session_id, config=active_config)
            scoring_records = res.get("records", [])

        candidates = self.cand_repo.list_by_session(session_id)
        cand_meta = {}
        for item in candidates:
            if isinstance(item, dict) and "candidate" in item:
                c_obj = item["candidate"]
                cand_meta[c_obj.id] = (c_obj.original_filename, c_obj.original_filename)
            elif hasattr(item, "id"):
                cand_meta[item.id] = (item.original_filename, item.original_filename)
        shortlist_entries = {s.candidate_id: s for s in self.shortlist_repo.list_by_session(session_id)}
        quality_map = self.quality_repo.get_session_map(session_id)

        ranked = self.ranker.rank_candidates(
            scoring_records=scoring_records,
            config=active_config,
            candidate_meta=cand_meta,
            shortlist_map=shortlist_entries,
            quality_map=quality_map,
        )

        if filters:
            ranked = self.ranker.filter_candidates(
                ranked_candidates=ranked,
                search_query=filters.get("search_query"),
                min_score=filters.get("min_score"),
                max_score=filters.get("max_score"),
                min_coverage=filters.get("min_coverage"),
                shortlist_filter=filters.get("shortlist_filter"),
                required_filter=filters.get("required_filter"),
                completeness_filter=filters.get("completeness_filter"),
            )

        return ranked
