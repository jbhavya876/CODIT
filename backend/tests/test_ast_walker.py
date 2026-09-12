"""
Tests for Module 3: AST / Import Graph Extraction.
"""

from __future__ import annotations

import pytest

from backend.app.ingestion.models import FileEntry
from backend.app.parsers.ast.treesitter_walker import parse_codebase_ast, resolve_import_path


def test_python_import_and_definition_extraction():
    py_content = """import os
import sys as system
from app.services.cypher import IMPACT_ANALYSIS, CRITICALITY
from ..models import User

class AuditEngine:
    def __init__(self):
        self.counter = 0

    def analyze(self, target):
        result = self.execute_query(target)
        return result

def helper_func():
    print("running helper")
"""
    files = [
        FileEntry(path="backend/app/routes/analyze.py", size=len(py_content), language="python", content=py_content),
        FileEntry(path="backend/app/services/cypher.py", size=100, language="python", content="# cypher"),
        FileEntry(path="backend/app/models.py", size=50, language="python", content="# models"),
    ]

    ast_map = parse_codebase_ast(files)
    summary = ast_map.get("backend/app/routes/analyze.py")

    assert summary is not None
    assert summary.language == "python"

    # Check imports
    sources = [imp.source for imp in summary.imports]
    assert "os" in sources
    assert "app.services.cypher" in sources or "backend.app.services.cypher" in sources or any("cypher" in s for s in sources)
    assert any("models" in imp.source for imp in summary.imports)

    # Check definitions
    def_names = [d.name for d in summary.defines]
    assert "AuditEngine" in def_names
    assert "analyze" in def_names
    assert "helper_func" in def_names

    # Check calls
    call_names = [c.callee for c in summary.calls]
    assert any("print" in c or "execute_query" in c for c in call_names)


def test_javascript_relative_import_resolution():
    app_jsx = """import React, { useState, useEffect } from 'react';
import Dashboard from './pages/Dashboard';
import { api } from './api';
const Button = require('./components/Button');

export function App() {
  const [data, setData] = useState(null);
  const handleFetch = () => {
    api.health();
  };
  return <div onClick={handleFetch}>Hello</div>;
}
"""
    files = [
        FileEntry(path="frontend/src/App.jsx", size=len(app_jsx), language="javascript", content=app_jsx),
        FileEntry(path="frontend/src/pages/Dashboard.jsx", size=100, language="javascript", content="export default function Dashboard() {}"),
        FileEntry(path="frontend/src/api.js", size=100, language="javascript", content="export const api = {};"),
        FileEntry(path="frontend/src/components/Button.jsx", size=100, language="javascript", content="module.exports = {};"),
    ]

    ast_map = parse_codebase_ast(files)
    summary = ast_map.get("frontend/src/App.jsx")

    assert summary is not None
    resolved_paths = {imp.source: imp.resolved_path for imp in summary.imports}

    # Relative imports must resolve to actual repo paths
    assert resolved_paths.get("./pages/Dashboard") == "frontend/src/pages/Dashboard.jsx"
    assert resolved_paths.get("./api") == "frontend/src/api.js"
    assert resolved_paths.get("./components/Button") == "frontend/src/components/Button.jsx"

    # External package (react) should not resolve to internal path
    assert resolved_paths.get("react") is None


def test_per_file_adjacency_list_structure():
    files = [
        FileEntry(
            path="main.py",
            size=100,
            language="python",
            content="from utils import add\ndef run(): return add(1, 2)",
        ),
        FileEntry(
            path="utils.py",
            size=50,
            language="python",
            content="def add(a, b): return a + b",
        ),
    ]

    ast_map = parse_codebase_ast(files)
    assert set(ast_map.keys()) == {"main.py", "utils.py"}

    main_summary = ast_map["main.py"]
    assert len(main_summary.imports) == 1
    assert main_summary.imports[0].resolved_path == "utils.py"
    assert len(main_summary.defines) == 1
    assert main_summary.defines[0].name == "run"
