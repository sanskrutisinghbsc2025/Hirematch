
from datetime import datetime, timezone
import io
from pathlib import Path
from typing import Any, BinaryIO, Dict, List, Optional, Tuple, Union

from config import AppConfig, settings
from core.models.candidate import Candidate
from core.models.enums import EvaluationMode, FileType, ProcessingStatus, SessionStatus
from core.models.evaluation import EvaluationCriterion
from core.models.job import Job
from core.models.session import ScreeningSession
from core.evaluation.baseline_evaluator import BaselineCandidateEvaluator
from core.evaluation.embedding_provider import CachedEmbeddingProvider
from core.evaluation.hybrid_scoring_engine import HybridScoringEngine
from core.evaluation.scoring_engine import TransparentScoringEngine
from core.evaluation.semantic_evaluator import SemanticCandidateEvaluator
from core.evaluation.semantic_matcher import SemanticMatcher
from core.processing.extractor import DocumentExtractorFactory
from core.services.file_validator import FileValidatorService
from core.services.model_manager import ModelManager
from core.evaluation.multi_layer_evaluator import MultiLayerCandidateEvaluator
from core.evaluation.resume_quality_evaluator import ResumeQualityEvaluator
from core.models.quality_models import ResumeQualityAssessment
from core.models.eval_config import EvaluationConfiguration
from core.storage.database import Database
from core.storage.embedding_cache import SQLiteEmbeddingCache
from core.storage.quality_repository import ResumeQualityRepository
from core.storage.eval_repository import (
    EvaluationConfigurationRepository,
    EvaluationRecordRepository,
)
from core.storage.repositories import (
    CandidateRepository,
    CriterionRepository,
    EvidenceRepository,
    JobRepository,
    ScoreRepository,
    SessionRepository,
)
from core.models.enums import ShortlistReviewStatus
from core.models.scoring_models import (
    CandidateScoringRecord,
    RankedCandidate,
    ScoringConfiguration,
    ShortlistRecord,
)
from core.scoring import (
    DeterministicCandidateRanker,
    RankingSensitivitySimulator,
    ScoreExplanationGenerator,
    ScoringService,
    ShortlistService,
    TransparentScoreCalculator,
)
from core.storage.scoring_repository import RankingSnapshotRepository, ScoringRecordRepository
from core.storage.shortlist_repository import ShortlistRepository
from core.models.report_models import (
    CandidateComparisonData,
    CandidateReportData,
    ExportFormat,
    GeneratedReportRecord,
    ReportType,
    SessionSummaryReportData,
    ShortlistReportData,
)
from core.reporting import (
    CandidateComparisonService,
    CandidateReportGenerator,
    RecruitmentInsightsService,
    ReportExportService,
    SessionSummaryReportGenerator,
    ShortlistReportGenerator,
)
from core.analytics import (
    AnalyticsExportService,
    AnalyticsFilter,
    CriterionAnalytics,
    CriterionAnalyticsService,
    PortfolioAnalytics,
    PortfolioAnalyticsService,
    SessionAnalytics,
    SessionAnalyticsService,
    SessionComparisonAnalytics,
    SessionComparisonAnalyticsService,
    SkillCoverageAnalyticsService,
    SkillCoverageItem,
    TraceableInsight,
    TraceableInsightsGenerator,
)
from core.storage.report_repository import ReportRecordRepository
from core.model_lab import (
    BenchmarkConfiguration,
    BenchmarkRunRecord,
    BenchmarkRunner,
    EvaluationDataset,
    EvaluationDatasetItem,
    EvaluationDatasetService,
    ModelMetadata,
    ModelRegistry,
    RelevanceGrade,
    TaskType,
)
from core.storage.benchmark_repository import BenchmarkRunRepository, EvaluationDatasetRepository
from core.utils.errors import (
    FileValidationError,
    SessionLimitExceededError,
    SessionNotFoundError,
)
from core.utils.hashing import compute_file_hash
from core.utils.logger import logger
from core.utils.sanitizer import sanitize_filename


class ScreeningOrchestrator:

    def __init__(self, db: Database, config: Optional[AppConfig] = None):
        self.db = db
        self.config = config or settings
        self.job_repo = JobRepository(db)
        self.session_repo = SessionRepository(db)
        self.candidate_repo = CandidateRepository(db)
        self.crit_repo = CriterionRepository(db)
        self.score_repo = ScoreRepository(db)
        self.evidence_repo = EvidenceRepository(db)
        self.validator = FileValidatorService(self.config)
        self.evaluator = BaselineCandidateEvaluator()
        self.scoring_engine = TransparentScoringEngine()
        self.quality_evaluator = ResumeQualityEvaluator(self.config)
        self.quality_repo = ResumeQualityRepository(db)

        self.embedding_cache = SQLiteEmbeddingCache(db)
        self.model_manager = ModelManager(self.config)
        try:
            emb_provider = self.model_manager.get_embedding_provider(
                model_name=self.config.semantic_model_name,
                prefer_mock_if_missing=True,
            )
            cached_provider = CachedEmbeddingProvider(emb_provider, self.embedding_cache)
            sem_matcher = SemanticMatcher(cached_provider)
            self.semantic_evaluator = SemanticCandidateEvaluator(sem_matcher)
        except Exception as e:
            logger.warning(f"Could not initialize semantic evaluator: {e}")
            self.semantic_evaluator = None

        self.hybrid_engine = HybridScoringEngine(
            baseline_evaluator=self.evaluator,
            semantic_evaluator=self.semantic_evaluator,
            scoring_engine=self.scoring_engine,
        )

        self.eval_config_repo = EvaluationConfigurationRepository(db)
        self.eval_record_repo = EvaluationRecordRepository(db)
        self.multi_layer_evaluator = MultiLayerCandidateEvaluator(
            baseline_evaluator=self.evaluator,
            semantic_evaluator=self.semantic_evaluator,
        )

        self.scoring_service = ScoringService(db)
        self.shortlist_service = ShortlistService(ShortlistRepository(db))
        self.sensitivity_simulator = RankingSensitivitySimulator()

        self.candidate_report_generator = CandidateReportGenerator(db)
        self.session_report_generator = SessionSummaryReportGenerator(db)
        self.candidate_comparison_service = CandidateComparisonService(db)
        self.shortlist_report_generator = ShortlistReportGenerator(db)
        self.insights_service = RecruitmentInsightsService(db)
        self.export_service = ReportExportService(db, self.config)
        self.report_repo = ReportRecordRepository(db)

        self.portfolio_analytics_service = PortfolioAnalyticsService(db)
        self.session_analytics_service = SessionAnalyticsService(db)
        self.skill_analytics_service = SkillCoverageAnalyticsService(db)
        self.criterion_analytics_service = CriterionAnalyticsService(db)
        self.insights_generator = TraceableInsightsGenerator(db)
        self.session_comparison_analytics_service = SessionComparisonAnalyticsService(db)
        self.analytics_export_service = AnalyticsExportService(self.config)

        self.model_registry = ModelRegistry(self.config)
        self.evaluation_dataset_service = EvaluationDatasetService(db)
        self.benchmark_runner = BenchmarkRunner(self.model_registry, self.evaluation_dataset_service, db)
        self.benchmark_run_repo = BenchmarkRunRepository(db)
        self.eval_dataset_repo = EvaluationDatasetRepository(db)


    def create_session(
        self,
        job_id: str,
        session_name: str,
        max_resume_count: Optional[int] = None,
    ) -> ScreeningSession:
        job = self.job_repo.get(job_id)
        if not job:
            raise ValueError(f"Job with ID '{job_id}' does not exist.")

        max_cap = max_resume_count or self.config.max_resumes_per_session
        if max_cap > self.config.max_resumes_per_session:
            raise SessionLimitExceededError(
                f"Requested limit of {max_cap} exceeds system maximum allowed ({self.config.max_resumes_per_session})."
            )

        session = ScreeningSession(
            job_id=job_id,
            session_name=session_name,
            max_resume_count=max_cap,
            status=SessionStatus.CREATED,
        )
        return self.session_repo.create(session)

    def add_resumes_to_session(
        self,
        session_id: str,
        files: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        session = self.session_repo.get(session_id)
        if not session:
            raise SessionNotFoundError(f"Session with ID '{session_id}' not found.")

        current_candidates = self.candidate_repo.list_by_session(session_id)
        current_count = len(current_candidates)
        new_count = len(files)

        if current_count + new_count > session.max_resume_count:
            raise SessionLimitExceededError(
                f"Cannot add {new_count} resumes to session '{session_id}'. "
                f"Session currently has {current_count} resumes; maximum allowed is {session.max_resume_count}.",
                user_message=(
                    f"Session limit reached. Adding {new_count} resumes exceeds the "
                    f"{session.max_resume_count}-resume limit (currently enrolled: {current_count})."
                ),
            )

        self.validator.validate_batch(files, current_session_count=current_count)

        enrolled_count = 0
        duplicate_count = 0
        failed_count = 0
        details = []

        existing_hashes = {c["candidate"].file_hash for c in current_candidates}

        for file_info in files:
            filename = file_info["filename"]
            raw_content = file_info["content"]

            if hasattr(raw_content, "read"):
                content_bytes = raw_content.read()
                if hasattr(raw_content, "seek"):
                    raw_content.seek(0)
            else:
                content_bytes = raw_content

            size_bytes = file_info.get("size", len(content_bytes))

            file_hash = compute_file_hash(content_bytes)

            try:
                meta = self.validator.validate_file(filename, size_bytes, content_bytes)
            except FileValidationError as e:
                logger.warning(f"File validation failed for '{filename}': {e}")
                failed_cand = Candidate(
                    original_filename=filename,
                    file_hash=file_hash,
                    file_type=self.validator.detect_file_type(filename),
                    processing_status=ProcessingStatus.FAILED,
                    error_info=e.user_message or str(e),
                )
                self.candidate_repo.create(failed_cand)
                self.candidate_repo.link_to_session(
                    session_id=session_id,
                    candidate_id=failed_cand.id,
                    processing_status=ProcessingStatus.FAILED,
                    manifest_meta={"filename": filename, "size_bytes": size_bytes},
                    error_info=e.user_message or str(e),
                )
                failed_count += 1
                details.append({"filename": filename, "status": "FAILED", "reason": str(e)})
                continue

            if file_hash in existing_hashes:
                logger.info(f"Duplicate resume detected within session: '{filename}' (hash: {file_hash[:8]}...)")
                duplicate_count += 1
                details.append({"filename": filename, "status": "DUPLICATE", "reason": "Duplicate content."})
                continue

            storage_path = self._persist_file(file_hash, filename, content_bytes)

            cand = Candidate(
                original_filename=filename,
                file_hash=file_hash,
                file_type=meta.file_type,
                text_ref=str(storage_path),
                processing_status=ProcessingStatus.PENDING,
            )
            created_cand = self.candidate_repo.create(cand)
            self.candidate_repo.link_to_session(
                session_id=session_id,
                candidate_id=created_cand.id,
                processing_status=ProcessingStatus.PENDING,
                manifest_meta={"filename": filename, "size_bytes": size_bytes, "storage_path": str(storage_path)},
            )
            existing_hashes.add(file_hash)
            enrolled_count += 1
            details.append({"filename": filename, "status": "ENROLLED", "candidate_id": created_cand.id})

        total_session_count = current_count + enrolled_count + duplicate_count + failed_count
        self.session_repo.update_status(
            session_id=session_id,
            status=SessionStatus.PROCESSING if enrolled_count > 0 else session.status,
            candidate_count=total_session_count,
        )
        self._refresh_progress_metadata(session_id)

        return {
            "session_id": session_id,
            "enrolled": enrolled_count,
            "duplicate": duplicate_count,
            "failed": failed_count,
            "total_in_session": total_session_count,
            "details": details,
        }

    def process_session_batch(
        self,
        session_id: str,
        batch_size: Optional[int] = None,
    ) -> Dict[str, Any]:
        session = self.session_repo.get(session_id)
        if not session:
            raise SessionNotFoundError(f"Session with ID '{session_id}' not found.")

        chunk_size = batch_size or self.config.processing_batch_size
        session_candidates = self.candidate_repo.list_by_session(session_id)
        
        pending = [
            sc for sc in session_candidates
            if sc["session_status"] == ProcessingStatus.PENDING
        ][:chunk_size]

        processed_in_chunk = 0
        failed_in_chunk = 0

        for item in pending:
            cand: Candidate = item["candidate"]
            self.candidate_repo.update_session_candidate_status(
                session_id=session_id,
                candidate_id=cand.id,
                status=ProcessingStatus.EXTRACTING,
            )

            try:
                extractor = DocumentExtractorFactory.get_extractor(cand.file_type)

                if cand.text_ref and Path(cand.text_ref).exists():
                    with open(cand.text_ref, "rb") as f:
                        file_data = f.read()
                elif cand.extracted_text:
                    file_data = cand.extracted_text.encode("utf-8")
                else:
                    raise FileValidationError("Stored file content reference could not be resolved.")

                doc = extractor.extract_document(file_data)
                self.candidate_repo.update_extracted_text(cand.id, doc.cleaned_text, cand.text_ref)

                from core.processing.resume_parser import StructuredResumeParser
                parser = StructuredResumeParser()
                parsed_resume = parser.parse(doc.raw_text)

                structured_dict = {
                    "contact": {
                        "name": parsed_resume.contact.name,
                        "email": parsed_resume.contact.email,
                        "phone": parsed_resume.contact.phone,
                        "location": parsed_resume.contact.location,
                    },
                    "ocr_needed": doc.ocr_needed,
                    "is_empty": doc.is_empty,
                    "page_count": len(doc.pages),
                    "sections": [
                        {
                            "canonical_name": s.canonical_name,
                            "display_title": s.display_title,
                            "raw_heading": s.raw_heading,
                            "confidence": s.confidence,
                        }
                        for s in parsed_resume.sections
                    ],
                    "projects": [
                        {"title": p.title, "description": p.description, "evidence_text": p.evidence_text}
                        for p in parsed_resume.projects
                    ],
                    "certifications": [
                        {"name": c.name, "evidence_text": c.evidence_text}
                        for c in parsed_resume.certifications
                    ],
                }
                self.candidate_repo.update_structured_data(cand.id, structured_dict)

                self.candidate_repo.save_extracted_entities(
                    candidate_id=cand.id,
                    skills=parsed_resume.skills,
                    experience=parsed_resume.experience,
                    education=parsed_resume.education,
                )

                try:
                    quality_assessment = self.quality_evaluator.evaluate(
                        candidate_id=cand.id,
                        text=doc.cleaned_text,
                        structured_data=structured_dict,
                        extraction_meta={
                            "ocr_needed": doc.ocr_needed,
                            "is_empty": doc.is_empty,
                            "page_count": len(doc.pages),
                            "char_count": len(doc.cleaned_text),
                        },
                        session_id=session_id,
                    )
                    self.quality_repo.save(quality_assessment)
                except Exception as q_err:
                    logger.warning(f"Quality assessment error for candidate {cand.id}: {q_err}")

                status_to_set = ProcessingStatus.COMPLETED
                err_msg = None
                if doc.ocr_needed:
                    status_to_set = ProcessingStatus.FLAGGED_QUALITY
                    err_msg = "Image-only scanned document detected. OCR is required for text extraction."

                self.candidate_repo.update_session_candidate_status(
                    session_id=session_id,
                    candidate_id=cand.id,
                    status=status_to_set,
                    error_info=err_msg,
                )
                processed_in_chunk += 1
            except Exception as e:
                logger.error(f"Error processing candidate {cand.id} ({cand.original_filename}): {e}")
                self.candidate_repo.update_session_candidate_status(
                    session_id=session_id,
                    candidate_id=cand.id,
                    status=ProcessingStatus.FAILED,
                    error_info=str(e),
                )
                failed_in_chunk += 1

        progress = self._refresh_progress_metadata(session_id)

        if progress["pending"] == 0:
            now_iso = datetime.now(timezone.utc).isoformat()
            self.session_repo.update_status(
                session_id=session_id,
                status=SessionStatus.COMPLETED,
                completed_at=now_iso,
            )

        return {
            "session_id": session_id,
            "processed_in_chunk": processed_in_chunk,
            "failed_in_chunk": failed_in_chunk,
            "progress": progress,
        }

    def retry_failed_candidates(self, session_id: str) -> int:
        count = self.candidate_repo.reset_failed_for_retry(session_id)
        if count > 0:
            self.session_repo.update_status(session_id, SessionStatus.PROCESSING)
            self._refresh_progress_metadata(session_id)
            logger.info(f"Reset {count} failed candidates in session '{session_id}' for retry.")
        return count

    def evaluate_session_batch(
        self,
        session_id: str,
        batch_size: Optional[int] = None,
        evaluation_mode: EvaluationMode = EvaluationMode.BASELINE,
        model_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        import time

        start_time = time.perf_counter()

        session = self.session_repo.get(session_id)
        if not session:
            raise SessionNotFoundError(f"Session with ID '{session_id}' not found.")

        job = self.job_repo.get(session.job_id)
        if not job:
            raise ValueError(f"Job with ID '{session.job_id}' not found.")

        criteria = self._ensure_job_criteria(job)

        chunk_size = batch_size or self.config.processing_batch_size
        session_candidates = self.candidate_repo.list_by_session(session_id)

        existing_scores = self.score_repo.list_by_session(session_id)
        to_evaluate = [
            sc for sc in session_candidates
            if sc["session_status"] == ProcessingStatus.COMPLETED and sc["candidate"].id not in existing_scores
        ][:chunk_size]

        if not to_evaluate:
            to_evaluate = [
                sc for sc in session_candidates
                if sc["session_status"] == ProcessingStatus.COMPLETED
            ][:chunk_size]

        evaluated_in_chunk = 0
        failed_in_chunk = 0
        actual_model_name = model_name or self.config.semantic_model_name

        for item in to_evaluate:
            cand: Candidate = item["candidate"]
            try:
                structured_data = self.candidate_repo.get_structured_data(cand.id)
                score, evidence_list = self.hybrid_engine.evaluate_candidate(
                    candidate=cand,
                    job=job,
                    criteria=criteria,
                    mode=evaluation_mode,
                    structured_data=structured_data,
                    semantic_model_name=actual_model_name,
                )

                self.score_repo.save_score(score)
                self.evidence_repo.save_batch(evidence_list)

                self.candidate_repo.update_session_candidate_status(
                    session_id=session_id,
                    candidate_id=cand.id,
                    status=ProcessingStatus.EVALUATED,
                )
                evaluated_in_chunk += 1

            except Exception as e:
                logger.error(f"Evaluation failed for candidate '{cand.id}' ({cand.original_filename}): {e}")
                failed_in_chunk += 1

        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 1)

        meta = self._refresh_progress_metadata(session_id)

        remaining_to_eval = sum(
            1 for c in self.candidate_repo.list_by_session(session_id)
            if c["session_status"] in (ProcessingStatus.PENDING, ProcessingStatus.EXTRACTING, ProcessingStatus.COMPLETED)
        )
        if remaining_to_eval == 0 and meta.get("total", 0) > 0:
            self.session_repo.update_status(session_id, SessionStatus.COMPLETED)

        return {
            "session_id": session_id,
            "evaluated_in_chunk": evaluated_in_chunk,
            "failed_in_chunk": failed_in_chunk,
            "remaining_to_evaluate": remaining_to_eval,
            "elapsed_ms": elapsed_ms,
            "progress_percent": meta.get("percent_complete", 0.0),
        }

    def evaluate_session_multi_layer(
        self,
        session_id: str,
        config_id: Optional[str] = None,
        batch_size: Optional[int] = None,
        candidate_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        import time

        start_time = time.perf_counter()

        session = self.session_repo.get(session_id)
        if not session:
            raise SessionNotFoundError(f"Session with ID '{session_id}' not found.")

        job = self.job_repo.get(session.job_id)
        if not job:
            raise ValueError(f"Job with ID '{session.job_id}' not found.")

        criteria = self._ensure_job_criteria(job)
        eval_config = None
        if config_id:
            eval_config = self.eval_config_repo.get_config(config_id)
        if not eval_config:
            eval_config = self.eval_config_repo.get_latest_for_job(job.id)

        if not eval_config or len(eval_config.criteria) < len(criteria):
            eval_config = EvaluationConfiguration.create_default(job_id=job.id, criteria=criteria)
            self.eval_config_repo.save_config(eval_config)

        chunk_size = batch_size or self.config.processing_batch_size
        session_candidates = self.candidate_repo.list_by_session(session_id)

        if candidate_ids is not None:
            id_set = set(candidate_ids)
            to_evaluate = [
                sc for sc in session_candidates
                if sc["candidate"].id in id_set
            ][:chunk_size]
        else:
            existing_records = self.eval_record_repo.list_records_for_session(session_id)
            to_evaluate = [
                sc for sc in session_candidates
                if sc["session_status"] in (ProcessingStatus.COMPLETED, ProcessingStatus.EVALUATED, ProcessingStatus.FLAGGED_QUALITY)
                and (
                    sc["candidate"].id not in existing_records
                    or existing_records[sc["candidate"].id].config_id != eval_config.id
                    or len(existing_records[sc["candidate"].id].criterion_results) < len(eval_config.criteria)
                )
            ][:chunk_size]

        evaluated_in_chunk = 0
        failed_in_chunk = 0
        conflicts_flagged = 0
        mandatory_unmet = 0

        records_to_save = []
        scores_to_save = []
        evidence_to_save = []
        evaluated_ids = []

        for item in to_evaluate:
            cand: Candidate = item["candidate"]
            try:
                structured_data = self.candidate_repo.get_structured_data(cand.id)
                record = self.multi_layer_evaluator.evaluate_candidate_record(
                    candidate=cand,
                    job=job,
                    config=eval_config,
                    structured_data=structured_data,
                    session_id=session_id,
                )
                records_to_save.append(record)

                cand_score = self.multi_layer_evaluator.record_to_candidate_score(record, cand.id)
                scores_to_save.append(cand_score)
                evidence_list = self.multi_layer_evaluator._record_to_evidence_list(record, cand.id)
                evidence_to_save.extend(evidence_list)

                evaluated_ids.append(cand.id)
                evaluated_in_chunk += 1

                if record.conflicting_criteria:
                    conflicts_flagged += 1
                if record.unmet_mandatory_criteria:
                    mandatory_unmet += 1

            except Exception as e:
                logger.error(f"Multi-layer evaluation failed for candidate '{cand.id}' ({cand.original_filename}): {e}")
                failed_in_chunk += 1

        if records_to_save:
            self.eval_record_repo.save_batch(records_to_save)
            if hasattr(self.score_repo, "save_scores_batch"):
                self.score_repo.save_scores_batch(scores_to_save)
            else:
                for sc_item in scores_to_save:
                    self.score_repo.save_score(sc_item)
            self.evidence_repo.save_batch(evidence_to_save)
            for c_id in evaluated_ids:
                self.candidate_repo.update_session_candidate_status(
                    session_id=session_id,
                    candidate_id=c_id,
                    status=ProcessingStatus.EVALUATED,
                )

        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 1)

        meta = self._refresh_progress_metadata(session_id)

        remaining_to_eval = sum(
            1 for c in self.candidate_repo.list_by_session(session_id)
            if c["session_status"] in (ProcessingStatus.PENDING, ProcessingStatus.EXTRACTING, ProcessingStatus.COMPLETED)
        )
        if remaining_to_eval == 0 and meta.get("total", 0) > 0:
            self.session_repo.update_status(session_id, SessionStatus.COMPLETED)

        return {
            "session_id": session_id,
            "evaluated_in_chunk": evaluated_in_chunk,
            "failed_in_chunk": failed_in_chunk,
            "conflicts_flagged": conflicts_flagged,
            "mandatory_unmet": mandatory_unmet,
            "remaining_to_evaluate": remaining_to_eval,
            "config_id": eval_config.id,
            "config_version": eval_config.version,
            "elapsed_ms": elapsed_ms,
            "progress_percent": meta.get("percent_complete", 0.0),
        }

    def _ensure_job_criteria(self, job: Job) -> List[EvaluationCriterion]:
        criteria = self.crit_repo.list_by_job(job.id)
        if criteria and len(criteria) >= 3 and sum(c.weight for c in criteria) >= 0.8:
            return criteria

        from core.models.enums import CriterionCategory, CriterionType
        from core.models.evaluation import EvaluationCriterion
        from core.processing.jd_parser import EnhancedJDParser

        jd_parser = EnhancedJDParser()
        jd_struct = jd_parser.parse_job_description(job.original_description, fallback_title=job.title)

        DOMAIN_CRITERIA_NAMES = {
            "healthcare": (
                "Core Clinical & Patient Care Competencies",
                "Clinical Protocols, Medical Tools & Equipment",
                "Clinical Practice & Healthcare Experience",
                "Nursing / Medical Education & Licensure",
            ),
            "culinary": (
                "Culinary Techniques & Food Preparation",
                "Kitchen Equipment, Safety & Food Sanitation",
                "Commercial Kitchen & Restaurant Experience",
                "Culinary Education & Food Safety Certifications",
            ),
            "trades": (
                "Core Trade Skills & Practical Workmanship",
                "Trade Tools, Diagnostics & Safety Standards",
                "Trade Field Experience & Project Track Record",
                "Vocational Training & Trade Licensures",
            ),
            "education": (
                "Curriculum Design & Instructional Competencies",
                "Educational Technology & Classroom Management",
                "Teaching Experience & Classroom Instruction",
                "Academic Degree & Teaching Credentials",
            ),
            "legal": (
                "Legal Analysis, Research & Case Strategy",
                "Contract Drafting, Compliance & Legal Systems",
                "Legal Practice & Case Management Experience",
                "Juris Doctor (J.D.) & Bar Licensure",
            ),
            "finance": (
                "Financial Analysis, Reporting & Accounting",
                "Financial Software, Modeling & Audit Compliance",
                "Accounting & Finance Industry Experience",
                "Finance / Accounting Degree & Certifications (CPA)",
            ),
            "hr": (
                "Talent Acquisition & Employee Relations",
                "HR Information Systems & People Operations",
                "Human Resources & People Management Experience",
                "HR / Business Degree & Certifications (SHRM/PHR)",
            ),
            "sales": (
                "Sales Prospecting, Negotiation & Closing",
                "CRM Systems, Pipeline & Territory Management",
                "Quota Attainment & B2B/B2C Sales Experience",
                "Higher Education & Professional Sales Track Record",
            ),
            "logistics": (
                "Supply Chain Coordination & Inventory Control",
                "Warehouse Management Systems & Equipment",
                "Logistics, Distribution & Fulfillment Experience",
                "Supply Chain Education & Logistics Certifications",
            ),
            "engineering": (
                "Core Engineering Design & Technical Analysis",
                "CAD / CAE Systems & Technical Specifications",
                "Engineering Project Experience & Design Validation",
                "Engineering Degree (ABET) & Professional Licensure",
            ),
            "creative": (
                "Visual Design, Interaction & Creative Concepting",
                "Design Systems, Prototyping & Creative Software",
                "Design Portfolio & Commercial Creative Experience",
                "Design Education & Portfolio Credentials",
            ),
            "tech": (
                "Core Technical & Engineering Competencies",
                "Specialized Frameworks, Databases & Tooling",
                "Software Engineering & Architecture Experience",
                "Technical Degree or Demonstrated Engineering Experience",
            ),
        }

        c1_name, c2_name, c3_name, c4_name = DOMAIN_CRITERIA_NAMES.get(
            jd_struct.domain,
            (
                f"Core Functional Competencies ({job.title or 'Role'})",
                "Domain Tools, Platforms & Methodologies",
                "Relevant Industry Work Experience",
                "Education & Foundational Qualifications",
            ),
        )

        auto_criteria = []

        core_skills_desc = ", ".join(jd_struct.required_skills[:6]) if jd_struct.required_skills else f"Core competencies and functional domain skills for {job.title}"
        auto_criteria.append(
            EvaluationCriterion(
                criterion_name=c1_name,
                description=core_skills_desc,
                weight=0.35,
                criterion_type=CriterionType.REQUIRED,
                category=CriterionCategory.TECHNICAL_SKILL,
            )
        )

        tools_list = jd_struct.preferred_skills if jd_struct.preferred_skills else (jd_struct.required_skills[6:12] if len(jd_struct.required_skills) > 6 else ["Standard Domain Software & Tools"])
        tools_desc = ", ".join(tools_list[:6]) if tools_list else f"Specialized tools, systems and standards for {job.title}"
        auto_criteria.append(
            EvaluationCriterion(
                criterion_name=c2_name,
                description=tools_desc,
                weight=0.25,
                criterion_type=CriterionType.REQUIRED,
                category=CriterionCategory.TECHNICAL_SKILL,
            )
        )

        exp_years = max(2.0, float(jd_struct.min_experience_years or 2.0))
        auto_criteria.append(
            EvaluationCriterion(
                criterion_name=c3_name,
                description=f"Demonstrated professional experience ({int(exp_years)}+ years expected)",
                weight=0.25,
                criterion_type=CriterionType.REQUIRED,
                category=CriterionCategory.EXPERIENCE_DURATION,
                evidence_requirements={"years": exp_years},
            )
        )

        edu_desc = jd_struct.education_level or "Bachelor's degree or equivalent practical industry experience"
        auto_criteria.append(
            EvaluationCriterion(
                criterion_name=c4_name,
                description=edu_desc,
                weight=0.15,
                criterion_type=CriterionType.PREFERRED,
                category=CriterionCategory.EDUCATION_REQUIREMENT,
            )
        )

        self.crit_repo.delete_by_job(job.id) if hasattr(self.crit_repo, "delete_by_job") else None
        self.crit_repo.save_batch(auto_criteria, job.id)
        return auto_criteria

    def _persist_file(self, file_hash: str, filename: str, content: bytes) -> Path:
        safe_name = sanitize_filename(filename)
        dest_dir = self.config.storage_dir / file_hash[:2]
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_file = dest_dir / f"{file_hash}_{safe_name}"
        if not dest_file.exists():
            with open(dest_file, "wb") as f:
                f.write(content)
        return dest_file

    def _refresh_progress_metadata(self, session_id: str) -> Dict[str, Any]:
        candidates = self.candidate_repo.list_by_session(session_id)
        total = len(candidates)
        processed = sum(1 for c in candidates if c["session_status"] in (ProcessingStatus.COMPLETED, ProcessingStatus.EVALUATED))
        evaluated = sum(1 for c in candidates if c["session_status"] == ProcessingStatus.EVALUATED)
        failed = sum(1 for c in candidates if c["session_status"] in (ProcessingStatus.FAILED, ProcessingStatus.DUPLICATE))
        pending = sum(1 for c in candidates if c["session_status"] in (ProcessingStatus.PENDING, ProcessingStatus.EXTRACTING))

        percent = round((processed + failed) / total * 100.0, 1) if total > 0 else 0.0

        meta = {
            "total": total,
            "processed": processed,
            "evaluated": evaluated,
            "failed": failed,
            "pending": pending,
            "percent_complete": percent,
        }
        self.session_repo.update_progress(session_id, meta)
        return meta


    def score_session(
        self, session_id: str, config: Optional[ScoringConfiguration] = None
    ) -> Dict[str, Any]:
        return self.scoring_service.score_session(session_id, config=config)

    def get_ranked_candidates(
        self,
        session_id: str,
        config: Optional[ScoringConfiguration] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[RankedCandidate]:
        return self.scoring_service.get_ranked_candidates(session_id, config=config, filters=filters)

    def get_candidate_quality_assessment(
        self, candidate_id: str, session_id: Optional[str] = None
    ) -> ResumeQualityAssessment:
        existing = self.quality_repo.get_by_candidate(candidate_id)
        if existing:
            return existing

        cand = self.candidate_repo.get(candidate_id)
        if not cand:
            raise ValueError(f"Candidate '{candidate_id}' not found.")

        structured = self.candidate_repo.get_structured_data(candidate_id) or {}
        text = cand.extracted_text or ""
        assessment = self.quality_evaluator.evaluate(
            candidate_id=candidate_id,
            text=text,
            structured_data=structured,
            extraction_meta={
                "ocr_needed": False,
                "is_empty": len(text.strip()) == 0,
                "page_count": 1,
                "char_count": len(text),
            },
            session_id=session_id,
        )
        self.quality_repo.save(assessment)
        return assessment

    def update_shortlist_status(
        self,
        session_id: str,
        candidate_id: str,
        status: ShortlistReviewStatus,
        notes: Optional[str] = None,
    ) -> ShortlistRecord:
        return self.shortlist_service.set_review_status(
            session_id=session_id,
            candidate_id=candidate_id,
            status=status,
            reviewer_notes=notes,
        )

    def list_shortlist(
        self, session_id: str, status: Optional[ShortlistReviewStatus] = None
    ) -> List[ShortlistRecord]:
        return self.shortlist_service.list_session_shortlist(session_id, status=status)

    def simulate_ranking_sensitivity(
        self, session_id: str, new_weights: Dict[str, float]
    ) -> Dict[str, Any]:
        session = self.session_repo.get(session_id)
        if not session:
            return {"success": False, "errors": [f"Session {session_id} not found"]}

        base_config = self.scoring_service.get_or_create_scoring_config(session.job_id)
        eval_records = self.eval_record_repo.list_by_session(session_id)
        candidates = self.candidate_repo.list_by_session(session_id)
        cand_meta = {}
        for item in candidates:
            cand = item["candidate"] if isinstance(item, dict) and "candidate" in item else item
            c_id = getattr(cand, "id", None)
            if c_id:
                fname = getattr(cand, "original_filename", "")
                structured = self.candidate_repo.get_structured_data(c_id) or {}
                contact = structured.get("contact", {}) if isinstance(structured, dict) else {}
                c_name = contact.get("name") if isinstance(contact, dict) else None
                if not c_name:
                    import re, os
                    stem = os.path.splitext(fname)[0]
                    cleaned = re.sub(r"^(resume|cv|candidate)[_\-\s]+", "", stem, flags=re.IGNORECASE)
                    cleaned = re.sub(r"[_\-\s]+(resume|cv)$", "", cleaned, flags=re.IGNORECASE)
                    cleaned = cleaned.replace("_", " ").replace("-", " ").strip()
                    c_name = cleaned.title() if cleaned else stem.title()
                cand_meta[c_id] = (c_name, fname)

        return self.sensitivity_simulator.simulate_weight_changes(
            base_config=base_config,
            evaluation_records=eval_records,
            new_weights=new_weights,
            candidate_meta=cand_meta,
        )

    def generate_candidate_report(
        self, candidate_id: str, session_id: str, include_pii: bool = False
    ) -> CandidateReportData:
        return self.candidate_report_generator.generate(
            candidate_id=candidate_id,
            session_id=session_id,
            include_pii=include_pii,
        )

    def export_candidate_report(
        self,
        candidate_id: str,
        session_id: str,
        export_format: ExportFormat = ExportFormat.PDF,
        include_pii: bool = False,
    ) -> Tuple[bytes, str, GeneratedReportRecord]:
        return self.export_service.export_candidate_report(
            candidate_id=candidate_id,
            session_id=session_id,
            export_format=export_format,
            include_pii=include_pii,
        )

    def generate_session_report(self, session_id: str) -> SessionSummaryReportData:
        return self.session_report_generator.generate(session_id=session_id)

    def export_session_report(
        self,
        session_id: str,
        export_format: ExportFormat = ExportFormat.PDF,
    ) -> Tuple[bytes, str, GeneratedReportRecord]:
        return self.export_service.export_session_report(
            session_id=session_id,
            export_format=export_format,
        )

    def generate_candidate_comparison(
        self,
        candidate_ids: List[str],
        session_id: str,
        selected_criterion_ids: Optional[List[str]] = None,
    ) -> CandidateComparisonData:
        return self.candidate_comparison_service.compare_candidates(
            candidate_ids=candidate_ids,
            session_id=session_id,
            selected_criterion_ids=selected_criterion_ids,
        )

    def export_candidate_comparison(
        self,
        candidate_ids: List[str],
        session_id: str,
        export_format: ExportFormat = ExportFormat.PDF,
        selected_criterion_ids: Optional[List[str]] = None,
    ) -> Tuple[bytes, str, GeneratedReportRecord]:
        return self.export_service.export_comparison_report(
            candidate_ids=candidate_ids,
            session_id=session_id,
            export_format=export_format,
            selected_criterion_ids=selected_criterion_ids,
        )

    def generate_shortlist_report(
        self, session_id: str, filter_status: Optional[ShortlistReviewStatus] = None
    ) -> ShortlistReportData:
        return self.shortlist_report_generator.generate(
            session_id=session_id,
            filter_status=filter_status,
        )

    def export_shortlist_report(
        self,
        session_id: str,
        export_format: ExportFormat = ExportFormat.PDF,
    ) -> Tuple[bytes, str, GeneratedReportRecord]:
        return self.export_service.export_shortlist_report(
            session_id=session_id,
            export_format=export_format,
        )

    def get_session_insights(self, session_id: str) -> Dict[str, Any]:
        return self.insights_service.get_session_insights(session_id=session_id)

    def list_generated_reports(
        self, session_id: str, report_type: Optional[ReportType] = None
    ) -> List[GeneratedReportRecord]:
        return self.report_repo.list_by_session(session_id=session_id, report_type=report_type)


    def get_portfolio_analytics(
        self, filters: Optional[AnalyticsFilter] = None
    ) -> PortfolioAnalytics:
        return self.portfolio_analytics_service.get_portfolio_analytics(filters=filters)

    def get_session_analytics_profile(
        self, session_id: str, filters: Optional[AnalyticsFilter] = None
    ) -> SessionAnalytics:
        return self.session_analytics_service.get_session_analytics(session_id=session_id, filters=filters)

    def get_skill_coverage_analytics(self, session_id: str) -> List[SkillCoverageItem]:
        return self.skill_analytics_service.analyze_session_skills(session_id=session_id)

    def get_criterion_analytics(self, session_id: str) -> List[CriterionAnalytics]:
        return self.criterion_analytics_service.analyze_session_criteria(session_id=session_id)

    def compare_sessions_analytics(self, session_ids: List[str]) -> SessionComparisonAnalytics:
        return self.session_comparison_analytics_service.compare_sessions(session_ids=session_ids)

    def export_session_analytics(
        self,
        session_id: str,
        export_format: ExportFormat = ExportFormat.CSV,
        filters: Optional[AnalyticsFilter] = None,
    ) -> Tuple[bytes, str]:
        analytics = self.get_session_analytics_profile(session_id=session_id, filters=filters)
        filters_meta = filters.to_dict() if filters else {}
        if export_format == ExportFormat.XLSX:
            return self.analytics_export_service.export_session_analytics_xlsx(analytics, filters_meta)
        return self.analytics_export_service.export_session_analytics_csv(analytics, filters_meta)

    def export_portfolio_analytics(
        self, filters: Optional[AnalyticsFilter] = None
    ) -> Tuple[bytes, str]:
        analytics = self.get_portfolio_analytics(filters=filters)
        filters_meta = filters.to_dict() if filters else {}
        return self.analytics_export_service.export_portfolio_analytics_csv(analytics, filters_meta)

    def export_comparison_analytics(
        self, session_ids: List[str]
    ) -> Tuple[bytes, str]:
        comp = self.compare_sessions_analytics(session_ids=session_ids)
        return self.analytics_export_service.export_comparison_analytics_csv(comp)


    def list_lab_models(
        self,
        task: Optional[TaskType] = None,
        model_type: Optional[str] = None,
    ) -> List[ModelMetadata]:
        return self.model_registry.list_models(task=task, model_type=model_type)

    def load_lab_model(self, model_id: str, device: str = "cpu") -> Any:
        return self.model_registry.load_model(model_id=model_id, device=device)

    def unload_lab_model(self, model_id: str) -> bool:
        return self.model_registry.unload_model(model_id=model_id)

    def clear_all_lab_models(self) -> None:
        self.model_registry.clear_all()

    def run_model_benchmark(
        self,
        config: BenchmarkConfiguration,
        run_name: Optional[str] = None,
    ) -> BenchmarkRunRecord:
        return self.benchmark_runner.run_benchmark(config=config, run_name=run_name)

    def get_benchmark_run(self, run_id: str) -> Optional[BenchmarkRunRecord]:
        return self.benchmark_run_repo.get_run(run_id)

    def list_benchmark_runs(
        self,
        dataset_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> List[BenchmarkRunRecord]:
        return self.benchmark_run_repo.list_runs(dataset_id=dataset_id, session_id=session_id)

    def list_evaluation_datasets(
        self, task: Optional[TaskType] = None
    ) -> List[EvaluationDataset]:
        return self.evaluation_dataset_service.list_datasets(task=task)

    def get_evaluation_dataset(
        self, dataset_id: str, load_items: bool = True
    ) -> Optional[EvaluationDataset]:
        return self.evaluation_dataset_service.get_dataset(dataset_id, load_items=load_items)

    def create_evaluation_dataset(
        self,
        name: str,
        version: str = "v1.0",
        task: TaskType = TaskType.SEMANTIC_RETRIEVAL,
        description: str = "",
        rubric_version: str = "rubric-v1.0",
        created_by: str = "Authorized Reviewer",
        items: Optional[List[EvaluationDatasetItem]] = None,
    ) -> EvaluationDataset:
        return self.evaluation_dataset_service.create_dataset(
            name=name,
            version=version,
            task=task,
            description=description,
            rubric_version=rubric_version,
            created_by=created_by,
            items=items,
        )



