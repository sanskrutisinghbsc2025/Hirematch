
import csv
import io
from typing import Any, Dict, List, Optional

from core.models.report_models import (
    CandidateComparisonData,
    CandidateReportData,
    SessionSummaryReportData,
    ShortlistReportData,
)


class CSVReportFormatter:

    @staticmethod
    def format_candidate_report(data: CandidateReportData) -> str:
        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow(["# HireMatch Candidate Evaluation Dossier"])
        writer.writerow(["# Candidate Reference", data.candidate_reference])
        writer.writerow(["# Original Filename", data.original_filename])
        writer.writerow(["# Target Job", data.job_title])
        writer.writerow(["# Screening Session", data.session_name])
        writer.writerow(["# Overall Score", data.overall_score if data.overall_score is not None else ""])
        writer.writerow(["# Evidence Coverage (%)", data.evidence_coverage])
        writer.writerow(["# Resume Quality Score", data.resume_quality_score if data.resume_quality_score is not None else ""])
        writer.writerow(["# Resume Quality Label", data.resume_quality_label or ""])
        writer.writerow(["# Completeness Status", data.completeness_status])
        writer.writerow(["# Scoring Config Version", data.scoring_config_version])
        writer.writerow(["# Review Status", data.review_status])
        writer.writerow(["# Reviewer Notes", data.reviewer_notes])
        writer.writerow([])

        writer.writerow([
            "criterion_id",
            "criterion_name",
            "category",
            "criterion_type",
            "configured_weight",
            "support_value",
            "normalized_points",
            "match_status",
            "matching_method",
            "is_eligible",
            "exclusion_reason",
            "explanation",
            "evidence_snippets",
        ])

        for c in data.criterion_items:
            cat_name = c.category.value if hasattr(c.category, "value") else str(c.category)
            type_name = c.criterion_type.value if hasattr(c.criterion_type, "value") else str(c.criterion_type)
            status_name = c.match_status.value if hasattr(c.match_status, "value") else str(c.match_status)
            ev_joined = " | ".join(c.supporting_evidence)

            writer.writerow([
                c.criterion_id,
                c.criterion_name,
                cat_name,
                type_name,
                c.configured_weight,
                c.support_value,
                c.normalized_points,
                status_name,
                c.matching_method,
                c.is_eligible,
                c.exclusion_reason or "",
                c.explanation or "",
                ev_joined,
            ])

        return output.getvalue()

    @staticmethod
    def format_session_report(data: SessionSummaryReportData) -> str:
        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow(["# HireMatch Screening Session Summary"])
        writer.writerow(["# Session Name", data.session_name])
        writer.writerow(["# Session ID", data.session_id])
        writer.writerow(["# Target Role", data.job_title])
        writer.writerow(["# Total Enrolled", data.total_resumes_enrolled])
        writer.writerow(["# Completed Processing", data.completed_processing_count])
        writer.writerow(["# Failed Processing", data.failed_processing_count])
        writer.writerow(["# Scoring Config Version", data.scoring_config_version])
        if data.coverage_limitation_warning:
            writer.writerow(["# Coverage Warning", data.coverage_limitation_warning])
        writer.writerow([])

        writer.writerow([
            "candidate_id",
            "candidate_reference",
            "original_filename",
            "processing_status",
            "overall_score",
            "evidence_coverage",
            "resume_quality_score",
            "resume_quality_label",
            "review_status",
            "reviewer_notes",
        ])

        for c in data.candidate_summaries:
            writer.writerow([
                c["candidate_id"],
                c["candidate_reference"],
                c["original_filename"],
                c["processing_status"],
                c["overall_score"] if c["overall_score"] is not None else "",
                c["evidence_coverage"],
                c.get("resume_quality_score", ""),
                c.get("resume_quality_label", ""),
                c["review_status"],
                c["reviewer_notes"],
            ])

        return output.getvalue()

    @staticmethod
    def format_comparison_report(data: CandidateComparisonData) -> str:
        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow(["# HireMatch Candidate Comparison Matrix"])
        writer.writerow(["# Target Role", data.job_title])
        writer.writerow(["# Session Name", data.session_name])
        writer.writerow(["# Evaluation Compatible", data.compatibility.is_compatible])
        for w in data.compatibility.compatibility_warnings:
            writer.writerow(["# Compatibility Warning", w])
        writer.writerow([])

        headers = ["criterion_id", "criterion_name", "category", "criterion_type", "weight", "meaningful_difference"]
        for h in data.candidate_headers:
            ref = h["candidate_reference"]
            headers.extend([f"{ref}_status", f"{ref}_points", f"{ref}_support"])

        writer.writerow(headers)

        for row in data.aligned_criteria_rows:
            cat_name = row.category.value if hasattr(row.category, "value") else str(row.category)
            type_name = row.criterion_type.value if hasattr(row.criterion_type, "value") else str(row.criterion_type)
            row_data = [
                row.criterion_id,
                row.criterion_name,
                cat_name,
                type_name,
                row.configured_weight,
                row.has_meaningful_difference,
            ]
            for h in data.candidate_headers:
                eval_item = row.candidate_evaluations.get(h["candidate_id"], {})
                row_data.extend([
                    eval_item.get("match_status", "N/A"),
                    eval_item.get("normalized_points", ""),
                    eval_item.get("support_value", ""),
                ])
            writer.writerow(row_data)

        return output.getvalue()

    @staticmethod
    def format_shortlist_report(data: ShortlistReportData) -> str:
        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow(["# HireMatch Recruiter Shortlist Report"])
        writer.writerow(["# Session Name", data.session_name])
        writer.writerow(["# Target Role", data.job_title])
        writer.writerow(["# Total Candidates", data.total_shortlisted_count])
        writer.writerow([])

        writer.writerow([
            "candidate_id",
            "candidate_reference",
            "original_filename",
            "review_status",
            "overall_score",
            "evidence_coverage",
            "key_evidence_highlights",
            "reviewer_notes",
            "updated_at",
        ])

        for item in data.items:
            writer.writerow([
                item.candidate_id,
                item.candidate_reference,
                item.original_filename,
                item.review_status.value if hasattr(item.review_status, "value") else str(item.review_status),
                item.overall_score if item.overall_score is not None else "",
                item.evidence_coverage,
                " | ".join(item.key_evidence_highlights),
                item.reviewer_notes,
                item.updated_at,
            ])

        return output.getvalue()
