"""
In-memory graph backend for offline development, CI tests, and active audit scans.

Implements the exact same query functions as ``cognodb_graph.py`` (same signatures,
same response shapes), so the rest of the application — routes, frontend, tests —
cannot tell the difference.

Supports loading dynamically ingested repository graphs as well as defaulting
to the canonical seed dataset from ``database.seed_data``.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import networkx as nx

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from database import seed_data  # noqa: E402

_G: nx.MultiDiGraph | None = None
_IS_CUSTOM_GRAPH = False

ALL_DEPENDENCY_REL_TYPES = set(seed_data.DEPENDENCY_TYPES) | {"IMPORTS"}


def _build_default_seed_graph() -> nx.MultiDiGraph:
    g = nx.MultiDiGraph()
    for node_id, label in seed_data.LABELS.items():
        props = dict(seed_data.ALL_PROPERTIES[node_id])
        props["id"] = node_id
        g.add_node(node_id, labels=label, **props)
    for src, rtype, dst in seed_data.RELATIONSHIPS:
        g.add_edge(src, dst, key=rtype, type=rtype)
    return g


def _graph() -> nx.MultiDiGraph:
    global _G
    if _G is None:
        _G = _build_default_seed_graph()
    return _G


def load_custom_graph(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> None:
    """Load an assembled graph from a real codebase ingestion."""
    global _G, _IS_CUSTOM_GRAPH
    g = nx.MultiDiGraph()
    for n in nodes:
        node_id = n["id"]
        label = n.get("type") or n.get("labels") or "Module"
        props = {k: v for k, v in n.items() if k not in ("labels", "type")}
        props["id"] = node_id
        props.setdefault("name", n.get("name") or node_id)
        g.add_node(node_id, labels=label, **props)

    for e in edges:
        src = e["source_id"]
        dst = e["target_id"]
        rtype = e.get("rel_type", "DEPENDS_ON")
        if src in g and dst in g:
            g.add_edge(src, dst, key=rtype, type=rtype)

    _G = g
    _IS_CUSTOM_GRAPH = True


def reset_to_demo() -> None:
    """Reset graph back to the default synthetic seed dataset."""
    global _G, _IS_CUSTOM_GRAPH
    _G = _build_default_seed_graph()
    _IS_CUSTOM_GRAPH = False


def _summary(node_id: str) -> dict:
    node = _graph().nodes[node_id]
    return {"id": node_id, "name": node.get("name", node_id), "type": node.get("labels")}


def _component(node_id: str) -> dict:
    """Node properties only — matches CognoDB's ``n{.*}`` serialization."""
    return {k: v for k, v in _graph().nodes[node_id].items() if k != "labels"}


def health() -> dict:
    g = _graph()
    return {
        "status": "ok",
        "backend": "demo",
        "nodes": g.number_of_nodes(),
        "relationships": g.number_of_edges(),
        "is_custom": _IS_CUSTOM_GRAPH,
    }


def stats() -> dict:
    g = _graph()
    nodes: dict[str, int] = {}
    for _, data in g.nodes(data=True):
        label = data.get("labels", "Unknown")
        nodes[label] = nodes.get(label, 0) + 1
    rels: dict[str, int] = {}
    for _, _, data in g.edges(data=True):
        t = data.get("type", "UNKNOWN")
        rels[t] = rels.get(t, 0) + 1
    return {
        "nodes": dict(sorted(nodes.items(), key=lambda kv: -kv[1])),
        "relationships": dict(sorted(rels.items(), key=lambda kv: -kv[1])),
        "teams": nodes.get("Team", 0),
    }


def search(q: str = "", type_label: str = "", limit: int = 25) -> list[dict]:
    g = _graph()
    out = []
    for node_id, data in g.nodes(data=True):
        if data.get("labels") == "Team":
            continue
        if type_label and data.get("labels") != type_label:
            continue
        name = data.get("name", "")
        if q and q.lower() not in name.lower():
            continue
        out.append({"component": _component(node_id), "type": data.get("labels")})
    out.sort(key=lambda r: r["component"].get("name", ""))
    return out[:limit]


def get_component(node_id: str) -> dict | None:
    g = _graph()
    if node_id not in g:
        return None
    owner = None
    for _, dst, data in g.out_edges(node_id, data=True):
        if data.get("type") == "OWNED_BY":
            owner = g.nodes[dst].get("name")
    return {
        "component": _component(node_id),
        "type": g.nodes[node_id].get("labels"),
        "owner": owner,
    }


def direct_dependencies(node_id: str) -> list[dict]:
    g = _graph()
    rows = []
    if node_id not in g:
        return rows
    for _, dst, data in g.out_edges(node_id, data=True):
        if data.get("type") == "OWNED_BY":
            continue
        rows.append({
            "rel": data.get("type"),
            "component": _component(dst),
            "type": g.nodes[dst].get("labels"),
        })
    rows.sort(key=lambda r: (r["rel"] or "", r["component"].get("name", "")))
    return rows


def direct_dependents(node_id: str) -> list[dict]:
    g = _graph()
    rows = []
    if node_id not in g:
        return rows
    for src, _, data in g.in_edges(node_id, data=True):
        rows.append({
            "rel": data.get("type"),
            "component": _component(src),
            "type": g.nodes[src].get("labels"),
        })
    rows.sort(key=lambda r: r["component"].get("name", ""))
    return rows


def _dep_only_view(g: nx.MultiDiGraph) -> nx.DiGraph:
    """Dependency-only simple digraph (drops OWNED_BY and parallel edges)."""
    keep = [
        (u, v)
        for u, v, d in g.edges(data=True)
        if d.get("type") in ALL_DEPENDENCY_REL_TYPES
    ]
    view = nx.DiGraph()
    view.add_nodes_from(g.nodes)
    view.add_edges_from(keep)
    return view


def impact(node_id: str) -> dict:
    """Equivalent Cypher: ``IMPACT_ANALYSIS`` (multi-hop, 1..6)."""
    g = _graph()
    if node_id not in g:
        return {"root": None, "direct": [], "indirect": [], "total": 0, "max_depth": 0}

    simple = _dep_only_view(g)
    affected_nodes = nx.ancestors(simple, node_id)
    entries = []
    for other in affected_nodes:
        try:
            chain_ids = nx.shortest_path(simple, other, node_id)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            continue
        depth = len(chain_ids) - 1
        if depth > 6:
            continue
        rels = []
        for u, v in zip(chain_ids, chain_ids[1:]):
            edge_data = g.get_edge_data(u, v) or {}
            types = sorted(
                d["type"]
                for d in edge_data.values()
                if d.get("type") in ALL_DEPENDENCY_REL_TYPES
            )
            rels.append(types[0] if types else "DEPENDS_ON")
        entries.append({
            "component": _component(other),
            "type": g.nodes[other].get("labels"),
            "depth": depth,
            "chain_nodes": [_summary(cid) for cid in chain_ids],
            "chain_rels": rels,
        })
    entries.sort(key=lambda e: (e["depth"], e["component"].get("name", "")))
    return {
        "root": {"component": _component(node_id), "type": g.nodes[node_id].get("labels")},
        "direct": [e for e in entries if e["depth"] == 1],
        "indirect": [e for e in entries if e["depth"] > 1],
        "total": len(entries),
        "max_depth": max((e["depth"] for e in entries), default=0),
    }


def shortest_path(from_id: str, to_id: str, max_paths: int = 6) -> dict:
    """Equivalent Cypher: ``DEPENDENCY_PATHS`` (all chains <= 8 hops, shortest first)."""
    g = _graph()
    simple = _dep_only_view(g)
    try:
        chains = sorted(nx.all_simple_paths(simple, from_id, to_id, cutoff=8), key=len)
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        chains = []
    paths = []
    for chain_ids in chains[:max_paths]:
        rels = []
        for u, v in zip(chain_ids, chain_ids[1:]):
            edge_data = g.get_edge_data(u, v) or {}
            types = sorted(
                d["type"]
                for d in edge_data.values()
                if d.get("type") in ALL_DEPENDENCY_REL_TYPES
            )
            rels.append(types[0] if types else "DEPENDS_ON")
        paths.append({
            "nodes": [_summary(cid) for cid in chain_ids],
            "rels": rels,
            "hops": len(rels),
        })
    return {
        "found": bool(paths),
        "paths": paths,
        "hops": paths[0]["hops"] if paths else 0,
    }


def criticality_counts(node_id: str) -> dict:
    """Equivalent Cypher: ``CRITICALITY``."""
    g = _graph()
    if node_id not in g:
        return {"direct": 0, "indirect": 0}
    simple = _dep_only_view(g)
    direct = sum(
        1 for u in simple.predecessors(node_id)
        if g.nodes[u].get("labels") != "Team"
    )
    indirect = 0
    for other in nx.ancestors(simple, node_id):
        if other == node_id:
            continue
        try:
            if nx.shortest_path_length(simple, other, node_id) >= 2:
                indirect += 1
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            pass
    return {"direct": direct, "indirect": indirect}


def leaderboard(limit: int = 10) -> list[dict]:
    """Equivalent Cypher: ``CRITICALITY_LEADERBOARD``."""
    g = _graph()
    simple = _dep_only_view(g)
    rows = []
    for node_id, data in g.nodes(data=True):
        if data.get("labels") == "Team":
            continue
        reach = len(nx.ancestors(simple, node_id))
        rows.append({
            "component": _component(node_id),
            "type": data.get("labels"),
            "reach": reach,
        })
    rows.sort(key=lambda r: (-r["reach"], r["component"].get("name", "")))
    return rows[:limit]


def ids() -> set[str]:
    return set(_graph().nodes)
