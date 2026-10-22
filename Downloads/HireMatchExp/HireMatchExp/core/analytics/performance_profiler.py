
from dataclasses import dataclass, field
import gc
import os
from pathlib import Path
import platform
import sys
import time
from typing import Any, Dict, List, Optional
import psutil

from config import AppConfig
from core.models.enums import ProcessingStatus
from core.models.report_models import ExportFormat
from core.models.job import Job
from core.services.session_orchestrator import ScreeningOrchestrator
from core.storage.database import Database


@dataclass
class StageProfileResult:
    stage_name: str
    elapsed_seconds: float
    items_processed: int
    throughput_per_second: float
    memory_rss_mb: float
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PerformanceBenchmarkReport:
    system_info: Dict[str, Any]
    config_summary: Dict[str, Any]
    batch_size: int
    total_elapsed_seconds: float
    peak_memory_mb: float
    stage_results: List[StageProfileResult] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "system_info": self.system_info,
            "config_summary": self.config_summary,
            "batch_size": self.batch_size,
            "total_elapsed_seconds": round(self.total_elapsed_seconds, 3),
            "peak_memory_mb": round(self.peak_memory_mb, 1),
            "stage_results": [
                {
                    "stage_name": r.stage_name,
                    "elapsed_seconds": round(r.elapsed_seconds, 3),
                    "items_processed": r.items_processed,
                    "throughput_per_sec": round(r.throughput_per_second, 2),
                    "memory_rss_mb": round(r.memory_rss_mb, 1),
                    "details": r.details,
                }
                for r in self.stage_results
            ],
        }


class ApplicationPerformanceProfiler:

    def __init__(self, db: Database, config: Optional[AppConfig] = None):
        self.db = db
        self.config = config or AppConfig()
        self.orchestrator = ScreeningOrchestrator(db, self.config)
        self.process = psutil.Process(os.getpid())

    def get_system_metadata(self) -> Dict[str, Any]:
        mem = psutil.virtual_memory()
        return {
            "os_name": platform.system(),
            "os_release": platform.release(),
            "cpu_architecture": platform.machine(),
            "cpu_count_logical": psutil.cpu_count(logical=True),
            "cpu_count_physical": psutil.cpu_count(logical=False),
            "total_ram_gb": round(mem.total / (1024**3), 2),
            "available_ram_gb": round(mem.available / (1024**3), 2),
            "python_version": sys.version.split()[0],
        }

    def _get_current_rss_mb(self) -> float:
        return self.process.memory_info().rss / (1024 * 1024)

    def _generate_synthetic_resumes(self, count: int) -> List[Dict[str, Any]]:
        import fitz

        resumes = []
        skills_variations = [
            ("Alice Smith", "Python, Kubernetes, Docker, PostgreSQL, Go", "5 years experience", "BS Computer Science"),
            ("Bob Jones", "Python, Docker, AWS, Terraform", "3 years experience", "MS Software Engineering"),
            ("Charlie Brown", "Java, Spring Boot, MySQL, REST APIs", "4 years experience", "BS Information Technology"),
            ("Diana Prince", "Python, Machine Learning, PyTorch, SQL, Go", "6 years experience", "PhD Data Science"),
            ("Evan Wright", "JavaScript, React, Node.js, TypeScript", "2 years experience", "BA Web Development"),
        ]

        for i in range(count):
            name, skills, exp, edu = skills_variations[i % len(skills_variations)]
            cand_name = f"{name} #{i+1}"
            text = (
                f"{cand_name}\n"
                f"Email: candidate_{i+1}@test.example.com | Phone: +1-555-{i:04d}\n\n"
                f"SUMMARY\nExperienced professional specializing in modern backend systems.\n\n"
                f"TECHNICAL SKILLS\n{skills}\n\n"
                f"WORK EXPERIENCE\n"
                f"Senior Systems Engineer at TechCorp (2019 - 2024)\n"
                f"- Architected distributed systems with {skills.split(',')[0]} and containerized deployments.\n"
                f"- Demonstrated {exp}.\n\n"
                f"EDUCATION\n{edu} (2018)\n"
            )

            doc = fitz.open()
            page = doc.new_page()
            page.insert_text((50, 72), text)
            pdf_bytes = doc.tobytes()
            doc.close()

            resumes.append({
                "filename": f"candidate_{i+1:03d}_{name.lower().replace(' ', '_')}.pdf",
                "content": pdf_bytes,
                "size": len(pdf_bytes),
            })

        return resumes

    def run_benchmark(self, batch_size: int = 25) -> PerformanceBenchmarkReport:
        gc.collect()
        bench_start = time.perf_counter()
        initial_rss = self._get_current_rss_mb()
        peak_rss = initial_rss
        stage_results: List[StageProfileResult] = []

        system_info = self.get_system_metadata()
        config_summary = {
            "max_resumes_per_session": self.config.max_resumes_per_session,
            "processing_batch_size": self.config.processing_batch_size,
            "semantic_model": self.config.semantic_model_name,
            "embedding_dimension": 384,
        }

        t0 = time.perf_counter()
        job = self.orchestrator.job_repo.create(
            Job(
                title="Senior Distributed Systems Architect",
                original_description=(
                    "We are hiring a Senior Distributed Systems Architect with 5+ years experience in Python, "
                    "Kubernetes, Docker, PostgreSQL, and Go. Master's or Bachelor's degree in Computer Science preferred."
                ),
                department="Core Infrastructure",
            )
        )
        session = self.orchestrator.create_session(
            job_id=job.id,
            session_name=f"Performance Benchmark Session (N={batch_size})",
            max_resume_count=self.config.max_resumes_per_session,
        )
        t_stage1 = time.perf_counter() - t0
        peak_rss = max(peak_rss, self._get_current_rss_mb())
        stage_results.append(StageProfileResult(
            stage_name="1. Job Creation & Criteria Setup",
            elapsed_seconds=t_stage1,
            items_processed=1,
            throughput_per_second=1.0 / max(0.001, t_stage1),
            memory_rss_mb=self._get_current_rss_mb(),
            details={"job_id": job.id, "session_id": session.id},
        ))

        t0 = time.perf_counter()
        resumes = self._generate_synthetic_resumes(batch_size)
        ingest_res = self.orchestrator.add_resumes_to_session(session.id, resumes)
        t_stage2 = time.perf_counter() - t0
        peak_rss = max(peak_rss, self._get_current_rss_mb())
        stage_results.append(StageProfileResult(
            stage_name="2. Batch Ingestion & Validation",
            elapsed_seconds=t_stage2,
            items_processed=batch_size,
            throughput_per_second=batch_size / max(0.001, t_stage2),
            memory_rss_mb=self._get_current_rss_mb(),
            details={"enrolled": ingest_res.get("enrolled", 0), "duplicates": ingest_res.get("duplicate", 0)},
        ))

        t0 = time.perf_counter()
        extract_res = self.orchestrator.process_session_batch(session.id, batch_size=batch_size)
        t_stage3 = time.perf_counter() - t0
        processed_count = extract_res.get("processed_in_chunk", 0)
        peak_rss = max(peak_rss, self._get_current_rss_mb())
        stage_results.append(StageProfileResult(
            stage_name="3. Text Extraction & Structured Parsing",
            elapsed_seconds=t_stage3,
            items_processed=processed_count,
            throughput_per_second=processed_count / max(0.001, t_stage3),
            memory_rss_mb=self._get_current_rss_mb(),
            details={"processed": processed_count, "failed": extract_res.get("failed_in_chunk", 0)},
        ))

        t0 = time.perf_counter()
        eval_res = self.orchestrator.evaluate_session_multi_layer(session.id, batch_size=batch_size)
        t_stage4 = time.perf_counter() - t0
        eval_count = eval_res.get("evaluated_in_chunk", 0)
        peak_rss = max(peak_rss, self._get_current_rss_mb())
        stage_results.append(StageProfileResult(
            stage_name="4. Multi-Layer Evidence Evaluation",
            elapsed_seconds=t_stage4,
            items_processed=eval_count,
            throughput_per_second=eval_count / max(0.001, t_stage4),
            memory_rss_mb=self._get_current_rss_mb(),
            details={"evaluated": eval_count, "failed": eval_res.get("failed_in_chunk", 0)},
        ))

        t0 = time.perf_counter()
        scoring_res = self.orchestrator.score_session(session.id)
        ranked = self.orchestrator.get_ranked_candidates(session.id)
        t_stage5 = time.perf_counter() - t0
        scored_count = len(ranked)
        peak_rss = max(peak_rss, self._get_current_rss_mb())
        stage_results.append(StageProfileResult(
            stage_name="5. Transparent Scoring & Ranking",
            elapsed_seconds=t_stage5,
            items_processed=scored_count,
            throughput_per_second=scored_count / max(0.001, t_stage5),
            memory_rss_mb=self._get_current_rss_mb(),
            details={"scored_count": scored_count, "top_candidate": ranked[0].filename if ranked else "N/A"},
        ))

        t0 = time.perf_counter()
        analytics = self.orchestrator.get_session_analytics_profile(session.id)
        skills = self.orchestrator.get_skill_coverage_analytics(session.id)
        criteria = self.orchestrator.get_criterion_analytics(session.id)
        t_stage6 = time.perf_counter() - t0
        peak_rss = max(peak_rss, self._get_current_rss_mb())
        stage_results.append(StageProfileResult(
            stage_name="6. Analytics & Traceable Insights Assembly",
            elapsed_seconds=t_stage6,
            items_processed=1,
            throughput_per_second=1.0 / max(0.001, t_stage6),
            memory_rss_mb=self._get_current_rss_mb(),
            details={
                "mean_score": round(analytics.score_mean or 0.0, 1),
                "skills_analyzed": len(skills),
                "criteria_analyzed": len(criteria),
            },
        ))

        t0 = time.perf_counter()
        csv_bytes, _, _ = self.orchestrator.export_session_report(session.id, export_format=ExportFormat.CSV)
        xlsx_bytes, _, _ = self.orchestrator.export_session_report(session.id, export_format=ExportFormat.XLSX)
        t_stage7 = time.perf_counter() - t0
        peak_rss = max(peak_rss, self._get_current_rss_mb())
        stage_results.append(StageProfileResult(
            stage_name="7. Multi-Format Report Export (CSV + XLSX)",
            elapsed_seconds=t_stage7,
            items_processed=2,
            throughput_per_second=2.0 / max(0.001, t_stage7),
            memory_rss_mb=self._get_current_rss_mb(),
            details={"csv_size_kb": round(len(csv_bytes) / 1024, 1), "xlsx_size_kb": round(len(xlsx_bytes) / 1024, 1)},
        ))

        total_elapsed = time.perf_counter() - bench_start
        return PerformanceBenchmarkReport(
            system_info=system_info,
            config_summary=config_summary,
            batch_size=batch_size,
            total_elapsed_seconds=total_elapsed,
            peak_memory_mb=peak_rss,
            stage_results=stage_results,
        )
