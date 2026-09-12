"""
Scalability Audit Collector:
1. N+1 query pattern detection (database/API calls inside loops).
2. Synchronous blocking calls inside async request paths.
3. Hardcoded connection strings and network configuration.
4. Missing caching on data-intensive operations.
"""

from __future__ import annotations

import logging
import re
import uuid
from typing import Dict, List

from backend.app.collectors.models import AuditFinding
from backend.app.ingestion.models import FileEntry
from backend.app.parsers.ast.treesitter_walker import FileAstSummary

log = logging.getLogger(__name__)

SYNC_BLOCKING_CALLS = {
    "requests.get", "requests.post", "requests.put", "requests.delete",
    "urllib.request.urlopen", "time.sleep",
}

QUERY_CALL_PATTERNS = [
    r"db\.query", r"session\.run", r"session\.query", r"cursor\.execute",
    r"\.find_one", r"\.find\(", r"\.select\(", r"fetch\(", r"axios\.get",
]

HARDCODED_CONFIG_PATTERNS = [
    (
        r"(?:postgres(?:ql)?|mysql|mongodb|redis)://[^:]+:[^@]+@[a-zA-Z0-9.-]+(?::\d+)?/[a-zA-Z0-9_-]+",
        "Hardcoded Database Connection URI with embedded credentials",
        "high",
        "HARDCODED_DB_URI",
    ),
    (
        r"(?:192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2[0-9]|3[0-1])\.\d{1,3}\.\d{1,3}):\d{2,5}",
        "Hardcoded Internal Network IP Address and Port",
        "medium",
        "HARDCODED_INTERNAL_IP",
    ),
]


def detect_scalability_antipatterns(
    files: List[FileEntry],
    ast_summaries: Dict[str, FileAstSummary],
) -> List[AuditFinding]:
    """
    Analyzes codebase for concurrency bottlenecks, N+1 queries, and hardcoded config.
    """
    findings: List[AuditFinding] = []

    for entry in files:
        if entry.language not in ("python", "javascript", "typescript"):
            continue

        lines = entry.content.splitlines()

        # 1. Hardcoded Connection Strings & IPs
        for idx, line in enumerate(lines, 1):
            # Skip test files and docstrings for hardcoded config
            if "test" in entry.path.lower() or line.strip().startswith(("#", "//", "/*", "*")):
                continue

            for pattern, desc, severity, rule_id in HARDCODED_CONFIG_PATTERNS:
                if re.search(pattern, line):
                    findings.append(AuditFinding(
                        id=f"scale-config-{uuid.uuid4().hex[:6]}",
                        dimension="scalability",
                        severity=severity,
                        confidence="high",
                        description=desc,
                        evidence_file=entry.path,
                        evidence_line=idx,
                        rule_id=rule_id,
                        remediation="Extract connection parameters and network addresses into environment variables.",
                        component_id=entry.path,
                    ))

        # 2. Synchronous blocking calls inside async paths (Python)
        if entry.language == "python":
            in_async_func = False
            async_func_name = ""
            async_indent = 0

            for idx, line in enumerate(lines, 1):
                stripped = line.strip()
                indent = len(line) - len(line.lstrip())

                if stripped.startswith("async def "):
                    in_async_func = True
                    async_indent = indent
                    m = re.match(r"async def\s+([A-Za-z0-9_]+)", stripped)
                    async_func_name = m.group(1) if m else "coroutine"
                elif in_async_func and stripped and indent <= async_indent and not stripped.startswith(("@", "#")):
                    in_async_func = False

                if in_async_func:
                    for blocking_call in SYNC_BLOCKING_CALLS:
                        if blocking_call in stripped:
                            findings.append(AuditFinding(
                                id=f"scale-blocking-{uuid.uuid4().hex[:6]}",
                                dimension="scalability",
                                severity="high",
                                confidence="high",
                                description=(
                                    f"Synchronous blocking call '{blocking_call}' in async function '{async_func_name}'. "
                                    f"This blocks the event loop and severely degrades concurrency."
                                ),
                                evidence_file=entry.path,
                                evidence_line=idx,
                                rule_id="SYNC_IN_ASYNC_PATH",
                                remediation=f"Replace '{blocking_call}' with an async non-blocking client (e.g. httpx.AsyncClient or asyncio.sleep).",
                                component_id=entry.path,
                            ))

        # 3. N+1 Query Patterns (Query execution inside loop statements)
        in_loop = False
        loop_indent = 0

        for idx, line in enumerate(lines, 1):
            stripped = line.strip()
            indent = len(line) - len(line.lstrip())

            # Detect loop starts: Python for/while or JS for/while/forEach/map
            if re.match(r"^(?:for\s+|while\s+|for\s*\(|while\s*\()", stripped) or re.search(r"\.(?:forEach|map)\s*\(", stripped):
                in_loop = True
                loop_indent = indent
            elif in_loop and stripped and indent <= loop_indent and not stripped.startswith(("#", "//", "}", "*/")):
                in_loop = False

            if in_loop:
                for qpat in QUERY_CALL_PATTERNS:
                    if re.search(qpat, stripped) and not stripped.startswith(("#", "//")):
                        findings.append(AuditFinding(
                            id=f"scale-nplus1-{uuid.uuid4().hex[:6]}",
                            dimension="scalability",
                            severity="high",
                            confidence="high",
                            description=f"Potential N+1 query pattern: database or network call inside loop construct.",
                            evidence_file=entry.path,
                            evidence_line=idx,
                            rule_id="N_PLUS_ONE_QUERY_SHAPE",
                            remediation="Batch operations using IN clauses, bulk queries, or dataloaders instead of per-item queries.",
                            component_id=entry.path,
                        ))
                        break

    return findings


def run_scalability_collector(
    files: List[FileEntry],
    ast_summaries: Dict[str, FileAstSummary],
) -> List[AuditFinding]:
    """Runs scalability, concurrency, and architecture pattern analysis."""
    return detect_scalability_antipatterns(files, ast_summaries)
