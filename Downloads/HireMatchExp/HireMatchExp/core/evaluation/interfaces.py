
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

from core.models.candidate import Candidate
from core.models.evaluation import CandidateScore, EvaluationCriterion, EvaluationEvidence
from core.models.job import Job
from core.models.skills import ExtractedSkill


class IQualityEvaluator(ABC):

    @abstractmethod
    def evaluate_quality(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> Tuple[float, List[str]]:
        pass


class ISkillExtractor(ABC):

    @abstractmethod
    def extract_skills(self, text: str) -> List[ExtractedSkill]:
        pass


class ISemanticMatcher(ABC):

    @abstractmethod
    def compute_similarity(self, query: str, passages: List[str]) -> List[float]:
        pass


class ICandidateEvaluator(ABC):

    @abstractmethod
    def evaluate(
        self,
        candidate: Candidate,
        job: Job,
        criteria: List[EvaluationCriterion],
    ) -> List[EvaluationEvidence]:
        pass


class IScoringService(ABC):

    @abstractmethod
    def calculate_score(
        self,
        candidate: Candidate,
        criteria: List[EvaluationCriterion],
        evidence_list: List[EvaluationEvidence],
    ) -> CandidateScore:
        pass
