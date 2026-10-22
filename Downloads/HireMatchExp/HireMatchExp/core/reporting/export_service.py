
from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple

from config import AppConfig, settings
from core.models.report_models import (
    CandidateComparisonData,
    CandidateReportData,
    ExportFormat,
    GeneratedReportRecord,
    ReportType,
    SessionSummaryReportData,
    ShortlistReportData,
)
from core.reporting.candidate_report import CandidateReportGenerator
from core.reporting.comparison_service import CandidateComparisonService
from core.reporting.formatters import (
    CSVReportFormatter,
    PDFReportFormatter,
    XLSXReportFormatter,
)
from core.reporting.session_report import SessionSummaryReportGenerator
from core.reporting.shortlist_report import ShortlistReportGenerator
from core.storage.database import Database
from core.storage.report_repository import ReportRecordRepository
from core.utils.logger import logger


class ReportExportService:

    def __init__(self, db: Database, config: Optional[AppConfig] = None):
        self.db = db
        self.config = config or settings
        self.reports_dir = self.config.reports_dir
        self.reports_dir.mkdir(parents=True, exist_ok=True)

        self.candidate_generator = CandidateReportGenerator(db)
        self.session_generator = SessionSummaryReportGenerator(db)
        self.comparison_service = CandidateComparisonService(db)
        self.shortlist_generator = ShortlistReportGenerator(db)
        self.report_repo = ReportRecordRepository(db)

    def export_candidate_report(
        self,
        candidate_id: str,
        session_id: str,
        export_format: ExportFormat = ExportFormat.PDF,
        include_pii: bool = False,
    ) -> Tuple[bytes, str, GeneratedReportRecord]:
        data = self.candidate_generator.generate(
            candidate_id=candidate_id,
            session_id=session_id,
            include_pii=include_pii,
        )

        content_bytes = self._serialize_report(data, ReportType.INDIVIDUAL_CANDIDATE, export_format)

        cand_clean = self._sanitize_filename(data.candidate_reference)
        filename = f"candidate_report_{cand_clean}_{data.report_id[:8]}.{export_format.value.lower()}"
        file_path = self.reports_dir / filename

        with open(file_path, "wb") as f:
            f.write(content_bytes)

        record = GeneratedReportRecord(
            id=data.report_id,
            report_type=ReportType.INDIVIDUAL_CANDIDATE,
            session_id=session_id,
            candidate_ids=[candidate_id],
            eval_config_version=data.scoring_config_version,
            scoring_config_version=data.scoring_config_version,
            export_format=export_format,
            file_path=str(file_path),
            metadata={
                "candidate_reference": data.candidate_reference,
                "overall_score": data.overall_score,
                "include_pii": include_pii,
            },
            created_at=data.generated_at,
        )
        self.report_repo.save(record)
        return content_bytes, str(file_path), record

    def export_session_report(
        self,
        session_id: str,
        export_format: ExportFormat = ExportFormat.PDF,
    ) -> Tuple[bytes, str, GeneratedReportRecord]:
        data = self.session_generator.generate(session_id=session_id)

        content_bytes = self._serialize_report(data, ReportType.SESSION_SUMMARY, export_format)

        sess_clean = self._sanitize_filename(data.session_name)
        filename = f"session_summary_{sess_clean}_{data.report_id[:8]}.{export_format.value.lower()}"
        file_path = self.reports_dir / filename

        with open(file_path, "wb") as f:
            f.write(content_bytes)

        candidate_ids = [c["candidate_id"] for c in data.candidate_summaries]
        record = GeneratedReportRecord(
            id=data.report_id,
            report_type=ReportType.SESSION_SUMMARY,
            session_id=session_id,
            candidate_ids=candidate_ids,
            eval_config_version=data.scoring_config_version,
            scoring_config_version=data.scoring_config_version,
            export_format=export_format,
            file_path=str(file_path),
            metadata={
                "total_enrolled": data.total_resumes_enrolled,
                "completed_evaluations": data.completed_evaluation_count,
            },
            created_at=data.generated_at,
        )
        self.report_repo.save(record)
        return content_bytes, str(file_path), record

    def export_comparison_report(
        self,
        candidate_ids: List[str],
        session_id: str,
        export_format: ExportFormat = ExportFormat.PDF,
        selected_criterion_ids: Optional[List[str]] = None,
    ) -> Tuple[bytes, str, GeneratedReportRecord]:
        data = self.comparison_service.compare_candidates(
            candidate_ids=candidate_ids,
            session_id=session_id,
            selected_criterion_ids=selected_criterion_ids,
        )

        content_bytes = self._serialize_report(data, ReportType.CANDIDATE_COMPARISON, export_format)

        filename = f"candidate_comparison_{session_id[:8]}_{data.report_id[:8]}.{export_format.value.lower()}"
        file_path = self.reports_dir / filename

        with open(file_path, "wb") as f:
            f.write(content_bytes)

        record = GeneratedReportRecord(
            id=data.report_id,
            report_type=ReportType.CANDIDATE_COMPARISON,
            session_id=session_id,
            candidate_ids=candidate_ids,
            eval_config_version=data.compatibility.shared_config_version or "mixed",
            scoring_config_version=data.compatibility.shared_config_version or "mixed",
            export_format=export_format,
            file_path=str(file_path),
            metadata={
                "compared_count": len(candidate_ids),
                "is_compatible": data.compatibility.is_compatible,
            },
            created_at=data.generated_at,
        )
        self.report_repo.save(record)
        return content_bytes, str(file_path), record

    def export_shortlist_report(
        self,
        session_id: str,
        export_format: ExportFormat = ExportFormat.PDF,
    ) -> Tuple[bytes, str, GeneratedReportRecord]:
        data = self.shortlist_generator.generate(session_id=session_id)

        content_bytes = self._serialize_report(data, ReportType.SHORTLIST_REPORT, export_format)

        filename = f"shortlist_report_{session_id[:8]}_{data.report_id[:8]}.{export_format.value.lower()}"
        file_path = self.reports_dir / filename

        with open(file_path, "wb") as f:
            f.write(content_bytes)

        candidate_ids = [item.candidate_id for item in data.items]
        record = GeneratedReportRecord(
            id=data.report_id,
            report_type=ReportType.SHORTLIST_REPORT,
            session_id=session_id,
            candidate_ids=candidate_ids,
            export_format=export_format,
            file_path=str(file_path),
            metadata={"shortlisted_total": data.total_shortlisted_count},
            created_at=data.generated_at,
        )
        self.report_repo.save(record)
        return content_bytes, str(file_path), record

    def _serialize_report(self, data: Any, report_type: ReportType, export_format: ExportFormat) -> bytes:
        if export_format == ExportFormat.PDF:
            if report_type == ReportType.INDIVIDUAL_CANDIDATE:
                return PDFReportFormatter.format_candidate_report(data)
            elif report_type == ReportType.SESSION_SUMMARY:
                return PDFReportFormatter.format_session_report(data)
            elif report_type == ReportType.CANDIDATE_COMPARISON:
                return PDFReportFormatter.format_comparison_report(data)
            elif report_type == ReportType.SHORTLIST_REPORT:
                return PDFReportFormatter.format_shortlist_report(data)

        elif export_format == ExportFormat.CSV:
            if report_type == ReportType.INDIVIDUAL_CANDIDATE:
                return CSVReportFormatter.format_candidate_report(data).encode("utf-8")
            elif report_type == ReportType.SESSION_SUMMARY:
                return CSVReportFormatter.format_session_report(data).encode("utf-8")
            elif report_type == ReportType.CANDIDATE_COMPARISON:
                return CSVReportFormatter.format_comparison_report(data).encode("utf-8")
            elif report_type == ReportType.SHORTLIST_REPORT:
                return CSVReportFormatter.format_shortlist_report(data).encode("utf-8")

        elif export_format == ExportFormat.XLSX:
            if report_type == ReportType.INDIVIDUAL_CANDIDATE:
                return XLSXReportFormatter.format_candidate_report(data)
            elif report_type == ReportType.SESSION_SUMMARY:
                return XLSXReportFormatter.format_session_report(data)
            elif report_type == ReportType.CANDIDATE_COMPARISON:
                return XLSXReportFormatter.format_comparison_report(data)
            elif report_type == ReportType.SHORTLIST_REPORT:
                return XLSXReportFormatter.format_shortlist_report(data)

        elif export_format == ExportFormat.JSON:
            return json.dumps(data.to_dict(), indent=2).encode("utf-8")

        raise ValueError(f"Unsupported report serialization: {report_type} to {export_format}")

    def _sanitize_filename(self, name: str) -> str:
        cleaned = re.sub(r"[^\w\-_.]", "_", name.strip())
        return cleaned[:30]
