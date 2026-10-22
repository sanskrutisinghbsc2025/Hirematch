
import os
import sys
import time
import signal
import socket
import platform
import subprocess
import urllib.request
import urllib.error
import webbrowser
import functools
from pathlib import Path

print = functools.partial(print, flush=True)

ROOT_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = ROOT_DIR / "frontend"

NODE_PATHS = [
    r"C:\Program Files\nodejs",
    r"C:\Program Files (x86)\nodejs",
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\node"),
    os.path.expandvars(r"%APPDATA%\npm"),
]
for p in NODE_PATHS:
    if os.path.exists(p) and p not in os.environ.get("PATH", ""):
        os.environ["PATH"] = p + os.pathsep + os.environ.get("PATH", "")

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")


def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def is_backend_healthy() -> bool:
    try:
        req = urllib.request.Request("http://127.0.0.1:8000/api/health", headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            return resp.status == 200
    except Exception:
        return False


def is_frontend_healthy() -> bool:
    for host in ("127.0.0.1", "localhost"):
        try:
            req = urllib.request.Request(
                f"http://{host}:3000",
                headers={"Accept": "text/html", "User-Agent": "HireMatch-HealthCheck"},
            )
            with urllib.request.urlopen(req, timeout=3.5) as resp:
                if resp.status in (200, 304, 307, 308):
                    return True
        except urllib.error.HTTPError as e:
            if e.code in (200, 304, 307, 308, 404):
                return True
        except Exception:
            pass
    return False


def free_port(port: int):
    if platform.system() == "Windows":
        killed_pids = set()
        try:
            cmd = f'powershell -Command "Get-NetTCPConnection -LocalPort {port} -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique"'
            out = subprocess.check_output(cmd, shell=True, text=True).strip()
            if out:
                for pid_str in out.splitlines():
                    pid_str = pid_str.strip()
                    if pid_str.isdigit() and int(pid_str) != os.getpid() and int(pid_str) not in killed_pids:
                        print(f" [INFO] Terminating stale process {pid_str} on port {port}...")
                        subprocess.run(["taskkill", "/F", "/T", "/PID", pid_str], capture_output=True)
                        killed_pids.add(int(pid_str))
        except Exception:
            pass

        try:
            cmd2 = f'cmd.exe /c "netstat -ano | findstr :{port}"'
            out2 = subprocess.check_output(cmd2, shell=True, text=True).strip()
            for line in out2.splitlines():
                parts = line.strip().split()
                if len(parts) >= 5 and "LISTENING" in line.upper():
                    pid_str = parts[-1]
                    if pid_str.isdigit() and int(pid_str) != os.getpid() and int(pid_str) not in killed_pids:
                        print(f" [INFO] Netstat cleanup: terminating PID {pid_str} on port {port}...")
                        subprocess.run(["taskkill", "/F", "/T", "/PID", pid_str], capture_output=True)
                        killed_pids.add(int(pid_str))
        except Exception:
            pass


def kill_proc_tree(proc: subprocess.Popen):
    if proc is None:
        return
    try:
        if platform.system() == "Windows":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
        else:
            proc.terminate()
    except Exception:
        pass


def print_banner():
    print("=" * 65)
    print("          HireMatch - AI Recruitment Platform")
    print("=" * 65)
    print(f" [Python]   {sys.version.split()[0]} ({sys.executable})")
    print(f" [Root]     {ROOT_DIR}")
    print("=" * 65)


def get_node_executable():
    import shutil
    node = shutil.which("node")
    if node:
        return node
    for p in [r"C:\Program Files\nodejs\node.exe", r"C:\Program Files (x86)\nodejs\node.exe"]:
        if os.path.exists(p):
            return p
    return "node"


def check_node():
    try:
        node_bin = get_node_executable()
        res = subprocess.run([node_bin, "-v"], capture_output=True, text=True)
        if res.returncode == 0:
            print(f" [PASS] Node.js Runtime: {res.stdout.strip()} ({node_bin})")
            return True
    except Exception:
        pass
    print(" [ERROR] Node.js not found in PATH or 'C:\\Program Files\\nodejs'.")
    print("         Please install Node.js from https://nodejs.org/")
    return False


def main():
    print_banner()

    if not check_node():
        sys.exit(1)

    backend_proc = None
    frontend_proc = None

    backend_already_active = False
    if is_port_in_use(8000):
        if is_backend_healthy():
            print(" [PASS] FastAPI Backend is already active and healthy on http://127.0.0.1:8000")
            backend_already_active = True
        else:
            print(" [INFO] Port 8000 in use by an unresponsive process. Resetting port...")
            free_port(8000)
            time.sleep(1)

    if not backend_already_active:
        if is_port_in_use(8000):
            free_port(8000)
            time.sleep(1)
        print("\n [1/2] Starting FastAPI Backend on http://127.0.0.1:8000 ...")
        backend_cmd = [
            sys.executable,
            "-m",
            "uvicorn",
            "backend.app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
        ]
        backend_proc = subprocess.Popen(
            backend_cmd,
            cwd=str(ROOT_DIR),
            env=os.environ.copy(),
        )
        for _ in range(20):
            if is_backend_healthy():
                break
            time.sleep(0.5)

    frontend_already_active = False
    if is_port_in_use(3000):
        if is_frontend_healthy():
            print(" [PASS] Next.js Frontend is already active on http://localhost:3000")
            frontend_already_active = True
        else:
            print(" [INFO] Port 3000 in use by an unresponsive process. Resetting port...")
            free_port(3000)
            time.sleep(1)

    if not frontend_already_active:
        if is_port_in_use(3000):
            free_port(3000)
            time.sleep(1)

        npm_cmd = "npm.cmd" if platform.system() == "Windows" else "npm"
        has_prod_build = (FRONTEND_DIR / ".next" / "BUILD_ID").is_file()

        if not has_prod_build:
            print("\n [INFO] No production build found. Building Next.js frontend (one-time, ~60s)...")
            print(" [INFO] Subsequent launches will start instantly.")
            build_result = subprocess.run(
                [npm_cmd, "run", "build"],
                cwd=str(FRONTEND_DIR),
                env=os.environ.copy(),
            )
            has_prod_build = (FRONTEND_DIR / ".next" / "BUILD_ID").is_file()
            if not has_prod_build:
                print(" [WARN] Build may have failed. Falling back to dev mode (will be slower).")

        mode = "start" if has_prod_build else "dev"
        print(f"\n [2/2] Starting Next.js Frontend ({mode} mode) on http://localhost:3000 ...")
        next_bin = FRONTEND_DIR / "node_modules" / "next" / "dist" / "bin" / "next"
        node_bin = get_node_executable()
        if next_bin.exists():
            frontend_cmd = [node_bin, str(next_bin), mode, "-p", "3000"]
        else:
            frontend_cmd = [npm_cmd, "run", mode]

        frontend_proc = subprocess.Popen(
            frontend_cmd,
            cwd=str(FRONTEND_DIR),
            env=os.environ.copy(),
            stdin=subprocess.DEVNULL,
        )

        for _ in range(40):
            if is_frontend_healthy():
                break
            time.sleep(0.5)

    print("\n" + "=" * 65)
    print("  HireMatch Platform is Live!")
    print("  - Frontend Web UI:       http://localhost:3000")
    print("  - Screening Requisition: http://localhost:3000/screenings/new")
    print("  - Backend API Docs:      http://127.0.0.1:8000/docs")
    print("  - Health Endpoint:       http://127.0.0.1:8000/api/health")
    print("=" * 65)
    print("  Press Ctrl+C to stop servers.\n")

    time.sleep(2)
    try:
        webbrowser.open("http://localhost:3000")
    except Exception:
        pass

    def cleanup(signum=None, frame=None):
        print("\n\n [Shutting down HireMatch services...]")
        if frontend_proc:
            kill_proc_tree(frontend_proc)
        if backend_proc:
            kill_proc_tree(backend_proc)
        print(" [HireMatch services stopped.]")
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    try:
        while True:
            if backend_proc and backend_proc.poll() is not None:
                if not is_port_in_use(8000) and not is_backend_healthy():
                    print(" [ERROR] Backend process exited unexpectedly.")
                    break
            if frontend_proc and frontend_proc.poll() is not None:
                if not is_port_in_use(3000) and not is_frontend_healthy():
                    print(" [ERROR] Frontend process exited unexpectedly.")
                    break
            time.sleep(2)
    except KeyboardInterrupt:
        cleanup()


if __name__ == "__main__":
    main()
