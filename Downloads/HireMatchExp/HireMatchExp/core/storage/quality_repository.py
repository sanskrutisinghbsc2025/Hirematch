
import json
from typing import Any, Dict, List, Optional

from core.models.quality_models import (
    ExtractionDiagnostics,
    QualityCriterionResult,
    QualityImprovement,
    QualityIssue,
    QualityLabel,
    QualityStrength,
    ReadabilityMetrics,
    ResumeQualityAssessment,
)
from core.storage.database import Database
from core.utils.logger import logger


class ResumeQualityRepository:

    def __init__(self, db: Database):
        self.db = db

    def save(self, assessment: ResumeQualityAssessment) -> ResumeQualityAssessment:
        query = """
        INSERT INTO resume_quality_assessments (
            id, candidate_id, session_id, overall_score, quality_label,
            criterion_results, strong_areas, areas_for_improvement, detected_issues,
            section_completeness, readability_metrics, extraction_diagnostics,
            executive_summary, assessed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            overall_score = excluded.overall_score,
            quality_label = excluded.quality_label,
            criterion_results = excluded.criterion_results,
            strong_areas = excluded.strong_areas,
            areas_for_improvement = excluded.areas_for_improvement,
            detected_issues = excluded.detected_issues,
            section_completeness = excluded.section_completeness,
            readability_metrics = excluded.readability_metrics,
            extraction_diagnostics = excluded.extraction_diagnostics,
            executive_summary = excluded.executive_summary,
            assessed_at = excluded.assessed_at;
        """
        params = (
            assessment.id,
            assessment.candidate_id,
            assessment.session_id,
            float(assessment.overall_score),
            assessment.quality_label.value,
            json.dumps([c.to_dict() for c in assessment.criterion_results]),
            json.dumps([s.to_dict() for s in assessment.strong_areas]),
            json.dumps([i.to_dict() for i in assessment.areas_for_improvement]),
            json.dumps([issue.to_dict() for issue in assessment.detected_issues]),
            json.dumps(assessment.section_completeness),
            json.dumps(assessment.readability_metrics.to_dict()),
            json.dumps(assessment.extraction_diagnostics.to_dict()),
            assessment.executive_summary,
            assessment.assessed_at,
        )
        self.db.execute_write(query, params)
        return assessment

    def get_by_candidate(self, candidate_id: str) -> Optional[ResumeQualityAssessment]:
        query = """
        SELECT * FROM resume_quality_assessments
        WHERE candidate_id = ?
        ORDER BY assessed_at DESC
        LIMIT 1;
        """
        rows = self.db.execute_query(query, (candidate_id,))
        if not rows:
            return None
        return self._row_to_assessment(rows[0])

    def get_by_session(self, session_id: str) -> List[ResumeQualityAssessment]:
        query = """
        SELECT rqa.* FROM resume_quality_assessments rqa
        JOIN session_candidates sc ON rqa.candidate_id = sc.candidate_id
        WHERE sc.session_id = ?
        ORDER BY rqa.overall_score DESC;
        """
        rows = self.db.execute_query(query, (session_id,))
        return [self._row_to_assessment(r) for r in rows]

    def get_session_map(self, session_id: str) -> Dict[str, ResumeQualityAssessment]:
        assessments = self.get_by_session(session_id)
        res: Dict[str, ResumeQualityAssessment] = {}
        for a in assessments:
            if a.candidate_id not in res:
                res[a.candidate_id] = a
        return res

    def delete_by_candidate(self, candidate_id: str) -> bool:
        query = "DELETE FROM resume_quality_assessments WHERE candidate_id = ?;"
        count = self.db.execute_write(query, (candidate_id,))
        return count > 0

    def _row_to_assessment(self, row: Any) -> ResumeQualityAssessment:
        try:
            criterion_results = [
                QualityCriterionResult.from_dict(c)
                for c in json.loads(row["criterion_results"] or "[]")
            ]
        except Exception:
            criterion_results = []

        try:
            strong_areas = [
                QualityStrength.from_dict(s)
                for s in json.loads(row["strong_areas"] or "[]")
            ]
        except Exception:
            strong_areas = []

        try:
            improvements = [
                QualityImprovement.from_dict(i)
                for i in json.loads(row["areas_for_improvement"] or "[]")
            ]
        except Exception:
            improvements = []

        try:
            issues = [
                QualityIssue.from_dict(iss)
                for iss in json.loads(row["detected_issues"] or "[]")
            ]
        except Exception:
            issues = []

        try:
            sec_completeness = json.loads(row["section_completeness"] or "{}")
        except Exception:
            sec_completeness = {}

        try:
            readability = ReadabilityMetrics.from_dict(
                json.loads(row["readability_metrics"] or "{}")
            )
        except Exception:
            readability = ReadabilityMetrics()

        try:
            extraction = ExtractionDiagnostics.from_dict(
                json.loads(row["extraction_diagnostics"] or "{}")
            )
        except Exception:
            extraction = ExtractionDiagnostics()

        q_label_raw = row["quality_label"]
        q_label = (
            QualityLabel(q_label_raw)
            if q_label_raw in QualityLabel._value2member_map_
            else QualityLabel.MODERATE
        )

        return ResumeQualityAssessment(
            id=row["id"],
            candidate_id=row["candidate_id"],
            session_id=row["session_id"],
            overall_score=float(row["overall_score"]),
            quality_label=q_label,
            criterion_results=criterion_results,
            strong_areas=strong_areas,
            areas_for_improvement=improvements,
            detected_issues=issues,
            section_completeness=sec_completeness,
            readability_metrics=readability,
            extraction_diagnostics=extraction,
            executive_summary=row["executive_summary"] or "",
            assessed_at=row["assessed_at"],
        )
