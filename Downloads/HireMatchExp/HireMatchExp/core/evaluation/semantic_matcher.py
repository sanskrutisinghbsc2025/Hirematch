
from typing import List, Optional, Tuple
import numpy as np

from core.evaluation.embedding_provider import IEmbeddingProvider
from core.evaluation.interfaces import ISemanticMatcher
from core.evaluation.text_chunker import DocumentChunk
from core.models.enums import SemanticSimilarityTier
from core.models.evaluation import SemanticMatchResult
from core.utils.logger import logger


class SemanticMatcher(ISemanticMatcher):

    STRONG_THRESHOLD = 0.70
    POSSIBLE_THRESHOLD = 0.50
    WEAK_THRESHOLD = 0.35

    def __init__(self, embedding_provider: IEmbeddingProvider):
        self.provider = embedding_provider
        self._query_cache: Dict[str, np.ndarray] = {}

    @property
    def model_name(self) -> str:
        return getattr(self.provider, "model_name", "Unknown")

    def _get_query_vector(self, query: str) -> np.ndarray:
        q_norm = query.strip()
        if q_norm not in self._query_cache:
            self._query_cache[q_norm] = self.provider.encode_queries([q_norm], normalize=True)
        return self._query_cache[q_norm]

    @classmethod
    def classify_tier(cls, score: float) -> SemanticSimilarityTier:
        if score >= cls.STRONG_THRESHOLD:
            return SemanticSimilarityTier.STRONG
        elif score >= cls.POSSIBLE_THRESHOLD:
            return SemanticSimilarityTier.POSSIBLE
        elif score >= cls.WEAK_THRESHOLD:
            return SemanticSimilarityTier.WEAK
        else:
            return SemanticSimilarityTier.INSUFFICIENT

    def compute_similarity(self, query: str, passages: List[str]) -> List[float]:
        if not passages:
            return []
        if not query.strip():
            return [0.0] * len(passages)

        q_vec = self._get_query_vector(query)
        p_vecs = self.provider.encode_passages(passages, normalize=True)

        sims = np.dot(p_vecs, q_vec.T).squeeze(axis=1)
        clipped = np.clip(sims, 0.0, 1.0)
        return [float(s) for s in clipped]

    def match_criterion(
        self,
        query: str,
        chunks: List[DocumentChunk],
        passage_embeddings: Optional[np.ndarray] = None,
        top_k: int = 3,
        threshold: float = 0.35,
    ) -> List[SemanticMatchResult]:
        if not chunks or not query.strip():
            return []

        q_vec = self._get_query_vector(query)

        if passage_embeddings is None:
            texts = [c.text for c in chunks]
            passage_embeddings = self.provider.encode_passages(texts, normalize=True)

        sims = np.dot(passage_embeddings, q_vec.T).squeeze(axis=1)
        sims = np.clip(sims, 0.0, 1.0)

        results: List[SemanticMatchResult] = []
        for idx, (chunk, score) in enumerate(zip(chunks, sims)):
            score_val = float(score)
            tier = self.classify_tier(score_val)
            results.append(
                SemanticMatchResult(
                    passage_text=chunk.text,
                    source_section=chunk.source_section,
                    similarity_score=round(score_val, 4),
                    similarity_tier=tier,
                    chunk_index=chunk.chunk_index,
                    model_id=self.provider.model_name,
                    char_start=chunk.char_start,
                    char_end=chunk.char_end,
                )
            )

        results.sort(key=lambda x: x.similarity_score, reverse=True)

        top_results = results[:top_k]
        return top_results
