"""Content-addressed SQLAlchemy + LRU cache for blob test/CI metrics."""

from __future__ import annotations

import threading
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from sqlalchemy import delete

from backend.app.db.engine import session_scope
from backend.app.db.models import BlobMetricRow

_LRU_LOCK = threading.Lock()
_LRU_MAX = 2048
_LRU: OrderedDict[tuple[str, str], Dict[str, Any]] = OrderedDict()


def get_cached_blob_metrics(blob_sha: str, analyzer_version: str) -> Optional[Dict[str, Any]]:
    key = (blob_sha, analyzer_version)
    with _LRU_LOCK:
        hit = _LRU.get(key)
        if hit is not None:
            _LRU.move_to_end(key)
            return hit

    try:
        with session_scope() as session:
            row = session.get(BlobMetricRow, {"blob_sha": blob_sha, "analyzer_version": analyzer_version})
            if row is not None:
                data = dict(row.metrics_json)
                with _LRU_LOCK:
                    _LRU[key] = data
                    _LRU.move_to_end(key)
                    while len(_LRU) > _LRU_MAX:
                        _LRU.popitem(last=False)
                return data
    except Exception:
        return None
    return None


def put_cached_blob_metrics(blob_sha: str, analyzer_version: str, metrics: Dict[str, Any]) -> None:
    key = (blob_sha, analyzer_version)
    with _LRU_LOCK:
        _LRU[key] = metrics
        _LRU.move_to_end(key)
        while len(_LRU) > _LRU_MAX:
            _LRU.popitem(last=False)

    try:
        with session_scope() as session:
            existing = session.get(BlobMetricRow, {"blob_sha": blob_sha, "analyzer_version": analyzer_version})
            if existing is None:
                session.add(
                    BlobMetricRow(
                        blob_sha=blob_sha,
                        analyzer_version=analyzer_version,
                        metrics_json=metrics,
                        created_at=datetime.now(timezone.utc),
                    )
                )
    except Exception:
        pass


def purge_old_blob_metrics(max_age_days: int = 30) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    with session_scope() as session:
        res = session.execute(delete(BlobMetricRow).where(BlobMetricRow.created_at <= cutoff))
        return res.rowcount or 0
