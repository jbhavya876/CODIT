# Engineering Notes & Architectural Decisions Log

This document records architectural decisions, default choices for underspecified requirements, and security justifications across all platform modules.

---

## Non-Negotiable Constraints Adherence

1. **Zero Execution of Untrusted Code**: All analysis of ingested repositories is strictly static (text/AST parsing). Package managers (`npm`, `yarn`, `pip`, `setup.py`) are never invoked on analyzed targets.
2. **Zip-Slip Defense**: All entries in uploaded ZIP archives are path-validated upfront before extracting any file. Any entry with path traversal (`..`), absolute paths, or symlink targets escaping the designated extraction directory triggers immediate rejection.
3. **Zip-Bomb Defense**: Cumulative uncompressed size, total file count, and directory depth are checked against configured thresholds before extraction begins.
4. **Sandboxed Worker Isolation**: Worker jobs run in isolated, ephemeral, resource-capped containers (`Dockerfile.worker`) with CPU (1 vCPU), memory (1024MB), and wall-time (120s/180s) limits.
5. **Zero Sandbox Network Egress**: Docker workers run with `--network none` by default.
6. **Privacy Boundary for LLM**: No raw source code is ever sent to Claude/LLM synthesis. Only structured findings, metrics, and graph summaries are transmitted.
7. **Source Code Retention & Deletion**: For the ZIP-upload tier, source files are purged immediately from storage upon completion of the report.
8. **Language Scope**: Exclusively Python and JavaScript/TypeScript.
9. **Evidence Traceability**: Every emitted finding includes an evidence citation with file path (and line number where applicable). Bare claims are prohibited.
10. **Deterministic Precedence**: Rule-triggered findings (critical CVEs, leaked secrets) cannot be downgraded or omitted by the LLM layer.

---

## Module 0: Foundation Decisions

- **FastAPI Migration**: Migrated the web layer from Flask to FastAPI (Python 3.10+ / 3.13 compatible). All existing endpoints (`/api/health`, `/api/stats`, `/api/components`, `/api/components/{id}`, `/api/components/{id}/dependencies`, `/api/components/{id}/impact`, `/api/components/{id}/criticality`, `/api/criticality`, `/api/path`) maintain exact contract parity, including the standard error envelope `{"error": {"code": ..., "message": ...}}`.
- **Cypher Query Library Preservation**: All Cypher queries authored by Charmi Reddy (`services/cypher.py` / `graph/cypher/`) are preserved intact and reused without rewriting query logic.
- **Graph Dual Mode**: Supported both live CognoDB/Neo4j Bolt connections and an enhanced offline in-memory graph engine (`demo_graph.py` / `assembler.py`) so the entire platform operates deterministically in both local development/CI and cloud production.
- **Sandbox Container**: Defined `backend/sandbox/Dockerfile.worker` with an unprivileged worker user, resource ceilings, and `--network none` operational configuration.
