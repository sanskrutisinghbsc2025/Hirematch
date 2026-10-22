
from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional, Tuple
import uuid

import numpy as np

from core.evaluation.keyword_matcher import KeywordMatcher
from core.evaluation.semantic_matcher import SemanticMatcher
from core.model_lab.dataset_service import EvaluationDatasetService
from core.model_lab.metrics import EvaluationMetricsCalculator, ProfileContext
from core.model_lab.models import (
    BenchmarkConfiguration,
    BenchmarkRunRecord,
    BenchmarkStatus,
    EvaluationDatasetItem,
    ModelBenchmarkResult,
    RelevanceGrade,
)
from core.model_lab.registry import ModelRegistry
from core.storage.benchmark_repository import BenchmarkRunRepository
from core.storage.database import Database
from core.storage.embedding_cache import SQLiteEmbeddingCache
from core.storage.repositories import CandidateRepository, JobRepository, SessionRepository
from core.utils.logger import logger


class BenchmarkRunner:

    def __init__(
        self,
        registry: ModelRegistry,
        dataset_service: EvaluationDatasetService,
        db: Database,
    ):
        self.registry = registry
        self.dataset_service = dataset_service
        self.db = db
        self.run_repo = BenchmarkRunRepository(db)
        self.cache = SQLiteEmbeddingCache(db)
        self.session_repo = SessionRepository(db)
        self.job_repo = JobRepository(db)
        self.candidate_repo = CandidateRepository(db)

    def run_benchmark(
        self,
        config: BenchmarkConfiguration,
        run_name: Optional[str] = None,
    ) -> BenchmarkRunRecord:
        if not config.models:
            raise ValueError("At least one model must be selected for benchmarking.")

        warnings = []
        if len(config.models) > 1:
            is_comp, warnings = self.registry.validate_compatibility(config.models)
            if not is_comp:
                raise ValueError(f"Incompatible Model Selection: {'; '.join(warnings)}")
        else:
            meta = self.registry.get(config.models[0])
            if not meta:
                raise ValueError(f"Selected model not registered: {config.models[0]}")

        started_at = datetime.now(timezone.utc).isoformat()
        auto_name = run_name or f"Benchmark-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

        record = BenchmarkRunRecord(
            id=str(uuid.uuid4()),
            run_name=auto_name,
            configuration=config,
            environment_info=self.registry.get_runtime_system_info(),
            status=BenchmarkStatus.RUNNING,
            started_at=started_at,
            error_log=list(warnings),
        )

        try:
            items = self._resolve_benchmark_items(config)
            if not items:
                raise ValueError("No test items found for benchmark run.")

            model_results: Dict[str, ModelBenchmarkResult] = {}
            score_vectors: Dict[str, List[float]] = {}

            for model_id in config.models:
                logger.info(f"Running benchmark on model '{model_id}' ({len(items)} items)...")
                res, scores = self._evaluate_single_model(model_id, items, config)
                model_results[model_id] = res
                score_vectors[model_id] = scores

            pairwise_agreement: Dict[str, float] = {}
            model_keys = list(model_results.keys())
            for i in range(len(model_keys)):
                for j in range(i + 1, len(model_keys)):
                    m1 = model_keys[i]
                    m2 = model_keys[j]
                    pair_key = f"{m1} vs {m2}"
                    corr = EvaluationMetricsCalculator.compute_pairwise_rank_correlation(
                        score_vectors[m1], score_vectors[m2]
                    )
                    tau = corr.get("kendall_tau")
                    if tau is not None:
                        pairwise_agreement[pair_key] = tau

            record.model_results = model_results
            record.pairwise_agreement = pairwise_agreement
            record.status = BenchmarkStatus.COMPLETED
            record.completed_at = datetime.now(timezone.utc).isoformat()

            if config.dataset_id:
                self.dataset_service.freeze_dataset(config.dataset_id)

        except Exception as e:
            record.status = BenchmarkStatus.FAILED
            record.completed_at = datetime.now(timezone.utc).isoformat()
            record.error_log.append(f"Benchmark Failure: {str(e)}")
            logger.error(f"Benchmark run failed: {e}")
            raise
        finally:
            self.run_repo.save_run(record)

        return record

    def _resolve_benchmark_items(
        self, config: BenchmarkConfiguration
    ) -> List[EvaluationDatasetItem]:
        if config.dataset_id:
            dataset = self.dataset_service.get_dataset(config.dataset_id, load_items=True)
            if not dataset:
                raise ValueError(f"Evaluation Dataset '{config.dataset_id}' not found.")
            return dataset.items

        elif config.session_id:
            return self._build_items_from_screening_session(config.session_id)

        raise ValueError("Neither dataset_id nor session_id was provided for benchmark.")

    def _build_items_from_screening_session(
        self, session_id: str
    ) -> List[EvaluationDatasetItem]:
        session = self.session_repo.get(session_id)
        if not session:
            raise ValueError(f"Screening Session '{session_id}' not found.")

        job = self.job_repo.get(session.job_id)
        if not job:
            raise ValueError(f"Job for session '{session_id}' not found.")

        criteria = []
        sql_crit = "SELECT criterion_name FROM evaluation_criteria WHERE job_id = ? AND is_enabled = 1;"
        rows_crit = self.db.execute_query(sql_crit, (job.id,))
        for r in rows_crit:
            criteria.append(r["criterion_name"])

        if not criteria and hasattr(job, "parsed_requirements") and isinstance(job.parsed_requirements, dict):
            criteria = job.parsed_requirements.get("requirements", [])
        if not criteria:
            criteria = [job.title]

        enrolled = self.candidate_repo.list_by_session(session_id)
        items: List[EvaluationDatasetItem] = []

        for item in enrolled:
            cand = item["candidate"]
            text = cand.extracted_text or ""
            paragraphs = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 40]
            if not paragraphs:
                paragraphs = [text[:300]] if text else ["No text extracted."]

            for crit in criteria:
                for p in paragraphs[:3]:
                    items.append(
                        EvaluationDatasetItem(
                            id=str(uuid.uuid4()),
                            dataset_id=f"session_{session_id}",
                            query_text=crit,
                            passage_text=p,
                            relevance_grade=RelevanceGrade.UNCERTAIN,
                            category="SESSION_DATA",
                            metadata={"candidate_id": cand.id, "candidate_name": f"Cand-{cand.id[:8]}"},
                        )
                    )
        return items

    def _evaluate_single_model(
        self,
        model_id: str,
        items: List[EvaluationDatasetItem],
        config: BenchmarkConfiguration,
    ) -> Tuple[ModelBenchmarkResult, List[float]]:
        meta = self.registry.get(model_id)
        if not meta:
            raise ValueError(f"Model '{model_id}' is not registered.")

        scores: List[float] = []
        detailed_scores: List[Dict[str, Any]] = []
        failure_count = 0
        error_log = []

        with ProfileContext(item_count=len(items)) as profiler:
            try:
                loaded_model = self.registry.load_model(model_id, device=config.device)

                if meta.model_type == "EMBEDDING":
                    scores = self._score_embedding(loaded_model, items, config)

                elif meta.model_type == "RERANKER":
                    scores = self._score_reranker(loaded_model, items, config)

                elif model_id == "rule-based-keyword":
                    scores = self._score_rule_keyword(loaded_model, items)

                elif model_id == "tfidf-baseline":
                    scores = self._score_tfidf(items)

                else:
                    scores = [0.0] * len(items)
                    error_log.append(f"Model '{model_id}' scoring logic fallback.")

            except Exception as e:
                failure_count += 1
                error_log.append(f"Execution error for '{model_id}': {str(e)}")
                scores = [0.0] * len(items)

        for it, sc in zip(items, scores):
            pred_rel = sc >= config.similarity_threshold
            detailed_scores.append({
                "item_id": it.id,
                "query": it.query_text,
                "passage_snippet": it.passage_text[:120] + "..." if len(it.passage_text) > 120 else it.passage_text,
                "score": round(sc, 4),
                "predicted_relevant": pred_rel,
                "ground_truth_grade": it.relevance_grade.value,
                "ground_truth_category": it.category,
            })

        ranked_indices = np.argsort(scores)[::-1]
        ranking_order = [items[idx].id for idx in ranked_indices]

        desc_stats = EvaluationMetricsCalculator.compute_distribution_statistics(
            scores, threshold=config.similarity_threshold
        )

        ground_truth_metrics = None
        has_ground_truth = any(it.relevance_grade != RelevanceGrade.UNCERTAIN for it in items)
        if has_ground_truth:
            y_true = [it.relevance_grade.value > 0 for it in items]
            y_pred = [sc >= config.similarity_threshold for sc in scores]

            ranked_labels = [items[idx].relevance_grade.value > 0 for idx in ranked_indices]
            ranked_grades = [max(0, items[idx].relevance_grade.value) for idx in ranked_indices]
            total_relevant = sum(1 for yt in y_true if yt)

            cls_metrics = EvaluationMetricsCalculator.compute_classification_metrics(y_true, y_pred)
            p_at_k = EvaluationMetricsCalculator.precision_at_k(ranked_labels, config.top_k)
            r_at_k = EvaluationMetricsCalculator.recall_at_k(ranked_labels, total_relevant, config.top_k)
            ndcg_val = EvaluationMetricsCalculator.ndcg_at_k(ranked_grades, config.top_k)
            mrr_val = EvaluationMetricsCalculator.mean_reciprocal_rank(ranked_labels)

            ground_truth_metrics = {
                **cls_metrics,
                f"precision_at_{config.top_k}": p_at_k,
                f"recall_at_{config.top_k}": r_at_k,
                f"ndcg_at_{config.top_k}": ndcg_val,
                "mrr": mrr_val,
            }

        res = ModelBenchmarkResult(
            model_id=meta.model_id,
            model_name=meta.display_name,
            model_type=meta.model_type,
            latency_seconds=profiler.elapsed_seconds,
            throughput_items_per_sec=profiler.throughput,
            memory_peak_mb=profiler.mem_peak_mb,
            failure_count=failure_count,
            descriptive_stats=desc_stats,
            ground_truth_metrics=ground_truth_metrics,
            ranking_order=ranking_order,
            detailed_scores=detailed_scores,
            error_log=error_log,
        )
        return res, scores

    def _score_embedding(
        self, provider: Any, items: List[EvaluationDatasetItem], config: BenchmarkConfiguration
    ) -> List[float]:
        matcher = SemanticMatcher(provider)
        scores = []

        queries = [it.query_text for it in items]
        passages = [it.passage_text for it in items]

        if "e5" in provider.model_name.lower():
            queries = [f"query: {q}" for q in queries]
            passages = [f"passage: {p}" for p in passages]

        unique_queries = list(dict.fromkeys(queries))
        unique_passages = list(dict.fromkeys(passages))

        q_embed_array = provider.encode(unique_queries, batch_size=config.batch_size, normalize=config.normalize_embeddings)
        p_embed_array = provider.encode(unique_passages, batch_size=config.batch_size, normalize=config.normalize_embeddings)

        q_embed_map = {q: q_embed_array[i] for i, q in enumerate(unique_queries)}
        p_embed_map = {p: p_embed_array[i] for i, p in enumerate(unique_passages)}

        for q, p in zip(queries, passages):
            q_vec = q_embed_map[q]
            p_vec = p_embed_map[p]
            sim = float(np.dot(q_vec, p_vec))
            sim = max(0.0, min(1.0, (sim + 1.0) / 2.0)) if not config.normalize_embeddings else max(0.0, min(1.0, sim))
            scores.append(round(sim, 4))

        return scores

    def _score_reranker(
        self, reranker: Any, items: List[EvaluationDatasetItem], config: BenchmarkConfiguration
    ) -> List[float]:
        pairs = [(it.query_text, it.passage_text) for it in items]
        raw_scores = reranker.score_pairs(pairs, batch_size=config.batch_size)
        scores = []
        for s in raw_scores:
            val = 1.0 / (1.0 + np.exp(-s)) if s < 0 or s > 1 else s
            scores.append(round(float(val), 4))
        return scores

    def _score_rule_keyword(
        self, matcher: Any, items: List[EvaluationDatasetItem]
    ) -> List[float]:
        scores = []
        for it in items:
            terms = [t.strip() for t in it.query_text.split() if len(t.strip()) > 2]
            hit_count = 0
            for t in terms:
                hit = matcher._scan_text_for_term(it.passage_text, t, t, "EXPERIENCE")
                if hit and not hit.is_negated:
                    hit_count += 1
            sc = hit_count / max(1, len(terms))
            scores.append(round(min(1.0, sc * 1.5), 4))
        return scores

    def _score_tfidf(self, items: List[EvaluationDatasetItem]) -> List[float]:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity

        scores = []
        for it in items:
            try:
                vec = TfidfVectorizer(ngram_range=(1, 2))
                mat = vec.fit_transform([it.query_text, it.passage_text])
                sim = float(cosine_similarity(mat[0:1], mat[1:2])[0][0])
                scores.append(round(max(0.0, min(1.0, sim)), 4))
            except Exception:
                scores.append(0.0)
        return scores
