"""History ingestion package."""

from backend.app.history.acquire import (
    HistoryAcquisitionError,
    acquire_bare_history,
    validate_branch_name,
    validate_github_repo_input,
)
from backend.app.history.models import HistoryCoverage, HistoryOptions, HistoryResult
from backend.app.history.walker import walk_history
from backend.app.history.worker import HistoryWorkerError, run_history_worker

__all__ = [
    "HistoryAcquisitionError",
    "HistoryCoverage",
    "HistoryOptions",
    "HistoryResult",
    "HistoryWorkerError",
    "acquire_bare_history",
    "run_history_worker",
    "validate_branch_name",
    "validate_github_repo_input",
    "walk_history",
]
