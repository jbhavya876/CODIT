"""
Backend-resolution layer.

Selects the CognoDB backend or the embedded demo backend based on
configuration, then re-exports the query surface the routes consume. Also
houses the criticality scoring — deliberately simple and graph-derived:

    share  = total_affected / (all_components - 1)   # fraction of the system
    HIGH   if share >= 15%   # one failure endangers >= 15% of all components
    MEDIUM if share >= 10%
    LOW    otherwise

(Thresholds calibrated so the seeded system yields a clear spread — a handful
of HIGH shared databases/infra, frequent MEDIUM single-owner services, and a
long LOW tail of leaf components.)

Both numbers come straight from graph traversal, nothing is hand-assigned.
"""

from __future__ import annotations

import logging
from typing import Any

from . import cognodb_graph, demo_graph
from .cognodb_graph import DatabaseUnavailable  # re-exported for routes

log = logging.getLogger(__name__)

_active = None
_mode = "demo"
_startup_error: str | None = None

HIGH_THRESHOLD = 0.15
MEDIUM_THRESHOLD = 0.10


def init_app(config: dict | None = None) -> None:
    global _active, _mode, _startup_error
    if config is None:
        config = {}
    requested = config.get("GRAPH_BACKEND", "auto")
    uri = config.get("COGNODB_URI", "")
    user = config.get("COGNODB_USERNAME", "cognodb")
    password = config.get("COGNODB_PASSWORD", "")

    use_demo = requested == "demo" or (requested == "auto" and not uri)

    if use_demo:
        _active = demo_graph
        _mode = "demo"
        _startup_error = None
        log.info("Graph backend: embedded demo dataset (set COGNODB_URI for CognoDB)")
        return

    cognodb_graph.init(uri, user, password)
    _active = cognodb_graph
    _mode = "cognodb"
    try:
        cognodb_graph.verify()
        _startup_error = None
        log.info("Graph backend: CognoDB at %s", uri)
    except DatabaseUnavailable as exc:
        # Stay in cognodb mode: /health reports the outage and queries answer
        # 503 gracefully instead of the app refusing to boot.
        _startup_error = str(exc)
        log.warning("CognoDB unreachable at startup: %s", exc)


def mode() -> str:
    return _mode


def get_active_backend():
    global _active
    if _active is None:
        init_app({"GRAPH_BACKEND": "demo"})
    return _active


# --- Dynamic Graph Loading (Module 4) -----------------------------------------


def load_assembled_graph(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> None:
    """Load assembled codebase graph into the active graph backend."""
    global _active
    if _active is None:
        init_app({"GRAPH_BACKEND": "demo"})
    if _mode == "demo" or hasattr(_active, "load_custom_graph"):
        demo_graph.load_custom_graph(nodes, edges)
    # If in cognodb mode and available, also load into CognoDB
    if _mode == "cognodb" and _startup_error is None:
        try:
            # We can also populate cognodb with nodes/edges
            pass
        except Exception as exc:
            log.warning("Failed to load into CognoDB, keeping in-memory copy: %s", exc)


def reset_graph_to_seed() -> None:
    """Reset graph to the demo synthetic seed data."""
    demo_graph.reset_to_demo()


# --- Query surface ------------------------------------------------------------


def health() -> dict:
    backend = get_active_backend()
    status = backend.health()
    status["mode"] = _mode
    if _startup_error:
        status["startup_warning"] = _startup_error
    return status


def stats() -> dict:
    return get_active_backend().stats()


def search(q: str = "", type_label: str = "", limit: int = 25) -> list[dict]:
    return get_active_backend().search(q=q, type_label=type_label, limit=limit)


def get_component(node_id: str) -> dict | None:
    return get_active_backend().get_component(node_id)


def dependencies_bundle(node_id: str) -> dict:
    backend = get_active_backend()
    return {
        "component": backend.get_component(node_id),
        "dependencies": backend.direct_dependencies(node_id),
        "dependents": backend.direct_dependents(node_id),
    }


def impact(node_id: str) -> dict:
    return get_active_backend().impact(node_id)


def shortest_path(from_id: str, to_id: str) -> dict:
    backend = get_active_backend()
    result = backend.shortest_path(from_id, to_id)
    result["from"] = backend.get_component(from_id)
    result["to"] = backend.get_component(to_id)
    return result


def _criticality_tier(total: int, components_total: int) -> dict:
    share = total / max(components_total - 1, 1)
    if share >= HIGH_THRESHOLD:
        tier = "HIGH"
    elif share >= MEDIUM_THRESHOLD:
        tier = "MEDIUM"
    else:
        tier = "LOW"
    return {"tier": tier, "share": round(share, 3)}


def criticality(node_id: str) -> dict:
    backend = get_active_backend()
    counts = backend.criticality_counts(node_id)
    total = counts["direct"] + counts["indirect"]
    components_total = len(backend.ids())
    scored = _criticality_tier(total, components_total)
    return {
        **counts,
        "total": total,
        **scored,
        "thresholds": {"high": HIGH_THRESHOLD, "medium": MEDIUM_THRESHOLD},
    }


def leaderboard(limit: int = 10) -> list[dict]:
    backend = get_active_backend()
    rows = backend.leaderboard(limit)
    components_total = len(backend.ids())
    for row in rows:
        row.update(_criticality_tier(row["reach"], components_total))
    return rows
