# ADR-0004: `codit_core` Library Boundary & Shared Contracts

- **Status**: Accepted (Gate 0)
- **Date**: 2026-11-27
- **Addresses**: Section 1.3 shared detector insight, P0 item 8, Constraint 16 (local-first guard)

## Context

CODIT runs static checks in two distinct execution contexts:
1. **Server history & snapshot audits** (`backend/app/history/walker.py` reading `dulwich` trees inside a resource-capped child process, plus collectors under `backend/app/collectors/`).
2. **Local/CI `codit-guard` CLI** (`packages/codit_guard/` running against staged diffs, commit ranges, and Claude Code `PreToolUse` edits).

Duplicating detector rules, regex tables, test AST parsers, or fingerprint logic between the server and the CLI guarantees rule drift, mismatched baselines, and duplicated security bugs.

## Decision

1. **Pure-Python library package at `packages/codit_core/`**:
   - Installed editably into the backend (`-e packages/codit_core` in `backend/requirements.txt`) and as a direct dependency of `packages/codit_guard/`.
   - **Forbidden imports inside `codit_core`**: FastAPI, Starlette, Pydantic/ORM DB drivers (`sqlalchemy`, `psycopg`, `neo4j`), HTTP/network clients (`httpx`, `urllib.request`, `socket`, `requests`), LLM SDKs (`anthropic`), subprocess invocations of `git`, and ML runtimes (`onnxruntime`, `shap`, `scikit-learn`).
   - Allowed dependencies inside `codit_core`: Python stdlib, `tree-sitter` + Python/JS/TS grammars (lazy-loaded on demand to meet the <=300 ms guard import budget), `pyyaml` (`safe_load` only), and `license-expression`.
2. **What moves or lives in `codit_core`**:
   - **P0 extraction**:
     - `codit_core.secrets`: `SECRET_PATTERNS`, placeholder skipping rules, and `scan_text()` extracted byte-for-byte from `backend/app/collectors/security.py`. `security.py` imports and delegates to `codit_core.secrets` while preserving exact `AuditFinding` output.
     - `codit_core.classify`: `is_test_file()` extracted from `backend/app/collectors/tests.py`, plus shared path classifiers (`is_ci_path`, `is_gate_config_path`, `is_generated_path`, `language_of`).
     - `codit_core.fingerprint`: `compute_fingerprint(rule_id, evidence_file, match_text, commit_sha=None)` producing stable 32-char SHA-256 prefixes excluding line numbers.
     - `codit_core.findings`: `CoreFinding` data model superset-compatible with `AuditFinding`.
   - **P2/P3 modules**:
     - `delta.py` (`AddedLine`, `FileDelta`, `CommitDelta`), `testmetrics.py` (Python + JS/TS tree-sitter case/assertion/skip/focus/body_hash extraction), `mapping.py` (Tier A name + Tier B import resolution), `suppressions.py`, `ci_weakening.py`, `attribution.py` + `signatures.yaml`, `rules.yaml` (single catalog driving templates, SARIF help URIs, `explain`, and `docs/RUBRIC.md`), and `detectors/` (`agt001`..`agt012`, `grd001`..`grd002`).
   - **P5 pure classification**:
     - `codit_core.licenses`: `spdx.py`, `classify.py`, `headers.py`, `matrix.py`, `classes.yaml`, `matrix.yaml`, and canonical license text matchers. (All HTTP lookups to `deps.dev`/npm/PyPI and `license_cache` stay strictly in `backend/app/licenses/resolve.py`).

## Consequences

- Server history walker and `codit-guard` evaluate identical `CommitDelta` instances through identical detector code, verifiable via parity tests asserting equal `(rule_id, fingerprint)` sets on shared commit ranges.
- `codit_guard` remains lightweight, offline-capable by default, and fast to import (<300 ms).
