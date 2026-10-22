
from typing import Any, Dict, List, Optional, Tuple

try:
    import pymupdf as fitz
except ImportError:
    import fitz

from core.models.report_models import (
    CandidateComparisonData,
    CandidateReportData,
    SessionSummaryReportData,
    ShortlistReportData,
)


class PDFBuilder:

    def __init__(self, page_width: float = 595.0, page_height: float = 842.0):
        self.doc = fitz.open()
        self.width = page_width
        self.height = page_height
        self.margin = 36.0
        self.printable_width = self.width - 2 * self.margin
        self.current_page = None
        self.y = self.margin
        self._new_page()

    def _new_page(self):
        self.current_page = self.doc.new_page(width=self.width, height=self.height)
        self.y = self.margin

        self.current_page.draw_line(
            fitz.Point(self.margin, 28),
            fitz.Point(self.width - self.margin, 28),
            color=(0.8, 0.82, 0.85),
            width=0.75,
        )
        self.current_page.insert_text(
            fitz.Point(self.margin, 24),
            "HireMatch Recruitment Intelligence Report",
            fontsize=7,
            color=(0.4, 0.45, 0.5),
        )

    def check_page_break(self, needed_height: float):
        if self.y + needed_height > self.height - 45.0:
            self._new_page()

    def add_title_block(self, title: str, subtitle: str, meta_badges: List[str]):
        self.check_page_break(75)
        rect = fitz.Rect(self.margin, self.y, self.width - self.margin, self.y + 65)
        self.current_page.draw_rect(rect, color=(0.1, 0.15, 0.25), fill=(0.95, 0.96, 0.98), width=0.5)

        self.current_page.insert_text(
            fitz.Point(self.margin + 12, self.y + 22),
            title,
            fontsize=15,
            color=(0.08, 0.12, 0.2),
        )
        self.current_page.insert_text(
            fitz.Point(self.margin + 12, self.y + 38),
            subtitle,
            fontsize=9,
            color=(0.35, 0.4, 0.45),
        )
        badges_str = "  •  ".join(meta_badges)
        self.current_page.insert_text(
            fitz.Point(self.margin + 12, self.y + 54),
            badges_str,
            fontsize=8,
            color=(0.2, 0.35, 0.55),
        )
        self.y += 75

    def add_section_header(self, text: str):
        self.check_page_break(35)
        self.y += 6
        self.current_page.draw_line(
            fitz.Point(self.margin, self.y),
            fitz.Point(self.width - self.margin, self.y),
            color=(0.85, 0.87, 0.9),
            width=1.0,
        )
        self.y += 14
        self.current_page.insert_text(
            fitz.Point(self.margin, self.y),
            text.upper(),
            fontsize=10,
            color=(0.15, 0.25, 0.4),
        )
        self.y += 12

    def add_metric_row(self, metrics: List[Tuple[str, str]]):
        self.check_page_break(45)
        col_w = self.printable_width / len(metrics)
        for i, (lbl, val) in enumerate(metrics):
            box_x = self.margin + i * col_w
            rect = fitz.Rect(box_x, self.y, box_x + col_w - 6, self.y + 38)
            self.current_page.draw_rect(rect, color=(0.85, 0.88, 0.92), fill=(0.98, 0.98, 0.99), width=0.5)

            self.current_page.insert_text(
                fitz.Point(box_x + 8, self.y + 14),
                lbl[:30],
                fontsize=7.5,
                color=(0.45, 0.5, 0.55),
            )
            self.current_page.insert_text(
                fitz.Point(box_x + 8, self.y + 30),
                str(val)[:24],
                fontsize=12,
                color=(0.1, 0.15, 0.25),
            )
        self.y += 45

    def add_bullet(self, label: str, value: str):
        self.check_page_break(18)
        self.current_page.insert_text(
            fitz.Point(self.margin + 8, self.y),
            f"• {label}:",
            fontsize=8.5,
            color=(0.2, 0.25, 0.3),
        )
        val_point = fitz.Point(self.margin + 130, self.y)
        self.current_page.insert_text(
            val_point,
            str(value)[:110],
            fontsize=8.5,
            color=(0.35, 0.4, 0.45),
        )
        self.y += 14

    def add_card(self, title: str, lines: List[str], bg_color: Tuple[float, float, float] = (0.97, 0.98, 0.99)):
        h = 24 + len(lines) * 13
        self.check_page_break(h + 8)
        rect = fitz.Rect(self.margin, self.y, self.width - self.margin, self.y + h)
        self.current_page.draw_rect(rect, color=(0.82, 0.85, 0.88), fill=bg_color, width=0.5)

        self.current_page.insert_text(
            fitz.Point(self.margin + 10, self.y + 14),
            title,
            fontsize=9,
            color=(0.1, 0.15, 0.25),
        )

        cur_y = self.y + 26
        for line in lines:
            self.current_page.insert_text(
                fitz.Point(self.margin + 10, cur_y),
                line[:120],
                fontsize=8,
                color=(0.3, 0.35, 0.4),
            )
            cur_y += 13
        self.y += h + 8

    def add_table(self, headers: List[str], rows: List[List[str]], col_widths: List[float]):
        row_height = 18.0
        header_height = 20.0

        self.check_page_break(header_height + row_height * min(len(rows), 3))
        header_rect = fitz.Rect(self.margin, self.y, self.width - self.margin, self.y + header_height)
        self.current_page.draw_rect(header_rect, color=(0.7, 0.75, 0.8), fill=(0.92, 0.94, 0.96), width=0.5)

        cur_x = self.margin + 6
        for idx, h_text in enumerate(headers):
            w = col_widths[idx]
            self.current_page.insert_text(
                fitz.Point(cur_x, self.y + 13),
                h_text,
                fontsize=8,
                color=(0.15, 0.2, 0.3),
            )
            cur_x += w
        self.y += header_height

        for r_idx, row in enumerate(rows):
            self.check_page_break(row_height)
            bg = (1.0, 1.0, 1.0) if r_idx % 2 == 0 else (0.97, 0.98, 0.99)
            row_rect = fitz.Rect(self.margin, self.y, self.width - self.margin, self.y + row_height)
            self.current_page.draw_rect(row_rect, color=(0.88, 0.9, 0.92), fill=bg, width=0.25)

            cur_x = self.margin + 6
            for idx, cell in enumerate(row):
                w = col_widths[idx]
                self.current_page.insert_text(
                    fitz.Point(cur_x, self.y + 12),
                    str(cell)[: int(w / 5.5)],
                    fontsize=7.5,
                    color=(0.25, 0.3, 0.35),
                )
                cur_x += w
            self.y += row_height
        self.y += 8

    def finalize(self, disclaimer_text: str = "") -> bytes:
        total_pages = len(self.doc)
        for idx, page in enumerate(self.doc):
            p_num = idx + 1
            page.draw_line(
                fitz.Point(self.margin, self.height - 30),
                fitz.Point(self.width - self.margin, self.height - 30),
                color=(0.82, 0.85, 0.88),
                width=0.75,
            )
            page.insert_text(
                fitz.Point(self.margin, self.height - 20),
                "Decision Support Report - Human Recruiter Retains Final Hiring Authority",
                fontsize=6.5,
                color=(0.45, 0.5, 0.55),
            )
            p_str = f"Page {p_num} of {total_pages}"
            page.insert_text(
                fitz.Point(self.width - self.margin - 50, self.height - 20),
                p_str,
                fontsize=7.5,
                color=(0.4, 0.45, 0.5),
            )
        return self.doc.tobytes()


class PDFReportFormatter:

    @staticmethod
    def format_candidate_report(data: CandidateReportData) -> bytes:
        builder = PDFBuilder()

        score_display = f"{data.overall_score:.1f}%" if data.overall_score is not None else "N/A"
        builder.add_title_block(
            title=f"Candidate Evaluation Dossier: {data.candidate_reference}",
            subtitle=f"Target Requisition: {data.job_title} | Session: {data.session_name}",
            meta_badges=[
                f"Status: {data.review_status}",
                f"Score: {score_display}",
                f"Coverage: {data.evidence_coverage:.1f}%",
                f"Config: {data.scoring_config_version}",
            ],
        )

        builder.add_section_header("1. Evaluation Summary")
        builder.add_metric_row([
            ("Overall Score", score_display),
            ("Evidence Coverage", f"{data.evidence_coverage:.1f}%"),
            ("Supported Criteria", f"{data.supported_criteria_count} / {data.total_criteria_count}"),
            ("Conflicts Detected", str(data.conflicting_criteria_count)),
        ])

        builder.add_bullet("Candidate File", data.original_filename)
        builder.add_bullet("Evaluation Status", data.evaluation_status)
        builder.add_bullet("Score Completeness", data.completeness_status)
        if data.contact_info:
            builder.add_bullet("Candidate Identity", data.contact_info.get("name", "N/A"))
            builder.add_bullet("Contact Details", f"{data.contact_info.get('email', '')} | {data.contact_info.get('phone', '')}")

        builder.add_section_header("2. Recruiter Shortlist & Review Notes")
        note_text = data.reviewer_notes if data.reviewer_notes else "No reviewer notes recorded."
        builder.add_card(
            f"Review Status: {data.review_status}",
            [f"Justification Notes: {note_text}", f"Last Updated: {data.shortlist_updated_at or data.generated_at[:10]}"],
            bg_color=(0.95, 0.97, 1.0),
        )

        builder.add_section_header("3. Criterion-Level Evaluation Breakdown")
        crit_headers = ["Criterion Name", "Category", "Type", "Weight", "Status", "Points"]
        crit_rows = []
        for c in data.criterion_items:
            cat_name = c.category.value if hasattr(c.category, "value") else str(c.category)
            t_name = "Req" if c.criterion_type.value == "REQUIRED" else "Pref"
            crit_rows.append([
                c.criterion_name,
                cat_name.replace("_", " ").title()[:14],
                t_name,
                f"{int(c.configured_weight * 100)}%",
                c.match_status.value if hasattr(c.match_status, "value") else str(c.match_status),
                f"{c.normalized_points:.1f} pts",
            ])

        col_w = [140.0, 90.0, 45.0, 50.0, 115.0, 75.0]
        builder.add_table(crit_headers, crit_rows, col_w)

        builder.add_section_header("4. Key Evidence Citations")
        has_citations = False
        for c in data.criterion_items:
            if c.supporting_evidence:
                has_citations = True
                ev_lines = [f'"{snippet}"' for snippet in c.supporting_evidence[:2]]
                if c.source_sections:
                    ev_lines.append(f"Source Sections: {', '.join(c.source_sections)}")
                builder.add_card(f"Evidence for: {c.criterion_name} ({c.match_status.value})", ev_lines)

        if not has_citations:
            builder.add_card("Evidence Summary", ["No verified verbatim citations found in resume text."])

        builder.add_section_header("5. Parsed Resume Background")
        skills_str = ", ".join(data.extracted_skills[:16]) if data.extracted_skills else "No technical skills parsed"
        builder.add_bullet("Extracted Skills", skills_str)

        exp_titles = [f"{e.get('job_title', 'Role')} ({e.get('employer', 'Co')})" for e in data.work_experience[:4]]
        builder.add_bullet("Work Experience", "; ".join(exp_titles) if exp_titles else "No employment records parsed")

        edu_degrees = [f"{ed.get('qualification', 'Degree')} - {ed.get('institution', 'School')}" for ed in data.education[:3]]
        builder.add_bullet("Education", "; ".join(edu_degrees) if edu_degrees else "No academic records parsed")

        if data.evaluation_warnings or data.evidence_limitations:
            builder.add_section_header("6. Warnings & Limitations")
            all_warns = data.evaluation_warnings + data.evidence_limitations
            for w in all_warns:
                builder.add_bullet("Audit Notice", w)

        return builder.finalize()

    @staticmethod
    def format_session_report(data: SessionSummaryReportData) -> bytes:
        builder = PDFBuilder()

        builder.add_title_block(
            title=f"Screening Session Summary: {data.session_name}",
            subtitle=f"Role: {data.job_title} ({data.department}) | Session ID: {data.session_id[:8]}",
            meta_badges=[
                f"Resumes: {data.total_resumes_enrolled}",
                f"Evaluated: {data.completed_evaluation_count}",
                f"Config: {data.scoring_config_version}",
                f"Date: {data.session_created_at[:10]}",
            ],
        )

        builder.add_section_header("1. Ingestion & Processing Pipeline")
        builder.add_metric_row([
            ("Total Enrolled", str(data.total_resumes_enrolled)),
            ("Extracted Successfully", str(data.completed_processing_count)),
            ("Failed Parsing", str(data.failed_processing_count)),
            ("Evaluated & Scored", str(data.completed_evaluation_count)),
        ])

        if data.coverage_limitation_warning:
            builder.add_card("Processing Coverage Limitation", [data.coverage_limitation_warning], bg_color=(1.0, 0.96, 0.92))

        builder.add_section_header("2. Score Distribution & Quality Tiers")
        sd = data.score_distribution
        mean_str = f"{sd.get('mean', 0.0):.1f}%" if sd.get("mean") is not None else "N/A"
        med_str = f"{sd.get('median', 0.0):.1f}%" if sd.get("median") is not None else "N/A"
        min_str = f"{sd.get('min', 0.0):.1f}%" if sd.get("min") is not None else "N/A"
        max_str = f"{sd.get('max', 0.0):.1f}%" if sd.get("max") is not None else "N/A"

        builder.add_metric_row([
            ("Mean Score", mean_str),
            ("Median Score", med_str),
            ("Min Score", min_str),
            ("Max Score", max_str),
        ])

        tiers = sd.get("tiers", {})
        builder.add_bullet("High Alignment (>= 80%)", f"{tiers.get('High Alignment (>= 80)', 0)} candidates")
        builder.add_bullet("Moderate Alignment (60 - 79%)", f"{tiers.get('Moderate Alignment (60 - 79)', 0)} candidates")
        builder.add_bullet("Low Alignment (< 60%)", f"{tiers.get('Low Alignment (< 60)', 0)} candidates")
        builder.add_bullet("Insufficient Evidence", f"{tiers.get('Insufficient Data', 0)} candidates")

        builder.add_section_header("3. Criterion Capability Summary (Pool-Wide)")
        cp_headers = ["Criterion Name", "Category", "Supported %", "Partial %", "Insufficient %"]
        cp_rows = []
        for cp in data.criterion_performance[:8]:
            cp_rows.append([
                cp["criterion_name"],
                cp["category"].replace("_", " ").title()[:14],
                f"{cp['supported_pct']:.1f}%",
                f"{cp['partial_pct']:.1f}%",
                f"{cp['insufficient_pct']:.1f}%",
            ])
        col_w = [170.0, 110.0, 75.0, 75.0, 85.0]
        builder.add_table(cp_headers, cp_rows, col_w)

        builder.add_section_header("4. Recruiter Shortlist Status Distribution")
        sl = data.shortlist_summary
        builder.add_metric_row([
            ("Shortlisted", str(sl.get("SHORTLISTED", 0))),
            ("In Review", str(sl.get("IN_REVIEW", 0))),
            ("Needs Review", str(sl.get("NEEDS_REVIEW", 0))),
            ("On Hold", str(sl.get("ON_HOLD", 0))),
        ])

        builder.add_section_header("5. Candidate Manifest Ranks & Scores")
        c_headers = ["Ref", "Filename", "Score", "Coverage", "Review Status"]
        c_rows = []
        for c in data.candidate_summaries[:15]:
            score_s = f"{c['overall_score']:.1f}%" if c["overall_score"] is not None else "N/A"
            c_rows.append([
                c["candidate_reference"],
                c["original_filename"][:26],
                score_s,
                f"{c['evidence_coverage']:.1f}%",
                c["review_status"],
            ])
        c_col_w = [90.0, 175.0, 75.0, 75.0, 100.0]
        builder.add_table(c_headers, c_rows, c_col_w)

        return builder.finalize()

    @staticmethod
    def format_comparison_report(data: CandidateComparisonData) -> bytes:
        builder = PDFBuilder()

        cand_refs = [h["candidate_reference"] for h in data.candidate_headers]
        builder.add_title_block(
            title=f"Side-by-Side Candidate Comparison ({len(cand_refs)} Candidates)",
            subtitle=f"Requisition: {data.job_title} | Session: {data.session_name}",
            meta_badges=[
                f"Candidates: {', '.join(cand_refs)}",
                f"Compatible: {'YES' if data.compatibility.is_compatible else 'NO'}",
                f"Generated: {data.generated_at[:10]}",
            ],
        )

        if not data.compatibility.is_compatible:
            builder.add_card(
                "Evaluation Compatibility Warning",
                data.compatibility.compatibility_warnings,
                bg_color=(1.0, 0.96, 0.92),
            )

        builder.add_section_header("1. Compared Candidates Overview")
        ov_headers = ["Candidate", "Overall Score", "Coverage %", "Review Status", "Config Version"]
        ov_rows = []
        for h in data.candidate_headers:
            sc_val = f"{h['overall_score']:.1f}%" if h["overall_score"] is not None else "N/A"
            ov_rows.append([
                h["candidate_reference"],
                sc_val,
                f"{h['evidence_coverage']:.1f}%",
                h["review_status"],
                h["config_version"],
            ])
        builder.add_table(ov_headers, ov_rows, [120.0, 95.0, 95.0, 105.0, 100.0])

        builder.add_section_header("2. Aligned Criteria Comparison")
        comp_headers = ["Criterion (Weight)"] + [h["candidate_reference"] for h in data.candidate_headers[:4]]
        col_count = len(comp_headers)
        first_w = 175.0
        rem_w = (builder.printable_width - first_w) / (col_count - 1)
        col_w = [first_w] + [rem_w] * (col_count - 1)

        crit_rows = []
        for row in data.aligned_criteria_rows:
            label = f"{row.criterion_name} ({int(row.configured_weight * 100)}%)"
            if row.has_meaningful_difference:
                label += " *"
            r_cells = [label]
            for h in data.candidate_headers[:4]:
                eval_item = row.candidate_evaluations.get(h["candidate_id"], {})
                st = eval_item.get("match_status", "N/A")
                pts = eval_item.get("normalized_points", 0.0)
                r_cells.append(f"{st} ({pts:.1f}p)")
            crit_rows.append(r_cells)

        builder.add_table(comp_headers, crit_rows, col_w)

        if data.key_differentiators:
            builder.add_section_header("3. Key Capability Differentiators")
            for diff in data.key_differentiators:
                builder.add_bullet("Differentiator", diff)

        return builder.finalize()

    @staticmethod
    def format_shortlist_report(data: ShortlistReportData) -> bytes:
        builder = PDFBuilder()

        builder.add_title_block(
            title=f"Recruiter Shortlist & Review Queue: {data.session_name}",
            subtitle=f"Target Requisition: {data.job_title} | Total Candidates: {data.total_shortlisted_count}",
            meta_badges=[
                f"Shortlisted: {data.status_counts.get('SHORTLISTED', 0)}",
                f"In Review: {data.status_counts.get('IN_REVIEW', 0)}",
                f"Needs Review: {data.status_counts.get('NEEDS_REVIEW', 0)}",
            ],
        )

        builder.add_section_header("1. Review Queue Summary")
        builder.add_metric_row([
            ("Shortlisted", str(data.status_counts.get("SHORTLISTED", 0))),
            ("In Review", str(data.status_counts.get("IN_REVIEW", 0))),
            ("Needs Review", str(data.status_counts.get("NEEDS_REVIEW", 0))),
            ("On Hold", str(data.status_counts.get("ON_HOLD", 0))),
        ])

        builder.add_section_header("2. Candidate Review Details & Notes")
        sl_headers = ["Candidate Ref", "Filename", "Score", "Coverage", "Review Status", "Reviewer Notes"]
        sl_rows = []
        for item in data.items:
            sc_str = f"{item.overall_score:.1f}%" if item.overall_score is not None else "N/A"
            note_str = item.reviewer_notes if item.reviewer_notes else "-"
            sl_rows.append([
                item.candidate_reference,
                item.original_filename[:20],
                sc_str,
                f"{item.evidence_coverage:.1f}%",
                item.review_status.value if hasattr(item.review_status, "value") else str(item.review_status),
                note_str[:25],
            ])

        col_w = [90.0, 110.0, 65.0, 65.0, 85.0, 100.0]
        builder.add_table(sl_headers, sl_rows, col_w)

        return builder.finalize()
