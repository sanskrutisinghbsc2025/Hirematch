
from typing import Any, Dict, Optional

from config import AppConfig, settings
from core.models.enums import ModelType
from core.models.model_config import ModelConfiguration
from core.utils.errors import ModelLoadError
from core.utils.logger import logger


class ModelManager:

    def __init__(self, config: Optional[AppConfig] = None):
        self.config = config or settings
        self._model_cache: Dict[str, Any] = {}
        self._registry: Dict[str, ModelConfiguration] = {}
        self._register_default_models()

    def _register_default_models(self) -> None:
        self.register_model(
            ModelConfiguration(
                model_name="sentence-transformers/all-MiniLM-L6-v2",
                model_type=ModelType.EMBEDDING,
                version="2.0",
                parameters={"batch_size": 32, "device": "cpu", "embedding_dimension": 384, "max_sequence_length": 256},
                is_enabled=True,
                notes="Default high-efficiency sentence embedding model (~80MB, 384-dim) for fast 100-resume batching.",
            )
        )
        self.register_model(
            ModelConfiguration(
                model_name="sentence-transformers/all-mpnet-base-v2",
                model_type=ModelType.EMBEDDING,
                version="2.0",
                parameters={"batch_size": 16, "device": "cpu", "embedding_dimension": 768, "max_sequence_length": 384},
                is_enabled=True,
                notes="High-precision sentence embedding model (~420MB, 768-dim) for nuanced conceptual matching.",
            )
        )
        self.register_model(
            ModelConfiguration(
                model_name="BAAI/bge-small-en-v1.5",
                model_type=ModelType.EMBEDDING,
                version="1.5",
                parameters={"batch_size": 32, "device": "cpu", "embedding_dimension": 384, "max_sequence_length": 512},
                is_enabled=True,
                notes="Compact high-performance retrieval model (~130MB, 384-dim) optimized for criteria queries.",
            )
        )
        self.register_model(
            ModelConfiguration(
                model_name="cross-encoder/ms-marco-MiniLM-L-6-v2",
                model_type=ModelType.RERANKER,
                version="1.0",
                parameters={"batch_size": 32, "device": "cpu"},
                is_enabled=True,
                notes="Cross-encoder neural reranker (~80MB) for scoring passage-requirement pairs directly.",
            )
        )
        self.register_model(
            ModelConfiguration(
                model_name=self.config.spacy_model_name,
                model_type=ModelType.NER,
                version="3.7",
                parameters={},
                is_enabled=True,
                notes="Lightweight linguistic processing, entity detection, and rule-based extraction.",
            )
        )
        self.register_model(
            ModelConfiguration(
                model_name="tfidf-baseline",
                model_type=ModelType.KEYWORD,
                version="1.0",
                parameters={"ngram_range": (1, 2), "max_features": 5000},
                is_enabled=True,
                notes="Transparent keyword and n-gram term frequency baseline.",
            )
        )

    def register_model(self, model_config: ModelConfiguration) -> None:
        self._registry[model_config.model_name] = model_config

    def get_model_config(self, model_name: str) -> Optional[ModelConfiguration]:
        return self._registry.get(model_name)

    def list_models(self) -> Dict[str, ModelConfiguration]:
        return dict(self._registry)

    def is_cached(self, model_name: str) -> bool:
        return model_name in self._model_cache

    def get_embedding_provider(
        self,
        model_name: Optional[str] = None,
        device: str = "cpu",
        prefer_mock_if_missing: bool = True,
    ):
        from core.evaluation.embedding_provider import get_embedding_provider

        name = model_name or self.config.semantic_model_name
        cache_key = f"emb_provider:{name}:{device}"
        if cache_key not in self._model_cache:
            provider = get_embedding_provider(
                model_name=name,
                device=device,
                prefer_mock_if_missing=prefer_mock_if_missing,
            )
            self._model_cache[cache_key] = provider
            if name in self._registry:
                self._registry[name].status = provider.status
        return self._model_cache[cache_key]

    def clear_cache(self) -> None:
        self._model_cache.clear()
        logger.info("Cleared model manager memory cache.")

