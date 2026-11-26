"""
In-memory graph backend for offline development, CI tests, and audit-scoped graphs.

Provides isolated `GraphHandle` instances per audit (ADR-0001) as well as the
default demo seed graph for un-scoped exploration queries.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Tuple

import networkx as nx

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from database import seed_data  # noqa: E402

ALL_DEPENDENCY_REL_TYPES = set(seed_data.DEPENDENCY_TYPES) | {"IMPORTS"}
DEFAULT_GRAPH_CAP_BYTES = 5 * 1024 * 1024


@dataclass
class GraphHandle:
    """Isolated graph container bound to a single audit or the demo seed."""

    g: nx.MultiDiGraph
    is_custom: bool = False
    audit_id: Optional[str] = None
    truncated: bool = False


_DEMO_SEED_HANDLE: Optional[GraphHandle] = None
_UNSCOPED_CUSTOM_HANDLE: Optional[GraphHandle] = None


def _build_default_seed_graph() -> nx.MultiDiGraph:
    g = nx.MultiDiGraph()
    for node_id, label in seed_data.LABELS.items():
        props = dict(seed_data.ALL_PROPERTIES[node_id])
        props["id"] = node_id
        g.add_node(node_id, labels=label, **props)
    for src, rtype, dst in seed_data.RELATIONSHIPS:
        g.add_edge(src, dst, key=rtype, type=rtype)
    return g


def build_nx_graph(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> nx.MultiDiGraph:
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
    return g


def serialize_graph(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    cap_bytes: int = DEFAULT_GRAPH_CAP_BYTES,
) -> Tuple[str, bool, list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Serialize nodes/edges to JSON, pruning lowest-criticality nodes if payload exceeds cap_bytes.
    Returns (graph_json_str, truncated, kept_nodes, kept_edges).
    """
    payload_str = json.dumps({"nodes": nodes, "edges": edges}, separators=(",", ":"))
    if len(payload_str.encode("utf-8")) <= cap_bytes:
        return payload_str, False, nodes, edges

    # Compute reach/degree heuristic on full graph and retain top nodes iteratively
    g = build_nx_graph(nodes, edges)
    scores: dict[str, int] = {}
    for nid in g.nodes:
        scores[nid] = g.in_degree(nid) * 2 + g.out_degree(nid)
    ranked_ids = sorted(scores.keys(), key=lambda nid: (-scores[nid], nid))

    kept_count = max(1, int(len(ranked_ids) * 0.7))
    while kept_count >= 1:
        keep_set = set(ranked_ids[:kept_count])
        sub_nodes = [n for n in nodes if n["id"] in keep_set]
        sub_edges = [e for e in edges if e["source_id"] in keep_set and e["target_id"] in keep_set]
        candidate = json.dumps({"nodes": sub_nodes, "edges": sub_edges}, separators=(",", ":"))
        if len(candidate.encode("utf-8")) <= cap_bytes or kept_count == 1:
            return candidate, True, sub_nodes, sub_edges
        kept_count = max(1, int(kept_count * 0.7))

    empty_str = json.dumps({"nodes": [], "edges": []})
    return empty_str, True, [], []


def deserialize_graph(
    graph_json: str,
    audit_id: Optional[str] = None,
    truncated: bool = False,
) -> GraphHandle:
    data = json.loads(graph_json)
    g = build_nx_graph(data.get("nodes", []), data.get("edges", []))
    return GraphHandle(g=g, is_custom=True, audit_id=audit_id, truncated=truncated)


def _resolve_handle(graph: Optional[GraphHandle] = None) -> GraphHandle:
    global _DEMO_SEED_HANDLE
    if graph is not None:
        return graph
    if _UNSCOPED_CUSTOM_HANDLE is not None:
        return _UNSCOPED_CUSTOM_HANDLE
    if _DEMO_SEED_HANDLE is None:
        _DEMO_SEED_HANDLE = GraphHandle(g=_build_default_seed_graph(), is_custom=False)
    return _DEMO_SEED_HANDLE


def load_custom_graph(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> GraphHandle:
    """Load an assembled graph for unscoped direct unit calls."""
    global _UNSCOPED_CUSTOM_HANDLE
    handle = GraphHandle(g=build_nx_graph(nodes, edges), is_custom=True)
    _UNSCOPED_CUSTOM_HANDLE = handle
    return handle


def reset_to_demo() -> None:
    """Reset unscoped fallback graph back to the default synthetic seed dataset."""
    global _UNSCOPED_CUSTOM_HANDLE, _DEMO_SEED_HANDLE
    _UNSCOPED_CUSTOM_HANDLE = None
    _DEMO_SEED_HANDLE = GraphHandle(g=_build_default_seed_graph(), is_custom=False)


def _summary(g: nx.MultiDiGraph, node_id: str) -> dict:
    node = g.nodes[node_id]
    return {"id": node_id, "name": node.get("name", node_id), "type": node.get("labels")}


def _component(g: nx.MultiDiGraph, node_id: str) -> dict:
    """Node properties only — matches CognoDB's `n{.*}` serialization."""
    return {k: v for k, v in g.nodes[node_id].items() if k != "labels"}


def health(graph: Optional[GraphHandle] = None) -> dict:
    handle = _resolve_handle(graph)
    g = handle.g
    return {
        "status": "ok",
        "backend": "demo",
        "nodes": g.number_of_nodes(),
        "relationships": g.number_of_edges(),
        "is_custom": handle.is_custom,
    }


def stats(graph: Optional[GraphHandle] = None) -> dict:
    g = _resolve_handle(graph).g
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


def search(q: str = "", type_label: str = "", limit: int = 25, graph: Optional[GraphHandle] = None) -> list[dict]:
    g = _resolve_handle(graph).g
    out = []
    for node_id, data in g.nodes(data=True):
        if data.get("labels") == "Team":
            continue
        if type_label and data.get("labels") != type_label:
            continue
        name = data.get("name", "")
        if q and q.lower() not in name.lower():
            continue
        out.append({"component": _component(g, node_id), "type": data.get("labels")})
    out.sort(key=lambda r: r["component"].get("name", ""))
    return out[:limit]


def get_component(node_id: str, graph: Optional[GraphHandle] = None) -> dict | None:
    g = _resolve_handle(graph).g
    if node_id not in g:
        return None
    owner = None
    for _, dst, data in g.out_edges(node_id, data=True):
        if data.get("type") == "OWNED_BY":
            owner = g.nodes[dst].get("name")
    return {
        "component": _component(g, node_id),
        "type": g.nodes[node_id].get("labels"),
        "owner": owner,
    }


def direct_dependencies(node_id: str, graph: Optional[GraphHandle] = None) -> list[dict]:
    g = _resolve_handle(graph).g
    rows = []
    if node_id not in g:
        return rows
    for _, dst, data in g.out_edges(node_id, data=True):
        if data.get("type") == "OWNED_BY":
            continue
        rows.append({
            "rel": data.get("type"),
            "component": _component(g, dst),
            "type": g.nodes[dst].get("labels"),
        })
    rows.sort(key=lambda r: (r["rel"] or "", r["component"].get("name", "")))
    return rows


def direct_dependents(node_id: str, graph: Optional[GraphHandle] = None) -> list[dict]:
    g = _resolve_handle(graph).g
    rows = []
    if node_id not in g:
        return rows
    for src, _, data in g.in_edges(node_id, data=True):
        rows.append({
            "rel": data.get("type"),
            "component": _component(g, src),
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


def impact(node_id: str, graph: Optional[GraphHandle] = None) -> dict:
    """Equivalent Cypher: `IMPACT_ANALYSIS` (multi-hop, 1..6)."""
    g = _resolve_handle(graph).g
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
            "component": _component(g, other),
            "type": g.nodes[other].get("labels"),
            "depth": depth,
            "chain_nodes": [_summary(g, cid) for cid in chain_ids],
            "chain_rels": rels,
        })
    entries.sort(key=lambda e: (e["depth"], e["component"].get("name", "")))
    return {
        "root": {"component": _component(g, node_id), "type": g.nodes[node_id].get("labels")},
        "direct": [e for e in entries if e["depth"] == 1],
        "indirect": [e for e in entries if e["depth"] > 1],
        "total": len(entries),
        "max_depth": max((e["depth"] for e in entries), default=0),
    }


def shortest_path(from_id: str, to_id: str, max_paths: int = 6, graph: Optional[GraphHandle] = None) -> dict:
    """Equivalent Cypher: `DEPENDENCY_PATHS` (all chains <= 8 hops, shortest first)."""
    g = _resolve_handle(graph).g
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
            "nodes": [_summary(g, cid) for cid in chain_ids],
            "rels": rels,
            "hops": len(rels),
        })
    return {
        "found": bool(paths),
        "paths": paths,
        "hops": paths[0]["hops"] if paths else 0,
    }


def criticality_counts(node_id: str, graph: Optional[GraphHandle] = None) -> dict:
    """Equivalent Cypher: `CRITICALITY`."""
    g = _resolve_handle(graph).g
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


def leaderboard(limit: int = 10, graph: Optional[GraphHandle] = None) -> list[dict]:
    """Equivalent Cypher: `CRITICALITY_LEADERBOARD`."""
    g = _resolve_handle(graph).g
    simple = _dep_only_view(g)
    rows = []
    for node_id, data in g.nodes(data=True):
        if data.get("labels") == "Team":
            continue
        reach = len(nx.ancestors(simple, node_id))
        rows.append({
            "component": _component(g, node_id),
            "type": data.get("labels"),
            "reach": reach,
        })
    rows.sort(key=lambda r: (-r["reach"], r["component"].get("name", "")))
    return rows[:limit]


def ids(graph: Optional[GraphHandle] = None) -> set[str]:
    return set(_resolve_handle(graph).g.nodes)
