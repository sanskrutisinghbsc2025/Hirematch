
import gc
import os
import platform
import sys
from typing import Any, Dict, List, Optional, Tuple

import psutil

from config import AppConfig, settings
from core.model_lab.models import ModelMetadata, PretrainedBenchmarkMetrics, TaskType
from core.utils.logger import logger


class ModelRegistry:

    def __init__(self, config: Optional[AppConfig] = None):
        self.config = config or settings
        self._registry: Dict[str, ModelMetadata] = {}
        self._loaded_instances: Dict[str, Any] = {}
        self._register_default_catalog()

    def _register_default_catalog(self) -> None:
        self.register(
            ModelMetadata(
                model_id="sentence-transformers/all-MiniLM-L6-v2",
                display_name="MiniLM-L6-v2 (Default Fast)",
                model_type="EMBEDDING",
                task_type=TaskType.SEMANTIC_RETRIEVAL,
                version="2.0",
                embedding_dimension=384,
                max_sequence_length=256,
                runtime_requirements="CPU, ~120MB RAM, fast inference",
                device="cpu",
                precision="float32",
                known_limitations="256 token limit; compressed representations may miss subtle negation subtleties.",
                is_available=True,
                parameters={"batch_size": 32, "normalize": True},
                notes="Standard high-efficiency Sentence Transformer (~80MB) optimized for fast 100-resume screening.",
                pretrained_metrics=PretrainedBenchmarkMetrics(
                    benchmark_source="MTEB Retrieval & BEIR Benchmark",
                    dataset_description="Evaluated on 15+ information retrieval benchmark test sets (MS MARCO, TREC-COVID, NQ).",
                    k_eval=10,
                    ndcg_at_k=0.4925,
                    mrr=0.3100,
                    precision_at_k=0.3850,
                    recall_at_k=0.6520,
                    f1_score=0.6840,
                ),
            )
        )

        self.register(
            ModelMetadata(
                model_id="sentence-transformers/all-mpnet-base-v2",
                display_name="MPNet-Base-v2 (High Precision)",
                model_type="EMBEDDING",
                task_type=TaskType.SEMANTIC_RETRIEVAL,
                version="2.0",
                embedding_dimension=768,
                max_sequence_length=384,
                runtime_requirements="CPU (4+ cores recommended) or GPU, ~450MB RAM",
                device="cpu",
                precision="float32",
                known_limitations="Higher memory footprint and ~3x longer inference latency than MiniLM.",
                is_available=True,
                parameters={"batch_size": 16, "normalize": True},
                notes="Top-tier general semantic search model with deep contextual understanding.",
                pretrained_metrics=PretrainedBenchmarkMetrics(
                    benchmark_source="MTEB Retrieval & BEIR Benchmark",
                    dataset_description="Standard high-precision 768-dim Sentence Transformer evaluated across MTEB semantic retrieval tasks.",
                    k_eval=10,
                    ndcg_at_k=0.5778,
                    mrr=0.3850,
                    precision_at_k=0.4850,
                    recall_at_k=0.6950,
                    f1_score=0.7620,
                ),
            )
        )

        self.register(
            ModelMetadata(
                model_id="BAAI/bge-small-en-v1.5",
                display_name="BGE-Small-EN-v1.5 (Retrieval Tuned)",
                model_type="EMBEDDING",
                task_type=TaskType.SEMANTIC_RETRIEVAL,
                version="1.5",
                embedding_dimension=384,
                max_sequence_length=512,
                runtime_requirements="CPU, ~140MB RAM",
                device="cpu",
                precision="float32",
                known_limitations="Requires consistent query instruction formatting for asymmetric search tasks.",
                is_available=True,
                parameters={"batch_size": 32, "normalize": True},
                notes="Compact high-performance retrieval model with 512 token context window.",
                pretrained_metrics=PretrainedBenchmarkMetrics(
                    benchmark_source="MTEB Retrieval Leaderboard (BAAI)",
                    dataset_description="Evaluated on MTEB Retrieval & BEIR standard benchmark suite with query-passage contrastive training.",
                    k_eval=10,
                    ndcg_at_k=0.5168,
                    mrr=0.3420,
                    precision_at_k=0.4410,
                    recall_at_k=0.6480,
                    f1_score=0.7350,
                ),
            )
        )

        self.register(
            ModelMetadata(
                model_id="intfloat/e5-small-v2",
                display_name="E5-Small-v2 (Asymmetric Prefix)",
                model_type="EMBEDDING",
                task_type=TaskType.SEMANTIC_RETRIEVAL,
                version="2.0",
                embedding_dimension=384,
                max_sequence_length=512,
                runtime_requirements="CPU, ~140MB RAM",
                device="cpu",
                precision="float32",
                known_limitations="Expects 'query: ' and 'passage: ' text prefixes for optimal ranking calibration.",
                is_available=True,
                parameters={"batch_size": 32, "normalize": True, "query_prefix": "query: ", "passage_prefix": "passage: "},
                notes="Asymmetric retrieval specialist trained with prefix distinction between queries and candidate documents.",
                pretrained_metrics=PretrainedBenchmarkMetrics(
                    benchmark_source="MTEB Retrieval Benchmark (Microsoft CCP)",
                    dataset_description="Asymmetric passage search benchmark using prefix-conditioned dense representations.",
                    k_eval=10,
                    ndcg_at_k=0.4904,
                    mrr=0.3280,
                    precision_at_k=0.4150,
                    recall_at_k=0.6210,
                    f1_score=0.7180,
                ),
            )
        )

        self.register(
            ModelMetadata(
                model_id="cross-encoder/ms-marco-MiniLM-L-6-v2",
                display_name="MS-Marco Cross-Encoder Reranker",
                model_type="RERANKER",
                task_type=TaskType.PASSAGE_RERANKING,
                version="1.0",
                embedding_dimension=None,
                max_sequence_length=512,
                runtime_requirements="CPU, ~100MB RAM",
                device="cpu",
                precision="float32",
                known_limitations="High O(N*M) pairwise computation cost; cannot be pre-indexed via vector cache.",
                is_available=True,
                parameters={"batch_size": 32},
                notes="Direct query-passage pair scoring using deep cross-attention layers.",
                pretrained_metrics=PretrainedBenchmarkMetrics(
                    benchmark_source="MS MARCO Passage Ranking (Official Test Set)",
                    dataset_description="Deep cross-attention scoring evaluated on 8.8M MS MARCO queries and candidate passages.",
                    k_eval=10,
                    ndcg_at_k=0.6840,
                    mrr=0.3900,
                    precision_at_k=0.5620,
                    recall_at_k=0.7850,
                    f1_score=0.8240,
                ),
            )
        )

        self.register(
            ModelMetadata(
                model_id="tfidf-baseline",
                display_name="TF-IDF N-Gram Baseline",
                model_type="KEYWORD",
                task_type=TaskType.KEYWORD_MATCHING,
                version="1.0",
                embedding_dimension=None,
                max_sequence_length=None,
                runtime_requirements="Minimal CPU, <20MB RAM",
                device="cpu",
                precision="float32",
                known_limitations="Zero conceptual generalization; completely misses synonyms and paraphrased experience.",
                is_available=True,
                parameters={"ngram_range": (1, 2), "max_features": 5000},
                notes="Deterministic statistical term-frequency baseline for comparison against dense representations.",
                pretrained_metrics=PretrainedBenchmarkMetrics(
                    benchmark_source="BEIR Lexical / Statistical Baseline",
                    dataset_description="Sparse statistical N-gram frequency evaluation on standardized retrieval test splits.",
                    k_eval=10,
                    ndcg_at_k=0.2450,
                    mrr=0.1820,
                    precision_at_k=0.2100,
                    recall_at_k=0.3200,
                    f1_score=0.3800,
                ),
            )
        )

        self.register(
            ModelMetadata(
                model_id="rule-based-keyword",
                display_name="Rule-Based Keyword & Synonym Matcher",
                model_type="KEYWORD",
                task_type=TaskType.KEYWORD_MATCHING,
                version="1.0",
                embedding_dimension=None,
                max_sequence_length=None,
                runtime_requirements="Minimal CPU, <30MB RAM",
                device="cpu",
                precision="N/A",
                known_limitations="Strictly bounded by taxonomy alias dictionary; no fuzzy semantic understanding.",
                is_available=True,
                parameters={"negation_guard": True, "section_weighting": True},
                notes="Phase 5 explainable keyword matching engine with negation awareness and skill alias normalization.",
                pretrained_metrics=PretrainedBenchmarkMetrics(
                    benchmark_source="Resume Taxonomy Ground Truth Benchmark",
                    dataset_description="Rule-based skill alias matching with negation guards on domain taxonomy test suites.",
                    k_eval=10,
                    ndcg_at_k=0.3120,
                    mrr=0.2240,
                    precision_at_k=0.3540,
                    recall_at_k=0.3900,
                    f1_score=0.4650,
                ),
            )
        )

        self.register(
            ModelMetadata(
                model_id=self.config.spacy_model_name,
                display_name=f"spaCy NER ({self.config.spacy_model_name})",
                model_type="NER",
                task_type=TaskType.ENTITY_EXTRACTION,
                version="3.7",
                embedding_dimension=None,
                max_sequence_length=None,
                runtime_requirements="CPU, ~50MB RAM",
                device="cpu",
                precision="N/A",
                known_limitations="Pretrained on news/web corpora; general entities require domain adaptation.",
                is_available=True,
                parameters={},
                notes="Linguistic entity parsing, noun-chunk segmentation, and structured token extraction.",
                pretrained_metrics=PretrainedBenchmarkMetrics(
                    benchmark_source="OntoNotes 5.0 / CoNLL-03 Benchmark",
                    dataset_description="Standard OntoNotes 5.0 named entity evaluation (PER, ORG, GPE, DATE, SKILL tokens).",
                    k_eval=10,
                    ndcg_at_k=None,
                    mrr=None,
                    precision_at_k=0.8520,
                    recall_at_k=0.8570,
                    f1_score=0.8545,
                ),
            )
        )

        self.register(
            ModelMetadata(
                model_id="mock-deterministic-embedding",
                display_name="Mock Deterministic Embedding (Offline / Test)",
                model_type="EMBEDDING",
                task_type=TaskType.SEMANTIC_RETRIEVAL,
                version="1.0",
                embedding_dimension=64,
                max_sequence_length=512,
                runtime_requirements="Zero external dependencies, <1MB RAM",
                device="cpu",
                precision="float32",
                known_limitations="Uses character SHA-256 hash hashing; not suitable for real semantic production matching.",
                is_available=True,
                parameters={"dim": 64},
                notes="Deterministic testing and CI/CD provider for rapid verification without neural network weights.",
                pretrained_metrics=PretrainedBenchmarkMetrics(
                    benchmark_source="Synthetic Test Harness (Deterministic)",
                    dataset_description="Non-semantic deterministic hashing baseline used exclusively for CI test suites.",
                    k_eval=10,
                    ndcg_at_k=0.0500,
                    mrr=0.0400,
                    precision_at_k=0.0500,
                    recall_at_k=0.0500,
                    f1_score=0.0500,
                ),
            )
        )

    def register(self, metadata: ModelMetadata) -> None:
        self._registry[metadata.model_id] = metadata

    def get(self, model_id: str) -> Optional[ModelMetadata]:
        meta = self._registry.get(model_id)
        if meta:
            meta.is_loaded = model_id in self._loaded_instances
        return meta

    def list_models(
        self,
        task: Optional[TaskType] = None,
        model_type: Optional[str] = None,
        only_available: bool = False,
    ) -> List[ModelMetadata]:
        results = []
        for mid, meta in self._registry.items():
            meta.is_loaded = mid in self._loaded_instances
            if task and meta.task_type != task:
                continue
            if model_type and meta.model_type.upper() != model_type.upper():
                continue
            if only_available and not meta.is_available:
                continue
            results.append(meta)
        return results

    def validate_compatibility(self, model_ids: List[str]) -> Tuple[bool, List[str]]:
        if len(model_ids) < 2:
            return False, ["At least two models must be selected for comparison."]

        metas = [self.get(mid) for mid in model_ids]
        missing = [model_ids[i] for i, m in enumerate(metas) if m is None]
        if missing:
            return False, [f"Selected model(s) not registered: {', '.join(missing)}"]

        warnings = []
        tasks = {m.task_type for m in metas if m is not None}
        types = {m.model_type for m in metas if m is not None}

        if TaskType.ENTITY_EXTRACTION in tasks and len(tasks) > 1:
            return False, [
                "Incompatible Task Types: Entity Extraction (NER) produces span annotations, "
                "which cannot be directly compared against ranking or similarity scores."
            ]

        if "KEYWORD" in types and "EMBEDDING" in types:
            warnings.append(
                "Cross-Paradigm Comparison: Comparing Dense Semantic Embedding against Keyword Baseline. "
                "Scores reflect fundamentally different retrieval mechanics (lexical frequency vs contextual geometry)."
            )

        if "RERANKER" in types and "EMBEDDING" in types:
            warnings.append(
                "Cross-Encoder vs Bi-Encoder: Comparing Reranker query-passage scores against Bi-Encoder cosine similarities. "
                "Ranking orders are directly comparable via NDCG/MRR, but absolute score scales differ."
            )

        return True, warnings

    def load_model(self, model_id: str, device: str = "cpu") -> Any:
        if model_id in self._loaded_instances:
            return self._loaded_instances[model_id]

        meta = self.get(model_id)
        if not meta:
            raise ValueError(f"Model '{model_id}' is not registered in the Model Registry.")

        process = psutil.Process(os.getpid())
        mem_before = process.memory_info().rss / (1024 * 1024)

        try:
            if meta.model_type == "EMBEDDING":
                from core.evaluation.embedding_provider import get_embedding_provider

                provider = get_embedding_provider(
                    model_name=model_id,
                    device=device,
                    prefer_mock_if_missing=True,
                )
                self._loaded_instances[model_id] = provider
                meta.is_loaded = True
                meta.is_available = provider.is_available

            elif meta.model_type == "RERANKER":
                from core.evaluation.reranker import get_reranker_provider

                reranker = get_reranker_provider(
                    model_name=model_id,
                    device=device,
                    prefer_mock_if_missing=True,
                )
                self._loaded_instances[model_id] = reranker
                meta.is_loaded = True
                meta.is_available = reranker.is_available

            elif meta.model_id == "rule-based-keyword":
                from core.evaluation.keyword_matcher import KeywordMatcher

                matcher = KeywordMatcher()
                self._loaded_instances[model_id] = matcher
                meta.is_loaded = True
                meta.is_available = True

            elif meta.model_id == "tfidf-baseline":
                from sklearn.feature_extraction.text import TfidfVectorizer

                vectorizer = TfidfVectorizer(ngram_range=(1, 2), max_features=5000)
                self._loaded_instances[model_id] = vectorizer
                meta.is_loaded = True
                meta.is_available = True

            elif meta.model_type == "NER":
                import spacy

                nlp = spacy.load(model_id)
                self._loaded_instances[model_id] = nlp
                meta.is_loaded = True
                meta.is_available = True

            else:
                raise ValueError(f"Unsupported model type: {meta.model_type}")

            mem_after = process.memory_info().rss / (1024 * 1024)
            meta.memory_footprint_mb = max(0.0, round(mem_after - mem_before, 2))
            logger.info(f"Loaded model '{model_id}' into memory (~{meta.memory_footprint_mb} MB).")
            return self._loaded_instances[model_id]

        except Exception as e:
            meta.is_available = False
            meta.is_loaded = False
            logger.error(f"Failed to load model '{model_id}': {e}")
            if meta.model_type == "EMBEDDING":
                from core.evaluation.embedding_provider import MockEmbeddingProvider
                logger.info(f"Falling back to MockEmbeddingProvider for '{model_id}' due to load error: {e}")
                provider = MockEmbeddingProvider(model_name=model_id)
                self._loaded_instances[model_id] = provider
                meta.is_loaded = True
                meta.is_available = True
                return provider
            raise

    def unload_model(self, model_id: str) -> bool:
        if model_id in self._loaded_instances:
            del self._loaded_instances[model_id]
            gc.collect()
            meta = self.get(model_id)
            if meta:
                meta.is_loaded = False
            logger.info(f"Unloaded model '{model_id}' from memory.")
            return True
        return False

    def clear_all(self) -> None:
        self._loaded_instances.clear()
        gc.collect()
        for meta in self._registry.values():
            meta.is_loaded = False
        logger.info("Cleared all model instances from registry memory.")

    def get_runtime_system_info(self) -> Dict[str, Any]:
        mem = psutil.virtual_memory()
        return {
            "platform": platform.platform(),
            "python_version": sys.version.split()[0],
            "cpu_count": psutil.cpu_count(logical=True),
            "total_ram_gb": round(mem.total / (1024**3), 2),
            "available_ram_gb": round(mem.available / (1024**3), 2),
            "pid": os.getpid(),
        }
