
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple

from core.models.enums import ModelStatus
from core.utils.logger import logger


class IReranker(ABC):

    @property
    @abstractmethod
    def model_name(self) -> str:
        pass

    @property
    @abstractmethod
    def status(self) -> ModelStatus:
        pass

    @property
    def is_available(self) -> bool:
        return self.status == ModelStatus.READY

    @abstractmethod
    def rerank(self, query: str, passages: List[str]) -> List[Tuple[int, float]]:
        pass

    @abstractmethod
    def score_pairs(self, pairs: List[Tuple[str, str]], batch_size: int = 32) -> List[float]:
        pass


class MockReranker(IReranker):

    def __init__(self, model_name: str = "mock-reranker", device: str = "cpu"):
        self._model_name = model_name
        self._device = device
        self._status = ModelStatus.READY

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def status(self) -> ModelStatus:
        return self._status

    def rerank(self, query: str, passages: List[str]) -> List[Tuple[int, float]]:
        if not passages:
            return []
        scores = self.score_pairs([(query, p) for p in passages])
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        return [(idx, float(score)) for idx, score in ranked]

    def score_pairs(self, pairs: List[Tuple[str, str]], batch_size: int = 32) -> List[float]:
        scores = []
        for q, p in pairs:
            q_words = set(q.lower().split())
            p_words = set(p.lower().split())
            if not q_words:
                scores.append(0.5)
                continue
            overlap = len(q_words.intersection(p_words)) / len(q_words)
            scores.append(round(min(1.0, max(0.0, overlap * 1.2)), 4))
        return scores


class CrossEncoderReranker(IReranker):

    def __init__(
        self,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        device: str = "cpu",
        prefer_mock_if_missing: bool = True,
    ):
        self._model_name = model_name
        self._device = device
        self._prefer_mock_if_missing = prefer_mock_if_missing
        self._model = None
        self._status = ModelStatus.REGISTERED
        self._error_message: Optional[str] = None
        self._load_model()

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def status(self) -> ModelStatus:
        return self._status

    @property
    def error_message(self) -> Optional[str]:
        return self._error_message

    def _load_model(self) -> None:
        self._status = ModelStatus.LOADING
        try:
            from sentence_transformers import CrossEncoder

            logger.info(f"Loading CrossEncoder '{self._model_name}' on {self._device}...")
            try:
                self._model = CrossEncoder(self._model_name, device=self._device, local_files_only=True)
                self._status = ModelStatus.READY
                logger.info(f"CrossEncoder '{self._model_name}' loaded from local storage.")
            except Exception:
                if self._prefer_mock_if_missing:
                    self._status = ModelStatus.UNAVAILABLE
                    self._error_message = "Local files not cached and prefer_mock_if_missing is True"
                    logger.info(f"Pretrained CrossEncoder '{self._model_name}' unavailable locally. Using fallback.")
                else:
                    self._model = CrossEncoder(self._model_name, device=self._device)
                    self._status = ModelStatus.READY
                    logger.info(f"CrossEncoder '{self._model_name}' loaded successfully.")
        except ImportError as e:
            self._status = ModelStatus.UNAVAILABLE
            self._error_message = f"sentence-transformers not installed ({e})"
            logger.info(self._error_message)
        except Exception as e:
            self._status = ModelStatus.ERROR
            self._error_message = f"Failed to load CrossEncoder: {e}"
            logger.error(self._error_message)

    def rerank(self, query: str, passages: List[str]) -> List[Tuple[int, float]]:
        if not passages:
            return []
        scores = self.score_pairs([(query, p) for p in passages])
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        return [(idx, float(score)) for idx, score in ranked]

    def score_pairs(self, pairs: List[Tuple[str, str]], batch_size: int = 32) -> List[float]:
        if not pairs:
            return []
        if self._status != ModelStatus.READY or self._model is None:
            mock = MockReranker(model_name=self._model_name, device=self._device)
            return mock.score_pairs(pairs, batch_size=batch_size)

        try:
            raw_scores = self._model.predict(pairs, batch_size=batch_size)
            return [float(s) for s in raw_scores]
        except Exception as e:
            logger.error(f"Error predicting cross-encoder scores for '{self._model_name}': {e}")
            mock = MockReranker(model_name=self._model_name, device=self._device)
            return mock.score_pairs(pairs, batch_size=batch_size)


def get_reranker_provider(
    model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
    device: str = "cpu",
    prefer_mock_if_missing: bool = True,
) -> IReranker:
    reranker = CrossEncoderReranker(
        model_name=model_name, device=device, prefer_mock_if_missing=prefer_mock_if_missing
    )
    if reranker.status == ModelStatus.READY:
        return reranker
    if prefer_mock_if_missing:
        logger.info(
            f"Pretrained reranker '{model_name}' unavailable ({reranker.error_message}). Using MockReranker fallback."
        )
        return MockReranker(model_name=model_name, device=device)
    return reranker
