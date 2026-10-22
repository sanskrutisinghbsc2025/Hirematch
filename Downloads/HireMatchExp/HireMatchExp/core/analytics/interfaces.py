
from abc import ABC, abstractmethod
from typing import Any, Dict, List

from core.models.candidate import Candidate
from core.models.evaluation import CandidateScore
from core.models.session import ScreeningSession


class IReportingService(ABC):

    @abstractmethod
    def generate_session_report(self, session: ScreeningSession, candidates: List[Candidate], scores: List[CandidateScore]) -> Dict[str, Any]:
        pass


class IAnalyticsService(ABC):

    @abstractmethod
    def compute_skill_coverage(self, candidates: List[Candidate], required_skills: List[str]) -> Dict[str, Any]:
        pass


class IModelComparisonService(ABC):

    @abstractmethod
    def evaluate_rankings(self, predicted_rankings: List[str], ground_truth: List[str], k: int = 10) -> Dict[str, float]:
        pass
