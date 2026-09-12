"""
Mermaid.js Diagram Generator for Architecture Overviews and Blast-Radius Impact Trees.

Reuses real graph traversal data from Module 4 and services/graph_service.py.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


def _sanitize_id(node_id: str) -> str:
    """Sanitizes node IDs to be safe identifiers in Mermaid.js syntax."""
    return re.sub(r"[^a-zA-Z0-9_]", "_", node_id)


def generate_architecture_diagram(
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
    max_nodes: int = 40,
) -> str:
    """
    Generates a Mermaid.js flowchart representing the repository's real architecture.
    Groups nodes into subgraphs (Modules, Databases, Libraries, Infrastructure).
    """
    lines = [
        "%%{init: {'theme': 'dark', 'themeVariables': { 'darkMode': true }}}%%",
        "flowchart TD",
    ]

    modules = []
    databases = []
    libraries = []
    infra = []

    # Sort nodes by importance (modules with most connections, then others)
    for n in nodes[:max_nodes]:
        lbl = n.get("labels") or n.get("type", "Module")
        if lbl in ("Database", "cache"):
            databases.append(n)
        elif lbl == "Library":
            libraries.append(n)
        elif lbl == "Infrastructure":
            infra.append(n)
        else:
            modules.append(n)

    if modules:
        lines.append("  subgraph Application_Modules[\"Application Modules\"]")
        for m in modules[:25]:
            nid = _sanitize_id(m["id"])
            name = m.get("name", m["id"])
            lines.append(f"    {nid}[\"{name}\"]")
        lines.append("  end")

    if databases:
        lines.append("  subgraph Data_Layer[\"Databases & Caching\"]")
        for d in databases[:8]:
            nid = _sanitize_id(d["id"])
            name = d.get("name", d["id"])
            lines.append(f"    {nid}[(\"{name}\")]")
        lines.append("  end")

    if libraries:
        lines.append("  subgraph External_Libraries[\"Key Third-Party Libraries\"]")
        for lib in libraries[:10]:
            nid = _sanitize_id(lib["id"])
            name = lib.get("name", lib["id"])
            v = lib.get("version", "")
            label = f"{name} ({v})" if v else name
            lines.append(f"    {nid}[\"{label}\"]")
        lines.append("  end")

    if infra:
        lines.append("  subgraph Infrastructure[\"Infrastructure & CI\"]")
        for i in infra[:6]:
            nid = _sanitize_id(i["id"])
            name = i.get("name", i["id"])
            lines.append(f"    {nid}{{\"{name}\"}}")
        lines.append("  end")

    # Add edges between visible nodes
    visible_ids = {n["id"] for n in nodes[:max_nodes]}
    for e in edges:
        src = e["source_id"]
        dst = e["target_id"]
        rtype = e.get("rel_type", "DEPENDS_ON")
        if src in visible_ids and dst in visible_ids:
            s_id = _sanitize_id(src)
            d_id = _sanitize_id(dst)
            lines.append(f"  {s_id} -->|{rtype}| {d_id}")

    return "\n".join(lines)


def generate_blast_radius_diagram(
    root_id: str,
    impact_data: Dict[str, Any],
) -> str:
    """
    Generates a Mermaid.js diagram illustrating the blast radius and failure propagation tree
    for a specific component from graph traversal results.
    """
    lines = [
        "%%{init: {'theme': 'dark', 'themeVariables': { 'darkMode': true }}}%%",
        "graph LR",
    ]

    root_sanitized = _sanitize_id(root_id)
    root_info = impact_data.get("root") or {}
    root_comp = root_info.get("component") or {}
    root_name = root_comp.get("name") or root_id
    lines.append(f"  {root_sanitized}[\"💥 ORIGIN: {root_name}\"]:::rootNode")

    direct = impact_data.get("direct") or []
    indirect = impact_data.get("indirect") or []

    # Group direct (Hop 1)
    if direct:
        lines.append("  subgraph Direct_Impact[\"Direct Dependents (Hop 1)\"]")
        for d in direct[:10]:
            comp = (d or {}).get("component") or {}
            cid = _sanitize_id(comp.get("id", "unknown"))
            cname = comp.get("name", comp.get("id", "unknown"))
            lines.append(f"    {cid}[\"{cname}\"]:::directNode")
            lines.append(f"    {cid} -.->|reaches| {root_sanitized}")
        lines.append("  end")

    # Group indirect (Hop >= 2)
    if indirect:
        lines.append("  subgraph Transitive_Impact[\"Transitive Dependents (Hops 2..6)\"]")
        for ind in indirect[:15]:
            comp = (ind or {}).get("component") or {}
            cid = _sanitize_id(comp.get("id", "unknown"))
            cname = comp.get("name", comp.get("id", "unknown"))
            depth = (ind or {}).get("depth", 2)
            lines.append(f"    {cid}[\"{cname} (depth {depth})\"]:::indirectNode")
            # Connect to its next step in chain if available
            chain_nodes = ind.get("chain_nodes", [])
            if len(chain_nodes) >= 2:
                next_in_chain = _sanitize_id(chain_nodes[1]["id"])
                lines.append(f"    {cid} --> {next_in_chain}")
            else:
                lines.append(f"    {cid} --> {root_sanitized}")
        lines.append("  end")

    # Custom styles
    lines.append("  classDef rootNode fill:#e11d48,stroke:#fda4af,stroke-width:2px,color:#fff;")
    lines.append("  classDef directNode fill:#d97706,stroke:#fde68a,stroke-width:1px,color:#fff;")
    lines.append("  classDef indirectNode fill:#475569,stroke:#94a3b8,stroke-width:1px,color:#fff;")

    return "\n".join(lines)
