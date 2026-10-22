
from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.app.api.deps import get_orchestrator
from backend.app.api.schemas.model_lab_schemas import (
    BenchmarkModelResult,
    BenchmarkRunRequest,
    BenchmarkRunResponse,
    DatasetItemResponse,
    ModelMetadataResponse,
    PretrainedMetricsResponse,
)
from core.model_lab.models import BenchmarkConfiguration, TaskType
from core.services.session_orchestrator import ScreeningOrchestrator
from core.utils.logger import logger

router = APIRouter(tags=["Model Laboratory"])


class LoadModelPayload(BaseModel):
    model_id: str
    device: str = "cpu"


class UnloadModelPayload(BaseModel):
    model_id: str


@router.get("/models", response_model=List[ModelMetadataResponse])
def list_models(
    task: Optional[str] = Query(None),
    model_type: Optional[str] = Query(None),
    orchestrator: ScreeningOrchestrator = Depends(get_orchestrator),
):
    try:
        task_enum = None
        if task:
            try:
                task_enum = TaskType(task)
            except ValueError:
                pass
        models = orchestrator.list_lab_models(task=task_enum, model_type=model_type)
        return [
            ModelMetadataResponse(
                model_id=m.model_id,
                display_name=m.display_name,
                model_type=m.model_type,
                task_type=m.task_type.value if hasattr(m.task_type, "value") else str(m.task_type),
                embedding_dimension=m.embedding_dimension,
                max_sequence_length=m.max_sequence_length,
                device=m.device,
                precision=m.precision,
                memory_footprint_mb=m.memory_footprint_mb,
                is_loaded=m.is_loaded,
                known_limitations=m.known_limitations,
                notes=m.notes,
                pretrained_metrics=(
                    PretrainedMetricsResponse(
                        benchmark_source=m.pretrained_metrics.benchmark_source,
                        dataset_description=m.pretrained_metrics.dataset_description,
                        k_eval=m.pretrained_metrics.k_eval,
                        ndcg_at_k=m.pretrained_metrics.ndcg_at_k,
                        mrr=m.pretrained_metrics.mrr,
                        precision_at_k=m.pretrained_metrics.precision_at_k,
                        recall_at_k=m.pretrained_metrics.recall_at_k,
                        f1_score=m.pretrained_metrics.f1_score,
                    )
                    if m.pretrained_metrics
                    else None
                ),
            )
            for m in models
        ]
    except Exception as e:
        logger.error(f"Error listing models: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list models: {str(e)}",
        )


@router.post("/models/load")
def load_model(
    payload: LoadModelPayload,
    orchestrator: ScreeningOrchestrator = Depends(get_orchestrator),
):
    try:
        orchestrator.load_lab_model(model_id=payload.model_id, device=payload.device)
        return {"status": "success", "message": f"Model '{payload.model_id}' loaded into memory."}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error loading model {payload.model_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load model: {str(e)}",
        )


@router.post("/models/unload")
def unload_model(
    payload: UnloadModelPayload,
    orchestrator: ScreeningOrchestrator = Depends(get_orchestrator),
):
    try:
        success = orchestrator.unload_lab_model(model_id=payload.model_id)
        return {"status": "success" if success else "not_loaded", "message": f"Model '{payload.model_id}' unloaded."}
    except Exception as e:
        logger.error(f"Error unloading model {payload.model_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to unload model: {str(e)}",
        )


@router.post("/models/clear-cache")
def clear_all_models(
    orchestrator: ScreeningOrchestrator = Depends(get_orchestrator),
):
    try:
        orchestrator.clear_all_lab_models()
        return {"status": "success", "message": "All models cleared from memory cache."}
    except Exception as e:
        logger.error(f"Error clearing models cache: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear model cache: {str(e)}",
        )


@router.get("/model-lab/benchmarks", response_model=List[BenchmarkRunResponse])
def list_benchmarks(
    dataset_id: Optional[str] = Query(None),
    session_id: Optional[str] = Query(None),
    orchestrator: ScreeningOrchestrator = Depends(get_orchestrator),
):
    try:
        runs = orchestrator.list_benchmark_runs(dataset_id=dataset_id, session_id=session_id)
        results = []
        for r in runs:
            m_res = {
                k: BenchmarkModelResult(
                    model_name=v.model_name,
                    model_type=v.model_type,
                    latency_seconds=v.latency_seconds,
                    throughput_items_per_sec=v.throughput_items_per_sec,
                    memory_peak_mb=v.memory_peak_mb,
                    failure_count=v.failure_count,
                    ground_truth_metrics=v.ground_truth_metrics,
                    descriptive_stats=v.descriptive_stats,
                    detailed_scores=v.detailed_scores,
                )
                for k, v in r.model_results.items()
            }
            results.append(
                BenchmarkRunResponse(
                    id=r.id,
                    run_name=r.run_name,
                    started_at=r.started_at,
                    completed_at=r.completed_at,
                    status=r.status.value if hasattr(r.status, "value") else str(r.status),
                    model_results=m_res,
                    pairwise_agreement=r.pairwise_agreement,
                    configuration=r.configuration.to_dict() if hasattr(r.configuration, "to_dict") else {},
                    error_message=r.error_log[0] if r.error_log else None,
                )
            )
        return results
    except Exception as e:
        logger.error(f"Error listing benchmarks: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list benchmarks: {str(e)}",
        )


@router.post("/model-lab/benchmarks", response_model=BenchmarkRunResponse)
def run_benchmark(
    payload: BenchmarkRunRequest,
    orchestrator: ScreeningOrchestrator = Depends(get_orchestrator),
):
    try:
        config = BenchmarkConfiguration(
            models=payload.models,
            dataset_id=payload.dataset_id,
            session_id=payload.session_id,
            top_k=payload.top_k,
            similarity_threshold=payload.similarity_threshold,
            batch_size=payload.batch_size,
        )

        record = orchestrator.run_model_benchmark(config=config, run_name=payload.run_name)

        m_res = {
            k: BenchmarkModelResult(
                model_name=v.model_name,
                model_type=v.model_type,
                latency_seconds=v.latency_seconds,
                throughput_items_per_sec=v.throughput_items_per_sec,
                memory_peak_mb=v.memory_peak_mb,
                failure_count=v.failure_count,
                ground_truth_metrics=v.ground_truth_metrics,
                descriptive_stats=v.descriptive_stats,
                detailed_scores=v.detailed_scores,
            )
            for k, v in record.model_results.items()
        }

        return BenchmarkRunResponse(
            id=record.id,
            run_name=record.run_name,
            started_at=record.started_at,
            completed_at=record.completed_at,
            status=record.status.value if hasattr(record.status, "value") else str(record.status),
            model_results=m_res,
            pairwise_agreement=record.pairwise_agreement,
            configuration=record.configuration.to_dict() if hasattr(record.configuration, "to_dict") else {},
            error_message=record.error_log[0] if record.error_log else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error running benchmark: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute benchmark: {str(e)}",
        )


@router.get("/model-lab/benchmarks/{run_id}", response_model=BenchmarkRunResponse)
def get_benchmark(
    run_id: str,
    orchestrator: ScreeningOrchestrator = Depends(get_orchestrator),
):
    record = orchestrator.get_benchmark_run(run_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Benchmark run '{run_id}' not found.")

    m_res = {
        k: BenchmarkModelResult(
            model_name=v.model_name,
            model_type=v.model_type,
            latency_seconds=v.latency_seconds,
            throughput_items_per_sec=v.throughput_items_per_sec,
            memory_peak_mb=v.memory_peak_mb,
            failure_count=v.failure_count,
            ground_truth_metrics=v.ground_truth_metrics,
            descriptive_stats=v.descriptive_stats,
            detailed_scores=v.detailed_scores,
        )
        for k, v in record.model_results.items()
    }

    return BenchmarkRunResponse(
        id=record.id,
        run_name=record.run_name,
        started_at=record.started_at,
        completed_at=record.completed_at,
        status=record.status.value if hasattr(record.status, "value") else str(record.status),
        model_results=m_res,
        pairwise_agreement=record.pairwise_agreement,
        configuration=record.configuration.to_dict() if hasattr(record.configuration, "to_dict") else {},
        error_message=record.error_log[0] if record.error_log else None,
    )


@router.get("/model-lab/datasets", response_model=List[DatasetItemResponse])
def list_datasets(
    task: Optional[str] = Query(None),
    orchestrator: ScreeningOrchestrator = Depends(get_orchestrator),
):
    try:
        task_enum = None
        if task:
            try:
                task_enum = TaskType(task)
            except ValueError:
                pass
        datasets = orchestrator.list_evaluation_datasets(task=task_enum)
        return [
            DatasetItemResponse(
                id=d.id,
                name=d.name,
                version=d.version,
                task=d.task.value if hasattr(d.task, "value") else str(d.task),
                item_count=d.item_count or len(d.items),
                is_frozen=d.is_frozen,
                rubric_version=d.rubric_version,
                created_at=d.created_at,
                description=d.description,
            )
            for d in datasets
        ]
    except Exception as e:
        logger.error(f"Error listing datasets: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list datasets: {str(e)}",
        )
