
import argparse
import json
from pathlib import Path
import sys
import tempfile

from config import AppConfig
from core.analytics.performance_profiler import ApplicationPerformanceProfiler
from core.storage.database import Database


def main():
    parser = argparse.ArgumentParser(description="HireMatch Performance Profiler CLI")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=25,
        help="Number of synthetic candidate resumes to profile in the screening session (max 100).",
    )
    parser.add_argument(
        "--output-file",
        type=str,
        default="docs/performance_telemetry.json",
        help="Target output file path to write telemetry results.",
    )
    args = parser.parse_args()

    batch_size = max(1, min(100, args.batch_size))

    print("=" * 75)
    print(" [HireMatch] Application Performance Benchmark & Telemetry Runner")
    print(f" Target Batch Size: {batch_size} Synthetic Resumes (Hard Cap: 100)")
    print("=" * 75)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_db = Path(tmp_dir) / "profile_benchmark.db"
        db = Database(tmp_db)
        db.initialize_schema()

        cfg = AppConfig(
            base_dir=Path(tmp_dir),
            db_path=tmp_db,
            processing_batch_size=batch_size,
        )

        profiler = ApplicationPerformanceProfiler(db, cfg)
        sys_info = profiler.get_system_metadata()

        print(f" Host OS:          {sys_info['os_name']} {sys_info['os_release']} ({sys_info['cpu_architecture']})")
        print(f" CPU Cores:        {sys_info['cpu_count_logical']} Logical ({sys_info['cpu_count_physical']} Physical)")
        print(f" Total System RAM: {sys_info['total_ram_gb']} GB (Available: {sys_info['available_ram_gb']} GB)")
        print(f" Python Runtime:   {sys_info['python_version']}")
        print("-" * 75)
        print(" Executing full-pipeline benchmark...")

        report = profiler.run_benchmark(batch_size=batch_size)

        print("\n" + "=" * 75)
        print(f" [Results] Performance Summary (Batch Size: {report.batch_size})")
        print("=" * 75)
        print(f" {'Stage Description'.ljust(44)} {'Elapsed':>10} {'Throughput':>16}")
        print("-" * 75)

        for s in report.stage_results:
            elapsed_str = f"{s.elapsed_seconds:.3f}s"
            tp_str = f"{s.throughput_per_second:.1f} it/s" if s.throughput_per_second > 0 else "N/A"
            print(f" {s.stage_name.ljust(44)} {elapsed_str:>10} {tp_str:>16}")

        print("-" * 75)
        print(f" Total Pipeline Execution Time: {report.total_elapsed_seconds:.2f} seconds")
        print(f" Peak Process Memory (RSS):    {report.peak_memory_mb:.1f} MB")
        print("=" * 75)

        out_path = Path(args.output_file)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2)

        print(f" Detailed telemetry saved to: {out_path.resolve()}\n")


if __name__ == "__main__":
    main()
