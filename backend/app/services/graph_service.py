"""
Backend-resolution layer with per-audit GraphHandle isolation and bounded LRU caching.

Each audit owns an isolated NetworkX GraphHandle reconstructed from persisted
`graph_json` (ADR-0001). Un-scoped exploration routes fall back to the demo seed
dataset unless an audit graph handle is explicitly passed.
"""

from __future__ import annotations

import logging
import threading
from collections import OrderedDict
from typing import Any, Optional

from backend.app.config import Config
from backend.app.services import cognodb_graph, demo_graph
from backend.app.services.cognodb_graph import DatabaseUnavailable  # re-exported for routes
from backend.app.services.demo_graph import GraphHandle, deserialize_graph, serialize_graph

log = logging.getLogger(__name__)

_backend_driver = None
_backend_mode = "demo"
_startup_error: str | None = None

HIGH_THRESHOLD = 0.15
MEDIUM_THRESHOLD = 0.10

_GRAPH_CACHE_MAX = 16
_GRAPH_CACHE_LOCK = threading.Lock()
_GRAPH_CACHE: OrderedDict[str, GraphHandle] = OrderedDict()


def init_app(config: dict | None = None) -> None:
    global _backend_driver, _backend_mode, _startup_error
    if config is None:
        config = {}
    requested = config.get("GRAPH_BACKEND", "auto")
    uri = config.get("COGNODB_URI", "")
    user = config.get("COGNODB_USERNAME", "cognodb")
    password = config.get("COGNODB_PASSWORD", "")

    use_demo = (
        Config.ENV == "production"
        or requested == "demo"
        or (requested == "auto" and not uri)
    )

    if use_demo:
        _backend_driver = demo_graph
        _backend_mode = "demo"
        _startup_error = None
        log.info("Graph backend: isolated NetworkX / embedded demo dataset")
        return

    cognodb_graph.init(uri, user, password)
    _backend_driver = cognodb_graph
    _backend_mode = "cognodb"
    try:
        cognodb_graph.verify()
        _startup_error = None
        log.info("Graph backend: CognoDB at %s", uri)
    except DatabaseUnavailable as exc:
        _startup_error = str(exc)
        log.warning("CognoDB unreachable at startup: %s", exc)


def mode() -> str:
    return _backend_mode


def get_backend_driver():
    global _backend_driver
    if _backend_driver is None:
        init_app({"GRAPH_BACKEND": "demo"})
    return _backend_driver


def cache_put_graph(audit_id: str, handle: GraphHandle) -> None:
    with _GRAPH_CACHE_LOCK:
        _GRAPH_CACHE[audit_id] = handle
        _GRAPH_CACHE.move_to_end(audit_id)
        while len(_GRAPH_CACHE) > _GRAPH_CACHE_MAX:
            _GRAPH_CACHE.popitem(last=False)


def cache_get_graph(audit_id: str) -> Optional[GraphHandle]:
    with _GRAPH_CACHE_LOCK:
        handle = _GRAPH_CACHE.get(audit_id)
        if handle is not None:
            _GRAPH_CACHE.move_to_end(audit_id)
        return handle


def cache_evict_graph(audit_id: str) -> None:
    with _GRAPH_CACHE_LOCK:
        _GRAPH_CACHE.pop(audit_id, None)


def build_handle_from_json(audit_id: str, graph_json: str, truncated: bool = False) -> GraphHandle:
    cached = cache_get_graph(audit_id)
    if cached is not None:
        return cached
    handle = deserialize_graph(graph_json, audit_id=audit_id, truncated=truncated)
    cache_put_graph(audit_id, handle)
    return handle


def load_assembled_graph(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    audit_id: Optional[str] = None,
) -> GraphHandle:
    """
    Build an isolated GraphHandle. When audit_id is omitted (legacy unit calls),
    updates the unscoped fallback handle without touching any persisted audit.
    """
    if audit_id is not None:
        graph_json, truncated, _kept_nodes, _kept_edges = serialize_graph(nodes, edges)
        handle = deserialize_graph(graph_json, audit_id=audit_id, truncated=truncated)
        cache_put_graph(audit_id, handle)
        return handle

    return demo_graph.load_custom_graph(nodes, edges)


def reset_graph_to_seed() -> None:
    """Reset unscoped fallback graph to the demo synthetic seed data."""
    demo_graph.reset_to_demo()


def _use_cognodb(graph: Optional[GraphHandle]) -> bool:
    return graph is None and _backend_mode == "cognodb" and cognodb_graph is get_backend_driver()


# --- Query surface (GraphHandle-threaded) -------------------------------------


def health(graph: Optional[GraphHandle] = None) -> dict:
    if _use_cognodb(graph):
        status = cognodb_graph.health()
    else:
        status = demo_graph.health(graph=graph)
    status["mode"] = _backend_mode if graph is None else "audit"
    if _startup_error and graph is None:
        status["startup_warning"] = _startup_error
    return status


def stats(graph: Optional[GraphHandle] = None) -> dict:
    if _use_cognodb(graph):
        return cognodb_graph.stats()
    return demo_graph.stats(graph=graph)


def search(q: str = "", type_label: str = "", limit: int = 25, graph: Optional[GraphHandle] = None) -> list[dict]:
    if _use_cognodb(graph):
        return cognodb_graph.search(q=q, type_label=type_label, limit=limit)
    return demo_graph.search(q=q, type_label=type_label, limit=limit, graph=graph)


def get_component(node_id: str, graph: Optional[GraphHandle] = None) -> dict | None:
    if _use_cognodb(graph):
        return cognodb_graph.get_component(node_id)
    return demo_graph.get_component(node_id, graph=graph)


def dependencies_bundle(node_id: str, graph: Optional[GraphHandle] = None) -> dict:
    if _use_cognodb(graph):
        return {
            "component": cognodb_graph.get_component(node_id),
            "dependencies": cognodb_graph.direct_dependencies(node_id),
            "dependents": cognodb_graph.direct_dependents(node_id),
        }
    return {
        "component": demo_graph.get_component(node_id, graph=graph),
        "dependencies": demo_graph.direct_dependencies(node_id, graph=graph),
        "dependents": demo_graph.direct_dependents(node_id, graph=graph),
    }


def impact(node_id: str, graph: Optional[GraphHandle] = None) -> dict:
    if _use_cognodb(graph):
        return cognodb_graph.impact(node_id)
    return demo_graph.impact(node_id, graph=graph)


def shortest_path(from_id: str, to_id: str, graph: Optional[GraphHandle] = None) -> dict:
    if _use_cognodb(graph):
        result = cognodb_graph.shortest_path(from_id, to_id)
        result["from"] = cognodb_graph.get_component(from_id)
        result["to"] = cognodb_graph.get_component(to_id)
        return result
    result = demo_graph.shortest_path(from_id, to_id, graph=graph)
    result["from"] = demo_graph.get_component(from_id, graph=graph)
    result["to"] = demo_graph.get_component(to_id, graph=graph)
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


def criticality(node_id: str, graph: Optional[GraphHandle] = None) -> dict:
    if _use_cognodb(graph):
        counts = cognodb_graph.criticality_counts(node_id)
        components_total = len(cognodb_graph.ids())
    else:
        counts = demo_graph.criticality_counts(node_id, graph=graph)
        components_total = len(demo_graph.ids(graph=graph))
    total = counts["direct"] + counts["indirect"]
    scored = _criticality_tier(total, components_total)
    return {
        **counts,
        "total": total,
        **scored,
        "thresholds": {"high": HIGH_THRESHOLD, "medium": MEDIUM_THRESHOLD},
    }


def leaderboard(limit: int = 10, graph: Optional[GraphHandle] = None) -> list[dict]:
    if _use_cognodb(graph):
        rows = cognodb_graph.leaderboard(limit)
        components_total = len(cognodb_graph.ids())
    else:
        rows = demo_graph.leaderboard(limit, graph=graph)
        components_total = len(demo_graph.ids(graph=graph))
    for row in rows:
        row.update(_criticality_tier(row["reach"], components_total))
    return rows
