
import importlib
import os
from pathlib import Path
import platform
import sys
from typing import Dict, List, Tuple


def check_python_version() -> Tuple[bool, str]:
    major, minor = sys.version_info.major, sys.version_info.minor
    version_str = f"{major}.{minor}.{sys.version_info.micro}"
    if (major, minor) >= (3, 10):
        return True, f"Python {version_str} (Compatible: >= 3.10)"
    return False, f"Python {version_str} (Incompatible: Requires >= 3.10)"


def check_dependencies() -> Tuple[List[Tuple[str, bool, str]], List[Tuple[str, bool, str]]]:
    required_packages = [
        ("fastapi", "FastAPI Modern Web Framework"),
        ("uvicorn", "Uvicorn ASGI High-Performance Server"),
        ("sqlite3", "Standard SQLite Embedded Database"),
        ("openpyxl", "Excel Multi-Tab Report Generation"),
        ("plotly", "Interactive Data Analytics Visualizations"),
        ("numpy", "Numerical & Statistical Computing"),
        ("sentence_transformers", "Pretrained Dense Semantic Embeddings"),
        ("torch", "PyTorch Neural Tensor Backend"),
        ("docx", "DOCX Resume Ingestion & Parsing (python-docx)"),
    ]

    optional_packages = [
        ("sklearn", "Scikit-Learn TF-IDF Baseline & Metrics"),
        ("spacy", "spaCy Linguistic Parser (Optional Extension)"),
    ]

    req_results = []
    for pkg_name, description in required_packages:
        try:
            mod = importlib.import_module(pkg_name)
            version = getattr(mod, "__version__", "Available")
            req_results.append((pkg_name, True, f"{description} (v{version})"))
        except ImportError:
            req_results.append((pkg_name, False, f"{description} (Missing: run 'pip install {pkg_name}')"))

    try:
        import pymupdf
        version = getattr(pymupdf, "__version__", "Available")
        req_results.append(("pymupdf", True, f"PyMuPDF PDF Text & Vector Formatter (v{version})"))
    except ImportError:
        try:
            import fitz
            version = getattr(fitz, "__version__", "Available")
            req_results.append(("fitz", True, f"PyMuPDF / fitz Engine (v{version})"))
        except ImportError:
            req_results.append(("pymupdf", False, "PyMuPDF PDF Engine (Missing: run 'pip install pymupdf')"))

    opt_results = []
    for pkg_name, description in optional_packages:
        try:
            mod = importlib.import_module(pkg_name)
            version = getattr(mod, "__version__", "Available")
            opt_results.append((pkg_name, True, f"{description} (v{version})"))
        except ImportError:
            opt_results.append((pkg_name, False, f"{description} (Optional: install with 'pip install {pkg_name}')"))

    return req_results, opt_results


def check_storage_directories(base_dir: Path) -> List[Tuple[str, bool, str]]:
    dirs_to_check = [
        ("data", base_dir / "data"),
        ("reports", base_dir / "reports"),
        ("temp", base_dir / "temp"),
        ("config", base_dir / "config"),
    ]

    results = []
    for name, path in dirs_to_check:
        try:
            path.mkdir(parents=True, exist_ok=True)
            test_file = path / ".write_test.tmp"
            with open(test_file, "w") as f:
                f.write("ok")
            test_file.unlink()
            results.append((name, True, f"Writable directory: {path}"))
        except Exception as e:
            results.append((name, False, f"Directory error for {path}: {e}"))

    return results


def check_taxonomy_file(base_dir: Path) -> Tuple[bool, str]:
    tax_path = base_dir / "config" / "skills_db.json"
    if tax_path.exists() and tax_path.is_file():
        size_kb = tax_path.stat().st_size / 1024
        return True, f"Skills Taxonomy Database present ({tax_path.name}, {size_kb:.1f} KB)"
    return False, f"Missing Skills Taxonomy Database at {tax_path}"


def check_database_initialization(base_dir: Path) -> Tuple[bool, str]:
    try:
        from core.storage.database import Database
        db_path = base_dir / "data" / "system_check_temp.db"
        db = Database(db_path)
        db.initialize_schema()
        tables = db.execute_query("SELECT name FROM sqlite_master WHERE type='table';")
        table_names = [t["name"] for t in tables if not t["name"].startswith("sqlite_")]
        if db_path.exists():
            db_path.unlink(missing_ok=True)
        return True, f"SQLite schema initialized successfully ({len(table_names)} tables verified)"
    except Exception as e:
        return False, f"Database initialization failed: {e}"


def run_all_checks() -> bool:
    base_dir = Path(__file__).resolve().parent

    print("=" * 70)
    print(" [HireMatch] System Environment & Pre-Flight Diagnostics")
    print("=" * 70)
    print(f" OS Platform:     {platform.system()} {platform.release()} ({platform.machine()})")
    print(f" Working Dir:     {base_dir}")
    print("-" * 70)

    all_passed = True

    py_ok, py_msg = check_python_version()
    status_symbol = "[PASS]" if py_ok else "[FAIL]"
    print(f" {status_symbol} Runtime:       {py_msg}")
    if not py_ok:
        all_passed = False

    print("\n Core Required Dependencies:")
    req_results, opt_results = check_dependencies()
    for name, ok, msg in req_results:
        symbol = "[PASS]" if ok else "[FAIL]"
        print(f"   {symbol} {name.ljust(22)} {msg}")
        if not ok:
            all_passed = False

    print("\n Optional Pretrained Extensions:")
    for name, ok, msg in opt_results:
        symbol = "[PASS]" if ok else "[INFO]"
        print(f"   {symbol} {name.ljust(22)} {msg}")

    print("\n Storage & Filesystem Checks:")
    storage_results = check_storage_directories(base_dir)
    for name, ok, msg in storage_results:
        symbol = "[PASS]" if ok else "[FAIL]"
        print(f"   {symbol} {name.ljust(12)} {msg}")
        if not ok:
            all_passed = False

    tax_ok, tax_msg = check_taxonomy_file(base_dir)
    symbol = "[PASS]" if tax_ok else "[FAIL]"
    print(f"\n {symbol} Taxonomy:      {tax_msg}")
    if not tax_ok:
        all_passed = False

    db_ok, db_msg = check_database_initialization(base_dir)
    symbol = "[PASS]" if db_ok else "[FAIL]"
    print(f" {symbol} Database:      {db_msg}")
    if not db_ok:
        all_passed = False

    print("=" * 70)
    if all_passed:
        print(" [SUCCESS] All pre-flight diagnostics passed! HireMatch is ready to run.")
        print(" To launch the application:")
        print("   1. Start Backend API:  uvicorn backend.app.main:app --port 8000 --reload")
        print("   2. Start Next.js App:  cd frontend && npm run dev")
        print(" To execute the automated test suites:")
        print("   python run_tests.py --suite fast")
        print("=" * 70)
        return True
    else:
        print(" [WARNING] One or more pre-flight checks failed.")
        print(" Please resolve the missing dependencies or directory permissions above.")
        print("=" * 70)
        return False


if __name__ == "__main__":
    success = run_all_checks()
    sys.exit(0 if success else 1)
