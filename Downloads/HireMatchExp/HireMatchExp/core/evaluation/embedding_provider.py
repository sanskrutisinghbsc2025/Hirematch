
from abc import ABC, abstractmethod
import hashlib
import math
import re
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from core.models.enums import ModelStatus
from core.storage.embedding_cache import SQLiteEmbeddingCache
from core.utils.logger import logger


class IEmbeddingProvider(ABC):

    @property
    @abstractmethod
    def model_name(self) -> str:
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        pass

    @property
    @abstractmethod
    def device(self) -> str:
        pass

    @property
    @abstractmethod
    def status(self) -> ModelStatus:
        pass

    @property
    def is_available(self) -> bool:
        return self.status == ModelStatus.READY

    @abstractmethod
    def encode(self, texts: List[str], batch_size: int = 32, normalize: bool = True) -> np.ndarray:
        pass

    def encode_queries(self, queries: List[str], batch_size: int = 32, normalize: bool = True) -> np.ndarray:
        return self.encode(queries, batch_size=batch_size, normalize=normalize)

    def encode_passages(self, passages: List[str], batch_size: int = 32, normalize: bool = True) -> np.ndarray:
        return self.encode(passages, batch_size=batch_size, normalize=normalize)


class MockEmbeddingProvider(IEmbeddingProvider):

    _GLOBAL_TOKEN_CACHE: Dict[Tuple[str, int], np.ndarray] = {}
    _GLOBAL_TEXT_CACHE: Dict[Tuple[str, int, bool], np.ndarray] = {}

    def __init__(self, model_name: str = "mock-MiniLM-L6-v2", dimension: int = 384):
        self._model_name = model_name
        self._dimension = dimension
        self._device = "cpu"
        self._status = ModelStatus.READY

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def device(self) -> str:
        return self._device

    @property
    def status(self) -> ModelStatus:
        return self._status

    def _hash_token(self, token: str) -> np.ndarray:
        cache_key = (token, self._dimension)
        cached = MockEmbeddingProvider._GLOBAL_TOKEN_CACHE.get(cache_key)
        if cached is not None:
            return cached
        h = int(hashlib.md5(token.encode("utf-8")).hexdigest()[:8], 16)
        rng = np.random.RandomState(h)
        vec = rng.randn(self._dimension).astype(np.float32)
        MockEmbeddingProvider._GLOBAL_TOKEN_CACHE[cache_key] = vec
        return vec

    def _encode_single(self, text: str, normalize: bool = True) -> np.ndarray:
        clean = text.lower().strip()
        text_cache_key = (clean, self._dimension, normalize)
        cached = MockEmbeddingProvider._GLOBAL_TEXT_CACHE.get(text_cache_key)
        if cached is not None:
            return cached.copy()

        if not clean:
            vec = np.zeros(self._dimension, dtype=np.float32)
            if normalize:
                vec[0] = 1.0
            MockEmbeddingProvider._GLOBAL_TEXT_CACHE[text_cache_key] = vec
            return vec.copy()

        words = re.findall(r"[a-z0-9+#.-]+", clean)
        if not words:
            words = [clean]

        vec = np.zeros(self._dimension, dtype=np.float32)
        for w in words:
            token_vec = self._hash_token(w)
            vec += token_vec

        for i in range(len(words) - 1):
            bigram = f"{words[i]}_{words[i+1]}"
            vec += 0.5 * self._hash_token(bigram)

        if normalize:
            norm = np.linalg.norm(vec)
            if norm > 1e-12:
                vec = vec / norm
            else:
                vec[0] = 1.0
        result = vec.astype(np.float32)
        MockEmbeddingProvider._GLOBAL_TEXT_CACHE[text_cache_key] = result
        return result.copy()

    def encode(self, texts: List[str], batch_size: int = 32, normalize: bool = True) -> np.ndarray:
        if not texts:
            return np.empty((0, self._dimension), dtype=np.float32)
        results = [self._encode_single(t, normalize=normalize) for t in texts]
        return np.vstack(results).astype(np.float32)


class SentenceTransformerProvider(IEmbeddingProvider):

    def __init__(
        self,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        device: Optional[str] = None,
        dimension: int = 384,
    ):
        self._model_name = model_name
        self._dimension = dimension
        self._device = device or "cpu"
        self._model = None
        self._status = ModelStatus.REGISTERED
        self._error_message: Optional[str] = None

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def device(self) -> str:
        return self._device

    @property
    def status(self) -> ModelStatus:
        return self._status

    @property
    def error_message(self) -> Optional[str]:
        return self._error_message

    def _load_model(self) -> None:
        self._status = ModelStatus.LOADING
        try:
            from sentence_transformers import SentenceTransformer
            import torch

            if self._device == "cuda" and not torch.cuda.is_available():
                logger.warning("CUDA requested but not available; falling back to CPU.")
                self._device = "cpu"

            logger.info(f"Loading SentenceTransformer '{self._model_name}' on {self._device}...")
            try:
                self._model = SentenceTransformer(self._model_name, device=self._device, local_files_only=True)
            except Exception:
                self._model = SentenceTransformer(self._model_name, device=self._device)
            test_emb = self._model.encode(["test"], normalize_embeddings=True)
            self._dimension = test_emb.shape[1]
            self._status = ModelStatus.READY
            logger.info(f"SentenceTransformer '{self._model_name}' loaded successfully (dim={self._dimension}).")
        except ImportError as e:
            self._status = ModelStatus.UNAVAILABLE
            self._error_message = (
                f"sentence-transformers or PyTorch is not installed in the environment. ({e})"
            )
            logger.warning(self._error_message)
        except Exception as e:
            self._status = ModelStatus.ERROR
            self._error_message = f"Failed to load embedding model '{self._model_name}': {e}"
            logger.error(self._error_message)

    def encode(self, texts: List[str], batch_size: int = 32, normalize: bool = True) -> np.ndarray:
        if self._model is None and self._status not in (ModelStatus.READY, ModelStatus.ERROR, ModelStatus.UNAVAILABLE):
            self._load_model()
        if self._status != ModelStatus.READY or self._model is None:
            raise RuntimeError(
                f"Model '{self._model_name}' is not ready (status={self._status.value}): {self._error_message}"
            )
        if not texts:
            return np.empty((0, self._dimension), dtype=np.float32)

        embeddings = self._model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=False,
            normalize_embeddings=normalize,
            convert_to_numpy=True,
        )
        return embeddings.astype(np.float32)


class CachedEmbeddingProvider(IEmbeddingProvider):

    def __init__(self, provider: IEmbeddingProvider, cache: SQLiteEmbeddingCache):
        self._provider = provider
        self._cache = cache
        self._l1_cache: Dict[Tuple[str, str, bool], np.ndarray] = {}

    @property
    def model_name(self) -> str:
        return self._provider.model_name

    @property
    def dimension(self) -> int:
        return self._provider.dimension

    @property
    def device(self) -> str:
        return self._provider.device

    @property
    def status(self) -> ModelStatus:
        return self._provider.status

    def encode(self, texts: List[str], batch_size: int = 32, normalize: bool = True) -> np.ndarray:
        if not texts:
            return np.empty((0, self.dimension), dtype=np.float32)

        results: List[Optional[np.ndarray]] = [None] * len(texts)
        missing_indices: List[int] = []
        missing_texts: List[str] = []

        # 1. Check L1 in-memory cache
        for idx, t in enumerate(texts):
            key = (self.model_name, t, normalize)
            cached = self._l1_cache.get(key)
            if cached is not None:
                results[idx] = cached
            else:
                missing_indices.append(idx)
                missing_texts.append(t)

        if not missing_texts:
            return np.vstack(results).astype(np.float32)

        # 2. Query SQLite L2 cache for missing
        cached_dict, missing_tuples = self._cache.get_batch(self.model_name, missing_texts)

        still_missing_tuples = []
        for orig_missing_idx, t in enumerate(missing_texts):
            real_idx = missing_indices[orig_missing_idx]
            if orig_missing_idx in cached_dict:
                emb = cached_dict[orig_missing_idx]
                results[real_idx] = emb
                self._l1_cache[(self.model_name, t, normalize)] = emb
            else:
                still_missing_tuples.append((real_idx, orig_missing_idx, t))

        # 3. Call underlying provider for items missing in both caches
        if still_missing_tuples:
            to_encode_texts = [t for _, _, t in still_missing_tuples]
            new_embeddings = self._provider.encode(
                to_encode_texts, batch_size=batch_size, normalize=normalize
            )

            items_to_cache = []
            for (real_idx, _, t), emb in zip(still_missing_tuples, new_embeddings):
                results[real_idx] = emb
                self._l1_cache[(self.model_name, t, normalize)] = emb
                items_to_cache.append((t, emb))
            self._cache.set_batch(self.model_name, items_to_cache)

        return np.vstack(results).astype(np.float32)


def get_embedding_provider(
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
    device: str = "cpu",
    cache: Optional[SQLiteEmbeddingCache] = None,
    prefer_mock_if_missing: bool = True,
) -> IEmbeddingProvider:
    provider: IEmbeddingProvider
    st_provider = SentenceTransformerProvider(model_name=model_name, device=device)
    if st_provider.status == ModelStatus.READY:
        provider = st_provider
    elif prefer_mock_if_missing:
        logger.info(
            f"Pretrained model '{model_name}' unavailable ({st_provider.error_message}). Using MockEmbeddingProvider fallback."
        )
        provider = MockEmbeddingProvider(model_name=model_name)
    else:
        provider = st_provider

    if cache is not None:
        return CachedEmbeddingProvider(provider=provider, cache=cache)
    return provider
