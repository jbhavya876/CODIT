"""Background job runner and retention reaper for CODIT audits."""

from __future__ import annotations

import logging
import shutil
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional

from sqlalchemy import delete, select, update

from backend.app.config import Config
from backend.app.db.engine import session_scope
from backend.app.db.models import AttestationRow, AuditRow
from backend.app.services import graph_service

log = logging.getLogger(__name__)

_EXECUTOR_LOCK = threading.Lock()
_EXECUTOR: Optional[ThreadPoolExecutor] = None
_REAPER_THREAD: Optional[threading.Thread] = None
_REAPER_STOP = threading.Event()


def get_executor() -> ThreadPoolExecutor:
    global _EXECUTOR
    with _EXECUTOR_LOCK:
        if _EXECUTOR is None:
            _EXECUTOR = ThreadPoolExecutor(max_workers=max(1, Config.JOB_WORKERS), thread_name_prefix="codit-audit")
        return _EXECUTOR


def submit_job(fn: Callable[..., None], *args, **kwargs) -> Future:
    return get_executor().submit(fn, *args, **kwargs)


def reap_stale_running_jobs(now: Optional[datetime] = None) -> int:
    """
    Mark running jobs that have exceeded SANDBOX_WALLTIME_SECONDS + 60 as failed(interrupted).
    """
    current = now or datetime.now(timezone.utc)
    cutoff = current - timedelta(seconds=Config.SANDBOX_WALLTIME_SECONDS + 60)
    count = 0
    with session_scope() as session:
        rows = session.execute(
            select(AuditRow).where(AuditRow.status == "running")
        ).scalars().all()
        for row in rows:
            ref_ts = row.started_at or row.created_at
            if ref_ts.tzinfo is None:
                ref_ts = ref_ts.replace(tzinfo=timezone.utc)
            if ref_ts <= cutoff:
                row.status = "failed"
                row.error_code = "interrupted"
                count += 1
    if count:
        log.warning("Reaped %d stale running audit jobs to failed(interrupted)", count)
    return count


def _remove_staging_dir(audit_id: str) -> None:
    staging_path = Path(Config.STAGING_DIR) / audit_id
    if staging_path.exists():
        shutil.rmtree(staging_path, ignore_errors=True)


def reap_expired_audits(now: Optional[datetime] = None) -> int:
    """
    Idempotently delete audits past expires_at, orphaned expired staging dirs,
    and expired attestations past expires_at + ATTESTATION_RETENTION_DAYS.
    """
    current = now or datetime.now(timezone.utc)
    staging_cutoff = current - timedelta(minutes=Config.STAGING_TTL_MINUTES)
    deleted_audits = 0

    with session_scope() as session:
        expired_rows = session.execute(
            select(AuditRow).where(AuditRow.expires_at <= current)
        ).scalars().all()
        expired_ids = [r.id for r in expired_rows]

        # Also clean staging dirs past STAGING_TTL_MINUTES even if audit row hasn't expired
        staged_rows = session.execute(
            select(AuditRow).where(AuditRow.staged_at.is_not(None))
        ).scalars().all()
        for sr in staged_rows:
            ts = sr.staged_at
            if ts is not None:
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if ts <= staging_cutoff:
                    _remove_staging_dir(sr.id)
                    sr.staged_at = None

        if expired_ids:
            # Explicitly null FK references before deletion so multi-worker runs stay safe
            session.execute(
                update(AttestationRow)
                .where(AttestationRow.audit_id.in_(expired_ids))
                .values(audit_id=None)
            )
            res = session.execute(
                delete(AuditRow).where(AuditRow.id.in_(expired_ids))
            )
            deleted_audits = res.rowcount or 0
            for aid in expired_ids:
                _remove_staging_dir(aid)
                graph_service.cache_evict_graph(aid)

        # Clean attestations past retention window
        att_cutoff = current - timedelta(days=Config.ATTESTATION_RETENTION_DAYS)
        session.execute(
            delete(AttestationRow).where(AttestationRow.expires_at <= att_cutoff)
        )

    # Sweep orphaned subdirectories in STAGING_DIR not tracked by active rows
    staging_root = Path(Config.STAGING_DIR)
    if staging_root.exists():
        cutoff_epoch = time.time() - (Config.STAGING_TTL_MINUTES * 60)
        for child in staging_root.iterdir():
            if child.is_dir():
                try:
                    if child.stat().st_mtime <= cutoff_epoch:
                        shutil.rmtree(child, ignore_errors=True)
                except OSError:
                    pass

    return deleted_audits


def _reaper_worker(interval_seconds: int = 600) -> None:
    while not _REAPER_STOP.wait(interval_seconds):
        try:
            reap_stale_running_jobs()
            reap_expired_audits()
        except Exception as exc:
            log.exception("Retention reaper tick failed: %s", exc)


def start_reaper(interval_seconds: int = 600) -> None:
    global _REAPER_THREAD
    _REAPER_STOP.clear()
    try:
        reap_stale_running_jobs()
        reap_expired_audits()
    except Exception as exc:
        log.warning("Initial startup reaper run failed: %s", exc)

    if _REAPER_THREAD is None or not _REAPER_THREAD.is_alive():
        _REAPER_THREAD = threading.Thread(
            target=_reaper_worker,
            args=(interval_seconds,),
            daemon=True,
            name="codit-reaper",
        )
        _REAPER_THREAD.start()


def stop_reaper() -> None:
    _REAPER_STOP.set()
