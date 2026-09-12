"""
Tests for Module 4: Graph Assembly & Load.
"""

from __future__ import annotations

import pytest

from backend.app.graph.assembler import assemble_graph, load_and_activate_graph
from backend.app.ingestion.models import FileEntry
from backend.app.parsers.ast.treesitter_walker import parse_codebase_ast
from backend.app.parsers.manifest import extract_manifests_and_signals
from backend.app.services import graph_service


@pytest.fixture(autouse=True)
def reset_graph_after_test():
    yield
    graph_service.reset_graph_to_seed()


def test_real_repo_assembled_graph_loads_without_schema_violations():
    # Construct a realistic multi-component project
    files = [
        FileEntry(
            path="package.json",
            size=150,
            language="json",
            content='{"name": "real-project", "dependencies": {"express": "^4.18.2", "pg": "^8.11.0"}}',
        ),
        FileEntry(
            path="docker-compose.yml",
            size=120,
            language="yaml",
            content="services:\n  db:\n    image: postgres:15\n",
        ),
        FileEntry(
            path="src/index.js",
            size=200,
            language="javascript",
            content="""const express = require('express');
const { getOrders } = require('./routes/orders');
const app = express();
""",
        ),
        FileEntry(
            path="src/routes/orders.js",
            size=250,
            language="javascript",
            content="""const { queryDb } = require('../db/client');
function getOrders() { return queryDb('SELECT * FROM orders'); }
module.exports = { getOrders };
""",
        ),
        FileEntry(
            path="src/db/client.js",
            size=180,
            language="javascript",
            content="""const { Pool } = require('pg');
function queryDb(sql) { return []; }
module.exports = { queryDb };
""",
        ),
    ]

    deps, signals = extract_manifests_and_signals(files)
    ast_map = parse_codebase_ast(files)

    nodes, edges = load_and_activate_graph(files, deps, signals, ast_map)

    # 1. Assert graph loaded without schema violations
    node_ids = {n["id"] for n in nodes}
    assert "src/index.js" in node_ids
    assert "src/routes/orders.js" in node_ids
    assert "src/db/client.js" in node_ids
    assert "lib-npm-express" in node_ids
    assert "lib-npm-pg" in node_ids
    assert "dat-postgresql" in node_ids

    # 2. Check stats endpoint returns correct counts from the assembled graph
    stats = graph_service.stats()
    assert stats["nodes"]["Module"] >= 4
    assert stats["nodes"]["Library"] >= 2
    assert stats["nodes"]["Database"] >= 1

    # 3. Test impact analysis on internal module 'src/db/client.js'
    # orders.js depends on client.js, and index.js depends on orders.js!
    # So if client.js changes, BOTH orders.js and index.js are affected!
    client_impact = graph_service.impact("src/db/client.js")
    assert client_impact["total"] >= 2
    affected_names = {item["component"]["id"] for item in client_impact["direct"] + client_impact["indirect"]}
    assert "src/routes/orders.js" in affected_names
    assert "src/index.js" in affected_names

    # 4. Criticality scoring query produces a plausible ranking
    # The database client module should have reach >= 2
    crit = graph_service.criticality("src/db/client.js")
    assert crit["total"] >= 2
    assert crit["direct"] >= 1  # orders.js directly imports it
    assert crit["indirect"] >= 1  # index.js transitively imports it

    # 5. Leaderboard ranks the most imported module highest
    top_ranked = graph_service.leaderboard(5)
    top_ids = [row["component"]["id"] for row in top_ranked]
    assert "src/db/client.js" in top_ids

    # 6. seed_data is no longer on the critical path:
    health = graph_service.health()
    assert health["is_custom"] is True
