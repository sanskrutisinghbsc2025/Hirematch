
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid


class TaskType(str, Enum):
    SEMANTIC_RETRIEVAL = "SEMANTIC_RETRIEVAL"
    PASSAGE_RERANKING = "PASSAGE_RERANKING"
    KEYWORD_MATCHING = "KEYWORD_MATCHING"
    ENTITY_EXTRACTION = "ENTITY_EXTRACTION"


class RelevanceGrade(int, Enum):
    HIGHLY_RELEVANT = 2
    RELEVANT = 1
    NOT_RELEVANT = 0
    UNCERTAIN = -1


class BenchmarkStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class MetricCategory(str, Enum):
    REFERENCE_GROUNDED = "REFERENCE_GROUNDED"
    DESCRIPTIVE_STATISTICS = "DESCRIPTIVE_STATISTICS"
    RUNTIME_MEASUREMENT = "RUNTIME_MEASUREMENT"


@dataclass
class PretrainedBenchmarkMetrics:
    benchmark_source: str = "Standard IR Benchmark"
    dataset_description: str = ""
    k_eval: int = 10
    ndcg_at_k: Optional[float] = None
    mrr: Optional[float] = None
    precision_at_k: Optional[float] = None
    recall_at_k: Optional[float] = None
    f1_score: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "benchmark_source": self.benchmark_source,
            "dataset_description": self.dataset_description,
            "k_eval": self.k_eval,
            "ndcg_at_k": self.ndcg_at_k,
            "mrr": self.mrr,
            "precision_at_k": self.precision_at_k,
            "recall_at_k": self.recall_at_k,
            "f1_score": self.f1_score,
        }

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> Optional["PretrainedBenchmarkMetrics"]:
        if not data:
            return None
        return cls(
            benchmark_source=data.get("benchmark_source", "Standard IR Benchmark"),
            dataset_description=data.get("dataset_description", ""),
            k_eval=data.get("k_eval", 10),
            ndcg_at_k=data.get("ndcg_at_k"),
            mrr=data.get("mrr"),
            precision_at_k=data.get("precision_at_k"),
            recall_at_k=data.get("recall_at_k"),
            f1_score=data.get("f1_score"),
        )


@dataclass
class ModelMetadata:

    model_id: str
    display_name: str
    model_type: str
    task_type: TaskType
    version: str = "1.0.0"
    embedding_dimension: Optional[int] = None
    max_sequence_length: Optional[int] = None
    runtime_requirements: str = "CPU (x86_64 / ARM), 256MB RAM"
    device: str = "cpu"
    precision: str = "float32"
    known_limitations: str = ""
    is_available: bool = True
    is_loaded: bool = False
    memory_footprint_mb: Optional[float] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    notes: str = ""
    pretrained_metrics: Optional[PretrainedBenchmarkMetrics] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "display_name": self.display_name,
            "model_type": self.model_type,
            "task_type": self.task_type.value,
            "version": self.version,
            "embedding_dimension": self.embedding_dimension,
            "max_sequence_length": self.max_sequence_length,
            "runtime_requirements": self.runtime_requirements,
            "device": self.device,
            "precision": self.precision,
            "known_limitations": self.known_limitations,
            "is_available": self.is_available,
            "is_loaded": self.is_loaded,
            "memory_footprint_mb": self.memory_footprint_mb,
            "parameters": self.parameters,
            "notes": self.notes,
            "pretrained_metrics": self.pretrained_metrics.to_dict() if self.pretrained_metrics else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModelMetadata":
        return cls(
            model_id=data["model_id"],
            display_name=data.get("display_name", data["model_id"]),
            model_type=data.get("model_type", "EMBEDDING"),
            task_type=TaskType(data.get("task_type", TaskType.SEMANTIC_RETRIEVAL.value)),
            version=data.get("version", "1.0.0"),
            embedding_dimension=data.get("embedding_dimension"),
            max_sequence_length=data.get("max_sequence_length"),
            runtime_requirements=data.get("runtime_requirements", "CPU"),
            device=data.get("device", "cpu"),
            precision=data.get("precision", "float32"),
            known_limitations=data.get("known_limitations", ""),
            is_available=bool(data.get("is_available", True)),
            is_loaded=bool(data.get("is_loaded", False)),
            memory_footprint_mb=data.get("memory_footprint_mb"),
            parameters=data.get("parameters", {}),
            notes=data.get("notes", ""),
            pretrained_metrics=PretrainedBenchmarkMetrics.from_dict(data.get("pretrained_metrics")),
        )


@dataclass
class EvaluationDatasetItem:

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    dataset_id: str = ""
    query_text: str = ""
    passage_text: str = ""
    relevance_grade: RelevanceGrade = RelevanceGrade.RELEVANT
    category: str = "GENERAL"
    reviewer_notes: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "dataset_id": self.dataset_id,
            "query_text": self.query_text,
            "passage_text": self.passage_text,
            "relevance_grade": self.relevance_grade.value,
            "category": self.category,
            "reviewer_notes": self.reviewer_notes,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvaluationDatasetItem":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            dataset_id=data.get("dataset_id", ""),
            query_text=data.get("query_text", ""),
            passage_text=data.get("passage_text", ""),
            relevance_grade=RelevanceGrade(int(data.get("relevance_grade", 1))),
            category=data.get("category", "GENERAL"),
            reviewer_notes=data.get("reviewer_notes", ""),
            metadata=data.get("metadata", {}),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
        )


@dataclass
class EvaluationDataset:

    name: str
    version: str = "v1.0"
    task: TaskType = TaskType.SEMANTIC_RETRIEVAL
    description: str = ""
    rubric_version: str = "rubric-v1.0"
    created_by: str = "Authorized Reviewer"
    is_frozen: bool = False
    item_count: int = 0
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    items: List[EvaluationDatasetItem] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "task": self.task.value,
            "description": self.description,
            "rubric_version": self.rubric_version,
            "created_by": self.created_by,
            "is_frozen": self.is_frozen,
            "item_count": self.item_count or len(self.items),
            "items": [it.to_dict() for it in self.items],
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvaluationDataset":
        raw_items = data.get("items", [])
        items = [EvaluationDatasetItem.from_dict(it) for it in raw_items]
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            name=data["name"],
            version=data.get("version", "v1.0"),
            task=TaskType(data.get("task", TaskType.SEMANTIC_RETRIEVAL.value)),
            description=data.get("description", ""),
            rubric_version=data.get("rubric_version", "rubric-v1.0"),
            created_by=data.get("created_by", "Authorized Reviewer"),
            is_frozen=bool(data.get("is_frozen", False)),
            item_count=int(data.get("item_count", len(items))),
            items=items,
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
        )


@dataclass
class BenchmarkConfiguration:

    models: List[str]
    dataset_id: Optional[str] = None
    session_id: Optional[str] = None
    top_k: int = 5
    similarity_threshold: float = 0.50
    batch_size: int = 32
    random_seed: int = 42
    device: str = "cpu"
    normalize_embeddings: bool = True
    reranker_model: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "models": self.models,
            "dataset_id": self.dataset_id,
            "session_id": self.session_id,
            "top_k": self.top_k,
            "similarity_threshold": self.similarity_threshold,
            "batch_size": self.batch_size,
            "random_seed": self.random_seed,
            "device": self.device,
            "normalize_embeddings": self.normalize_embeddings,
            "reranker_model": self.reranker_model,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BenchmarkConfiguration":
        return cls(
            models=data.get("models", []),
            dataset_id=data.get("dataset_id"),
            session_id=data.get("session_id"),
            top_k=int(data.get("top_k", 5)),
            similarity_threshold=float(data.get("similarity_threshold", 0.50)),
            batch_size=int(data.get("batch_size", 32)),
            random_seed=int(data.get("random_seed", 42)),
            device=data.get("device", "cpu"),
            normalize_embeddings=bool(data.get("normalize_embeddings", True)),
            reranker_model=data.get("reranker_model"),
        )


@dataclass
class ModelBenchmarkResult:

    model_id: str
    model_name: str
    model_type: str
    latency_seconds: float = 0.0
    throughput_items_per_sec: float = 0.0
    memory_peak_mb: float = 0.0
    failure_count: int = 0
    descriptive_stats: Dict[str, float] = field(default_factory=dict)
    ground_truth_metrics: Optional[Dict[str, float]] = None
    ranking_order: List[str] = field(default_factory=list)
    detailed_scores: List[Dict[str, Any]] = field(default_factory=list)
    error_log: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "model_name": self.model_name,
            "model_type": self.model_type,
            "latency_seconds": round(self.latency_seconds, 4),
            "throughput_items_per_sec": round(self.throughput_items_per_sec, 2),
            "memory_peak_mb": round(self.memory_peak_mb, 2),
            "failure_count": self.failure_count,
            "descriptive_stats": self.descriptive_stats,
            "ground_truth_metrics": self.ground_truth_metrics,
            "ranking_order": self.ranking_order,
            "detailed_scores": self.detailed_scores,
            "error_log": self.error_log,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModelBenchmarkResult":
        return cls(
            model_id=data["model_id"],
            model_name=data.get("model_name", data["model_id"]),
            model_type=data.get("model_type", "EMBEDDING"),
            latency_seconds=float(data.get("latency_seconds", 0.0)),
            throughput_items_per_sec=float(data.get("throughput_items_per_sec", 0.0)),
            memory_peak_mb=float(data.get("memory_peak_mb", 0.0)),
            failure_count=int(data.get("failure_count", 0)),
            descriptive_stats=data.get("descriptive_stats", {}),
            ground_truth_metrics=data.get("ground_truth_metrics"),
            ranking_order=data.get("ranking_order", []),
            detailed_scores=data.get("detailed_scores", []),
            error_log=data.get("error_log", []),
        )


@dataclass
class BenchmarkRunRecord:

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    run_name: str = ""
    configuration: BenchmarkConfiguration = field(default_factory=lambda: BenchmarkConfiguration(models=[]))
    environment_info: Dict[str, Any] = field(default_factory=dict)
    model_results: Dict[str, ModelBenchmarkResult] = field(default_factory=dict)
    pairwise_agreement: Dict[str, float] = field(default_factory=dict)
    status: BenchmarkStatus = BenchmarkStatus.PENDING
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None
    error_log: List[str] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "run_name": self.run_name,
            "configuration": self.configuration.to_dict(),
            "environment_info": self.environment_info,
            "model_results": {k: v.to_dict() for k, v in self.model_results.items()},
            "pairwise_agreement": self.pairwise_agreement,
            "status": self.status.value,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error_log": self.error_log,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BenchmarkRunRecord":
        raw_results = data.get("model_results", {})
        results = {k: ModelBenchmarkResult.from_dict(v) for k, v in raw_results.items()}
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            run_name=data.get("run_name", ""),
            configuration=BenchmarkConfiguration.from_dict(data.get("configuration", {})),
            environment_info=data.get("environment_info", {}),
            model_results=results,
            pairwise_agreement=data.get("pairwise_agreement", {}),
            status=BenchmarkStatus(data.get("status", BenchmarkStatus.COMPLETED.value)),
            started_at=data.get("started_at", datetime.now(timezone.utc).isoformat()),
            completed_at=data.get("completed_at"),
            error_log=data.get("error_log", []),
            notes=data.get("notes", ""),
        )
