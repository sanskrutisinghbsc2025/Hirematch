
import json
from typing import Any, Dict, List, Optional

from core.model_lab.models import (
    BenchmarkConfiguration,
    BenchmarkRunRecord,
    BenchmarkStatus,
    EvaluationDataset,
    EvaluationDatasetItem,
    ModelBenchmarkResult,
    RelevanceGrade,
    TaskType,
)
from core.storage.database import Database
from core.utils.logger import logger


class EvaluationDatasetRepository:

    def __init__(self, db: Database):
        self.db = db

    def create_dataset(self, dataset: EvaluationDataset) -> EvaluationDataset:
        sql_ds = """
        INSERT INTO evaluation_datasets (id, name, version, task, description, rubric_version, created_by, is_frozen, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        self.db.execute_non_query(
            sql_ds,
            (
                dataset.id,
                dataset.name,
                dataset.version,
                dataset.task.value,
                dataset.description,
                dataset.rubric_version,
                dataset.created_by,
                1 if dataset.is_frozen else 0,
                dataset.created_at,
            ),
        )

        if dataset.items:
            self._insert_items_raw(dataset.items)

        logger.info(f"Created Evaluation Dataset '{dataset.name}' ({dataset.version}, id={dataset.id})")
        return dataset

    def get_dataset(self, dataset_id: str, load_items: bool = True) -> Optional[EvaluationDataset]:
        sql = "SELECT * FROM evaluation_datasets WHERE id = ?;"
        rows = self.db.execute_query(sql, (dataset_id,))
        if not rows:
            return None
        r = rows[0]

        items: List[EvaluationDatasetItem] = []
        if load_items:
            items = self.get_items_by_dataset(dataset_id)

        return EvaluationDataset(
            id=r["id"],
            name=r["name"],
            version=r["version"],
            task=TaskType(r["task"]),
            description=r["description"] or "",
            rubric_version=r["rubric_version"],
            created_by=r["created_by"],
            is_frozen=bool(r["is_frozen"]),
            item_count=len(items) if load_items else 0,
            items=items,
            created_at=r["created_at"],
        )

    def list_datasets(self, task: Optional[TaskType] = None) -> List[EvaluationDataset]:
        if task:
            sql = "SELECT * FROM evaluation_datasets WHERE task = ? ORDER BY created_at DESC;"
            rows = self.db.execute_query(sql, (task.value,))
        else:
            sql = "SELECT * FROM evaluation_datasets ORDER BY created_at DESC;"
            rows = self.db.execute_query(sql)

        datasets = []
        for r in rows:
            sql_cnt = "SELECT COUNT(*) as cnt FROM evaluation_dataset_items WHERE dataset_id = ?;"
            cnt_rows = self.db.execute_query(sql_cnt, (r["id"],))
            cnt = cnt_rows[0]["cnt"] if cnt_rows else 0

            datasets.append(
                EvaluationDataset(
                    id=r["id"],
                    name=r["name"],
                    version=r["version"],
                    task=TaskType(r["task"]),
                    description=r["description"] or "",
                    rubric_version=r["rubric_version"],
                    created_by=r["created_by"],
                    is_frozen=bool(r["is_frozen"]),
                    item_count=cnt,
                    items=[],
                    created_at=r["created_at"],
                )
            )
        return datasets

    def _insert_items_raw(self, items: List[EvaluationDatasetItem]) -> None:
        if not items:
            return

        sql = """
        INSERT OR REPLACE INTO evaluation_dataset_items
        (id, dataset_id, query_text, passage_text, relevance_grade, category, reviewer_notes, metadata, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        params = [
            (
                it.id,
                it.dataset_id,
                it.query_text,
                it.passage_text,
                it.relevance_grade.value,
                it.category,
                it.reviewer_notes,
                json.dumps(it.metadata),
                it.created_at,
            )
            for it in items
        ]
        self.db.execute_batch(sql, params)

    def add_items(self, items: List[EvaluationDatasetItem]) -> None:
        if not items:
            return

        ds_id = items[0].dataset_id
        if self.is_frozen(ds_id):
            raise ValueError(f"Cannot add items: Evaluation Dataset '{ds_id}' is frozen.")

        self._insert_items_raw(items)

    def get_items_by_dataset(self, dataset_id: str) -> List[EvaluationDatasetItem]:
        sql = "SELECT * FROM evaluation_dataset_items WHERE dataset_id = ? ORDER BY created_at ASC;"
        rows = self.db.execute_query(sql, (dataset_id,))
        return [
            EvaluationDatasetItem(
                id=r["id"],
                dataset_id=r["dataset_id"],
                query_text=r["query_text"],
                passage_text=r["passage_text"],
                relevance_grade=RelevanceGrade(int(r["relevance_grade"])),
                category=r["category"],
                reviewer_notes=r["reviewer_notes"] or "",
                metadata=json.loads(r["metadata"] or "{}"),
                created_at=r["created_at"],
            )
            for r in rows
        ]

    def freeze_dataset(self, dataset_id: str) -> None:
        sql = "UPDATE evaluation_datasets SET is_frozen = 1 WHERE id = ?;"
        self.db.execute_non_query(sql, (dataset_id,))
        logger.info(f"Evaluation Dataset '{dataset_id}' has been permanently frozen.")

    def is_frozen(self, dataset_id: str) -> bool:
        sql = "SELECT is_frozen FROM evaluation_datasets WHERE id = ?;"
        rows = self.db.execute_query(sql, (dataset_id,))
        return bool(rows[0]["is_frozen"]) if rows else False

    def delete_dataset(self, dataset_id: str) -> bool:
        sql = "DELETE FROM evaluation_datasets WHERE id = ?;"
        self.db.execute_non_query(sql, (dataset_id,))
        return True


class BenchmarkRunRepository:

    def __init__(self, db: Database):
        self.db = db

    def save_run(self, run: BenchmarkRunRecord) -> BenchmarkRunRecord:
        sql = """
        INSERT OR REPLACE INTO model_benchmark_runs
        (id, run_name, dataset_id, session_id, config_json, results_json, pairwise_json, status, error_log, started_at, completed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        config_data = {
            **run.configuration.to_dict(),
            "_environment": run.environment_info,
            "_notes": run.notes,
        }
        results_data = {k: v.to_dict() for k, v in run.model_results.items()}

        self.db.execute_non_query(
            sql,
            (
                run.id,
                run.run_name,
                run.configuration.dataset_id,
                run.configuration.session_id,
                json.dumps(config_data),
                json.dumps(results_data),
                json.dumps(run.pairwise_agreement),
                run.status.value,
                json.dumps(run.error_log),
                run.started_at,
                run.completed_at,
            ),
        )
        logger.info(f"Saved Benchmark Run '{run.run_name}' (id={run.id}, status={run.status.value})")
        return run

    def get_run(self, run_id: str) -> Optional[BenchmarkRunRecord]:
        sql = "SELECT * FROM model_benchmark_runs WHERE id = ?;"
        rows = self.db.execute_query(sql, (run_id,))
        if not rows:
            return None
        r = rows[0]

        cfg_dict = json.loads(r["config_json"] or "{}")
        env_info = cfg_dict.pop("_environment", {})
        notes = cfg_dict.pop("_notes", "")

        res_dict = json.loads(r["results_json"] or "{}")
        model_results = {k: ModelBenchmarkResult.from_dict(v) for k, v in res_dict.items()}

        return BenchmarkRunRecord(
            id=r["id"],
            run_name=r["run_name"],
            configuration=BenchmarkConfiguration.from_dict(cfg_dict),
            environment_info=env_info,
            model_results=model_results,
            pairwise_agreement=json.loads(r["pairwise_json"] or "{}"),
            status=BenchmarkStatus(r["status"]),
            started_at=r["started_at"],
            completed_at=r["completed_at"],
            error_log=json.loads(r["error_log"] or "[]"),
            notes=notes,
        )

    def list_runs(
        self, dataset_id: Optional[str] = None, session_id: Optional[str] = None
    ) -> List[BenchmarkRunRecord]:
        if dataset_id:
            sql = "SELECT * FROM model_benchmark_runs WHERE dataset_id = ? ORDER BY started_at DESC;"
            rows = self.db.execute_query(sql, (dataset_id,))
        elif session_id:
            sql = "SELECT * FROM model_benchmark_runs WHERE session_id = ? ORDER BY started_at DESC;"
            rows = self.db.execute_query(sql, (session_id,))
        else:
            sql = "SELECT * FROM model_benchmark_runs ORDER BY started_at DESC;"
            rows = self.db.execute_query(sql)

        runs = []
        for r in rows:
            cfg_dict = json.loads(r["config_json"] or "{}")
            env_info = cfg_dict.pop("_environment", {})
            notes = cfg_dict.pop("_notes", "")
            res_dict = json.loads(r["results_json"] or "{}")
            model_results = {k: ModelBenchmarkResult.from_dict(v) for k, v in res_dict.items()}

            runs.append(
                BenchmarkRunRecord(
                    id=r["id"],
                    run_name=r["run_name"],
                    configuration=BenchmarkConfiguration.from_dict(cfg_dict),
                    environment_info=env_info,
                    model_results=model_results,
                    pairwise_agreement=json.loads(r["pairwise_json"] or "{}"),
                    status=BenchmarkStatus(r["status"]),
                    started_at=r["started_at"],
                    completed_at=r["completed_at"],
                    error_log=json.loads(r["error_log"] or "[]"),
                    notes=notes,
                )
            )
        return runs

    def delete_run(self, run_id: str) -> bool:
        sql = "DELETE FROM model_benchmark_runs WHERE id = ?;"
        self.db.execute_non_query(sql, (run_id,))
        return True
