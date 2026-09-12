"""
Tests for Module 2: Manifest & Tech-Stack Detection.
"""

from __future__ import annotations

import pytest

from backend.app.ingestion.models import FileEntry
from backend.app.parsers.manifest import extract_manifests_and_signals
from backend.app.parsers.manifest.config_signals import detect_config_signals
from backend.app.parsers.manifest.npm import parse_package_json
from backend.app.parsers.manifest.python import parse_pyproject_toml, parse_requirements_txt


def test_package_json_nested_dependency_types():
    content = """{
      "name": "full-stack-app",
      "version": "1.0.0",
      "dependencies": {
        "react": "^18.2.0",
        "express": "~4.18.2"
      },
      "devDependencies": {
        "typescript": "^5.0.4",
        "vite": "4.3.9"
      },
      "peerDependencies": {
        "react-dom": ">=18.0.0"
      },
      "optionalDependencies": {
        "fsevents": "^2.3.2"
      }
    }"""
    deps = parse_package_json(content, file_path="frontend/package.json")
    by_name = {d.name: d for d in deps}

    # Assert all 6 dependencies across all 4 nested sections were extracted
    assert len(deps) == 6
    assert "react" in by_name
    assert by_name["react"].dep_type == "dependency"
    assert by_name["react"].normalized_version == "18.2.0"
    assert by_name["react"].ecosystem == "npm"
    assert by_name["react"].evidence_file == "frontend/package.json"
    assert by_name["react"].evidence_line is not None

    assert by_name["typescript"].dep_type == "devDependency"
    assert by_name["react-dom"].dep_type == "peerDependency"
    assert by_name["fsevents"].dep_type == "optionalDependency"


def test_pyproject_toml_poetry_format():
    content = """
    [tool.poetry]
    name = "audit-engine"
    version = "0.1.0"
    description = "Codebase audit platform"

    [tool.poetry.dependencies]
    python = "^3.11"
    fastapi = "^0.110.0"
    uvicorn = {version = ">=0.28.0", extras = ["standard"]}
    neo4j = "5.20.0"

    [tool.poetry.dev-dependencies]
    pytest = "^8.1.1"

    [tool.poetry.group.docs.dependencies]
    mkdocs = "^1.5.0"
    """
    deps = parse_pyproject_toml(content, file_path="pyproject.toml")
    by_name = {d.name: d for d in deps}

    assert "fastapi" in by_name
    assert by_name["fastapi"].normalized_version == "0.110.0"
    assert by_name["fastapi"].ecosystem == "PyPI"
    assert by_name["fastapi"].dep_type == "dependency"
    assert by_name["fastapi"].evidence_file == "pyproject.toml"

    assert "uvicorn" in by_name
    assert by_name["uvicorn"].normalized_version == "0.28.0"

    assert "pytest" in by_name
    assert by_name["pytest"].dep_type == "devDependency"

    assert "mkdocs" in by_name
    assert by_name["mkdocs"].dep_type == "group-docs"


def test_requirements_txt_parsing():
    content = """
    # Production dependencies
    Flask>=3.0.0
    gunicorn==21.2.0
    requests[security]~=2.31.0
    -r base.txt
    networkx
    """
    deps = parse_requirements_txt(content, file_path="backend/requirements.txt")
    by_name = {d.name: d for d in deps}

    assert len(deps) == 4
    assert by_name["Flask"].normalized_version == "3.0.0"
    assert by_name["gunicorn"].normalized_version == "21.2.0"
    assert by_name["requests"].normalized_version == "2.31.0"
    assert by_name["networkx"].normalized_version == "latest"
    assert by_name["Flask"].evidence_line == 3


def test_tech_stack_signals_tagged_with_file_evidence():
    files = [
        FileEntry(
            path="docker-compose.yml",
            size=300,
            language="yaml",
            content="""version: '3.8'
services:
  db:
    image: postgres:15-alpine
  cache:
    image: redis:7-alpine
  queue:
    image: rabbitmq:3-management
""",
        ),
        FileEntry(
            path="Dockerfile",
            size=150,
            language="dockerfile",
            content="""FROM python:3.11-slim
EXPOSE 8000
""",
        ),
        FileEntry(
            path=".env.example",
            size=100,
            language="env",
            content="""DATABASE_URL=postgres://user:your_password_here@localhost:5432/db
AWS_ACCESS_KEY_ID=your_aws_key_here
STRIPE_SECRET_KEY=your_stripe_key_here
""",
        ),
    ]

    deps = [
        FileEntry(path="requirements.txt", size=50, language="text", content="fastapi==0.110.0\nneo4j==5.20.0")
    ]
    parsed_deps, _ = extract_manifests_and_signals(deps)
    signals = detect_config_signals(files, parsed_deps)

    # Verify every signal is tagged with evidence_file
    assert len(signals) >= 6
    for s in signals:
        assert s.evidence_file in ("docker-compose.yml", "Dockerfile", ".env.example", "requirements.txt")
        assert s.confidence in ("high", "medium", "low")
        assert s.category in ("database", "cache", "infra", "api", "framework", "message_queue", "ci")

    names = {s.name for s in signals}
    assert "PostgreSQL" in names
    assert "Redis" in names
    assert "RabbitMQ" in names
    assert "FastAPI" in names
    assert "Stripe Payments API" in names
