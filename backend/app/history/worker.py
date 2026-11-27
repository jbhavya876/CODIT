"""
Resource-capped child process worker for reading untrusted `.git` history (ADR-0002).

Invocation:
    python -m backend.app.history.worker <job.json>

Security properties:
- Zero HTTP client imports inside worker.
- Linux resource caps (RLIMIT_CPU, RLIMIT_AS, RLIMIT_NOFILE); skips with warning on non-Linux dev.
- JSON-only IPC validated by Pydantic (never pickle); result capped at 25 MB, stdout at 1 MB.
"""

from __future__ import annotations

import json
import logging
import os
import platform
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

from backend.app.config import Config
from backend.app.history.models import HistoryCoverage, HistoryOptions, HistoryResult
from backend.app.history.walker import walk_history

log = logging.getLogger(__name__)

MAX_RESULT_BYTES = 25 * 1024 * 1024
MAX_STDOUT_BYTES = 1 * 1024 * 1024


class HistoryWorkerError(RuntimeError):
    """Raised when child history worker fails or exceeds bounds."""


def _apply_posix_rlimits(walltime_seconds: int, mem_mb: int) -> None:
    if platform.system().lower() != "linux":
        log.warning("Non-Linux host (%s): skipping POSIX setrlimit; production must be Linux.", platform.system())
        return
    import resource

    mem_bytes = mem_mb * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_CPU, (walltime_seconds, walltime_seconds))
    resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
    resource.setrlimit(resource.RLIMIT_NOFILE, (256, 256))


def _worker_main(job_path: Path) -> int:
    job = json.loads(job_path.read_text(encoding="utf-8"))
    wall = int(job.get("walltime_seconds", Config.HISTORY_WALLTIME_SECONDS))
    mem_mb = int(job.get("mem_mb", Config.HISTORY_MEM_MB))
    _apply_posix_rlimits(wall, mem_mb)

    repo_path = Path(job["repo_path"])
    out_path = Path(job["result_path"])
    options = HistoryOptions.model_validate(job.get("options") or {})
    test_globs = job.get("test_globs")

    result = walk_history(repo_path, options=options, test_globs=test_globs)
    serialized = result.model_dump_json()
    encoded = serialized.encode("utf-8")
    if len(encoded) > MAX_RESULT_BYTES:
        # Shrink file delta list cleanly to stay within 25 MB IPC budget
        for commit in result.commits:
            commit.files = []
        serialized = result.model_dump_json()
        encoded = serialized.encode("utf-8")
        if len(encoded) > MAX_RESULT_BYTES:
            raise HistoryWorkerError("History result exceeded 25 MB cap.")

    out_path.write_bytes(encoded)
    print(json.dumps({"status": "ok", "commits": result.coverage.commits_analyzed}), flush=True)
    return 0


def run_history_worker(
    repo_path: Path,
    options: Optional[HistoryOptions] = None,
    *,
    test_globs: Optional[list[str]] = None,
    walltime_seconds: Optional[int] = None,
    mem_mb: Optional[int] = None,
) -> HistoryResult:
    """Spawn resource-limited child process to inspect `repo_path` via dulwich."""
    wall = walltime_seconds or Config.HISTORY_WALLTIME_SECONDS
    mem = mem_mb or Config.HISTORY_MEM_MB
    opts = options or HistoryOptions()

    with tempfile.TemporaryDirectory(prefix="codit_hist_ipc_") as ipc_dir_str:
        ipc_dir = Path(ipc_dir_str)
        job_file = ipc_dir / "job.json"
        result_file = ipc_dir / "result.json"

        job_file.write_text(
            json.dumps({
                "repo_path": str(repo_path),
                "result_path": str(result_file),
                "options": opts.model_dump(),
                "test_globs": test_globs,
                "walltime_seconds": wall,
                "mem_mb": mem,
            }),
            encoding="utf-8",
        )

        popen_kwargs: dict = {
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "env": {**os.environ, "CODIT_WORKER_CHILD": "1"},
        }
        if os.name == "nt":
            popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            popen_kwargs["start_new_session"] = True

        proc = subprocess.Popen(
            [sys.executable, "-m", "backend.app.history.worker", str(job_file)],
            **popen_kwargs,
        )

        try:
            stdout_b, stderr_b = proc.communicate(timeout=wall)
        except subprocess.TimeoutExpired as exc:
            _kill_process_tree(proc)
            proc.wait(timeout=5)
            return HistoryResult(
                coverage=HistoryCoverage(assessed=False, reason="history_timeout", caps_hit=["walltime"])
            )

        if len(stdout_b) > MAX_STDOUT_BYTES:
            raise HistoryWorkerError("Worker stdout exceeded 1 MB cap.")

        if proc.returncode != 0:
            err = stderr_b.decode("utf-8", errors="replace").strip()
            raise HistoryWorkerError(f"History worker failed (exit {proc.returncode}): {err}")

        if not result_file.exists():
            raise HistoryWorkerError("History worker exited without producing result.json.")

        if result_file.stat().st_size > MAX_RESULT_BYTES:
            raise HistoryWorkerError("History worker result.json exceeded 25 MB cap.")

        return HistoryResult.model_validate_json(result_file.read_bytes())


def _kill_process_tree(proc: subprocess.Popen) -> None:
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            import signal
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except Exception:
        proc.kill()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(2)
    sys.exit(_worker_main(Path(sys.argv[1])))
