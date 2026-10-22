
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class PretrainedMetricsResponse(BaseModel):
    benchmark_source: str
    dataset_description: Optional[str] = ""
    k_eval: int = 10
    ndcg_at_k: Optional[float] = None
    mrr: Optional[float] = None
    precision_at_k: Optional[float] = None
    recall_at_k: Optional[float] = None
    f1_score: Optional[float] = None


class ModelMetadataResponse(BaseModel):
    model_id: str
    display_name: str
    model_type: str
    task_type: str
    embedding_dimension: Optional[int] = None
    max_sequence_length: Optional[int] = None
    device: str
    precision: str
    memory_footprint_mb: Optional[float] = None
    is_loaded: bool
    known_limitations: Optional[str] = None
    notes: Optional[str] = None
    pretrained_metrics: Optional[PretrainedMetricsResponse] = None


class BenchmarkRunRequest(BaseModel):
    models: List[str] = Field(..., min_length=2, max_length=5)
    dataset_id: Optional[str] = None
    session_id: Optional[str] = None
    top_k: int = Field(default=5, ge=1, le=20)
    similarity_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    batch_size: int = Field(default=32, ge=1, le=128)
    run_name: Optional[str] = None


class BenchmarkModelResult(BaseModel):
    model_name: str
    model_type: str
    latency_seconds: float
    throughput_items_per_sec: float
    memory_peak_mb: float
    failure_count: int
    ground_truth_metrics: Optional[Dict[str, Any]] = None
    descriptive_stats: Optional[Dict[str, Any]] = None
    detailed_scores: List[Dict[str, Any]] = []


class BenchmarkRunResponse(BaseModel):
    id: str
    run_name: str
    started_at: str
    completed_at: Optional[str] = None
    status: str
    model_results: Dict[str, BenchmarkModelResult]
    pairwise_agreement: Dict[str, float]
    configuration: Dict[str, Any]
    error_message: Optional[str] = None


class DatasetItemResponse(BaseModel):
    id: str
    name: str
    version: str
    task: str
    item_count: int
    is_frozen: bool
    rubric_version: str
    created_at: str
    description: Optional[str] = None
