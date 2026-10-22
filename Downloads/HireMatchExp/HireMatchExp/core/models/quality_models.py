
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid


class QualityLabel(str, Enum):
    GOOD = "Good Quality"
    MODERATE = "Moderate Quality"
    POOR = "Poor Quality"

    @classmethod
    def from_score(cls, score: float, good_threshold: float = 75.0, moderate_threshold: float = 50.0) -> "QualityLabel":
        if score >= good_threshold:
            return cls.GOOD
        if score >= moderate_threshold:
            return cls.MODERATE
        return cls.POOR


class IssueSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class SectionPresence(str, Enum):
    PRESENT = "PRESENT"
    OPTIONAL_MISSING = "OPTIONAL_MISSING"
    MISSING_CORE = "MISSING_CORE"


class QualityCriterionKey(str, Enum):
    COMPLETENESS = "completeness"
    STRUCTURE_ORGANIZATION = "structure_organization"
    READABILITY = "readability"
    FORMATTING_CONSISTENCY = "formatting_consistency"
    EXPERIENCE_CLARITY = "experience_clarity"
    SKILLS_CLARITY = "skills_clarity"
    ACHIEVEMENT_SPECIFICITY = "achievement_specificity"
    DATE_CONSISTENCY = "date_consistency"
    CONTACT_COMPLETENESS = "contact_completeness"
    EXTRACTION_QUALITY = "extraction_quality"


@dataclass
class QualityCriterionResult:
    criterion_key: str
    criterion_name: str
    score: float
    weight: float
    weighted_score: float
    status: str
    observations: str
    evidence_snippets: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "criterion_key": self.criterion_key,
            "criterion_name": self.criterion_name,
            "score": round(self.score, 1),
            "weight": self.weight,
            "weighted_score": round(self.weighted_score, 1),
            "status": self.status,
            "observations": self.observations,
            "evidence_snippets": self.evidence_snippets,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QualityCriterionResult":
        return cls(
            criterion_key=data["criterion_key"],
            criterion_name=data["criterion_name"],
            score=float(data["score"]),
            weight=float(data["weight"]),
            weighted_score=float(data.get("weighted_score", data["score"] * data["weight"])),
            status=data.get("status", "ACCEPTABLE"),
            observations=data.get("observations", ""),
            evidence_snippets=data.get("evidence_snippets", []),
        )


@dataclass
class QualityStrength:
    title: str
    description: str
    criterion_key: str
    evidence_quote: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "description": self.description,
            "criterion_key": self.criterion_key,
            "evidence_quote": self.evidence_quote,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QualityStrength":
        return cls(
            title=data["title"],
            description=data["description"],
            criterion_key=data.get("criterion_key", "general"),
            evidence_quote=data.get("evidence_quote"),
        )


@dataclass
class QualityImprovement:
    title: str
    recommendation: str
    criterion_key: str
    rationale: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "recommendation": self.recommendation,
            "criterion_key": self.criterion_key,
            "rationale": self.rationale,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QualityImprovement":
        return cls(
            title=data["title"],
            recommendation=data["recommendation"],
            criterion_key=data.get("criterion_key", "general"),
            rationale=data.get("rationale", ""),
        )


@dataclass
class QualityIssue:
    issue_type: str
    severity: IssueSeverity
    description: str
    context: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "issue_type": self.issue_type,
            "severity": self.severity.value,
            "description": self.description,
            "context": self.context,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QualityIssue":
        sev = data.get("severity", IssueSeverity.LOW.value)
        return cls(
            issue_type=data["issue_type"],
            severity=IssueSeverity(sev) if sev in IssueSeverity._value2member_map_ else IssueSeverity.LOW,
            description=data["description"],
            context=data.get("context"),
        )


@dataclass
class ReadabilityMetrics:
    word_count: int = 0
    sentence_count: int = 0
    avg_words_per_sentence: float = 0.0
    bullet_count: int = 0
    bullet_ratio: float = 0.0
    action_verb_count: int = 0
    action_verb_ratio: float = 0.0
    quantified_metric_count: int = 0
    readability_level: str = "Clear and Concise"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "word_count": self.word_count,
            "sentence_count": self.sentence_count,
            "avg_words_per_sentence": round(self.avg_words_per_sentence, 1),
            "bullet_count": self.bullet_count,
            "bullet_ratio": round(self.bullet_ratio, 2),
            "action_verb_count": self.action_verb_count,
            "action_verb_ratio": round(self.action_verb_ratio, 2),
            "quantified_metric_count": self.quantified_metric_count,
            "readability_level": self.readability_level,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReadabilityMetrics":
        return cls(
            word_count=int(data.get("word_count", 0)),
            sentence_count=int(data.get("sentence_count", 0)),
            avg_words_per_sentence=float(data.get("avg_words_per_sentence", 0.0)),
            bullet_count=int(data.get("bullet_count", 0)),
            bullet_ratio=float(data.get("bullet_ratio", 0.0)),
            action_verb_count=int(data.get("action_verb_count", 0)),
            action_verb_ratio=float(data.get("action_verb_ratio", 0.0)),
            quantified_metric_count=int(data.get("quantified_metric_count", 0)),
            readability_level=data.get("readability_level", "Clear and Concise"),
        )


@dataclass
class ExtractionDiagnostics:
    char_count: int = 0
    line_count: int = 0
    page_count: int = 1
    ocr_needed: bool = False
    is_empty: bool = False
    parse_confidence: float = 1.0
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "char_count": self.char_count,
            "line_count": self.line_count,
            "page_count": self.page_count,
            "ocr_needed": self.ocr_needed,
            "is_empty": self.is_empty,
            "parse_confidence": round(self.parse_confidence, 2),
            "warnings": self.warnings,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExtractionDiagnostics":
        return cls(
            char_count=int(data.get("char_count", 0)),
            line_count=int(data.get("line_count", 0)),
            page_count=int(data.get("page_count", 1)),
            ocr_needed=bool(data.get("ocr_needed", False)),
            is_empty=bool(data.get("is_empty", False)),
            parse_confidence=float(data.get("parse_confidence", 1.0)),
            warnings=data.get("warnings", []),
        )


@dataclass
class ResumeQualityAssessment:
    candidate_id: str
    overall_score: float
    quality_label: QualityLabel
    criterion_results: List[QualityCriterionResult]
    strong_areas: List[QualityStrength] = field(default_factory=list)
    areas_for_improvement: List[QualityImprovement] = field(default_factory=list)
    detected_issues: List[QualityIssue] = field(default_factory=list)
    section_completeness: Dict[str, Any] = field(default_factory=dict)
    readability_metrics: ReadabilityMetrics = field(default_factory=ReadabilityMetrics)
    extraction_diagnostics: ExtractionDiagnostics = field(default_factory=ExtractionDiagnostics)
    executive_summary: str = ""
    session_id: Optional[str] = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    assessed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "candidate_id": self.candidate_id,
            "session_id": self.session_id,
            "overall_score": round(self.overall_score, 1),
            "quality_label": self.quality_label.value,
            "criterion_results": [c.to_dict() for c in self.criterion_results],
            "strong_areas": [s.to_dict() for s in self.strong_areas],
            "areas_for_improvement": [i.to_dict() for i in self.areas_for_improvement],
            "detected_issues": [issue.to_dict() for issue in self.detected_issues],
            "section_completeness": self.section_completeness,
            "readability_metrics": self.readability_metrics.to_dict(),
            "extraction_diagnostics": self.extraction_diagnostics.to_dict(),
            "executive_summary": self.executive_summary,
            "assessed_at": self.assessed_at,
            "responsible_ai_notice": (
                "Resume quality reflects how clearly and consistently the submitted resume "
                "communicates its information. It is separate from the candidate's match score. "
                "Resume quality is not candidate quality."
            ),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ResumeQualityAssessment":
        c_results = [QualityCriterionResult.from_dict(c) for c in data.get("criterion_results", [])]
        strengths = [QualityStrength.from_dict(s) for s in data.get("strong_areas", [])]
        improvements = [QualityImprovement.from_dict(i) for i in data.get("areas_for_improvement", [])]
        issues = [QualityIssue.from_dict(issue) for issue in data.get("detected_issues", [])]
        r_metrics = ReadabilityMetrics.from_dict(data.get("readability_metrics", {}))
        e_diagnostics = ExtractionDiagnostics.from_dict(data.get("extraction_diagnostics", {}))

        q_label_raw = data.get("quality_label", QualityLabel.MODERATE.value)
        q_label = QualityLabel(q_label_raw) if q_label_raw in QualityLabel._value2member_map_ else QualityLabel.MODERATE

        return cls(
            id=data.get("id", str(uuid.uuid4())),
            candidate_id=data["candidate_id"],
            session_id=data.get("session_id"),
            overall_score=float(data["overall_score"]),
            quality_label=q_label,
            criterion_results=c_results,
            strong_areas=strengths,
            areas_for_improvement=improvements,
            detected_issues=issues,
            section_completeness=data.get("section_completeness", {}),
            readability_metrics=r_metrics,
            extraction_diagnostics=e_diagnostics,
            executive_summary=data.get("executive_summary", ""),
            assessed_at=data.get("assessed_at", datetime.now(timezone.utc).isoformat()),
        )
