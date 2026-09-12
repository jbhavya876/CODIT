readable, and easy to extend — adding a new relationship kind is a data change,
not a schema migration plus a rewrite of every recursive query.

**Why CognoDB specifically:** a fully managed cloud graph database that speaks
Bolt 5.x and openCypher, so the official Neo4j Python driver connects unchanged,
and local development can move to production with a one-line URI change.

---

## Architecture

```
┌────────────────────┐        REST/JSON        ┌────────────────────────┐
│  React + Tailwind  │  ─────────────────────▶ │      Flask API         │
│  (Vite dev server) │ ◀─────────────────────  │  route → validate      │
└────────────────────┘                         │  → service → query     │
   never sees DB credentials                    └───────────┬────────────┘
                                                official Neo4j driver (Bolt)
                                               ┌───────────▼────────────┐
                                               │    CognoDB (managed)   │
                                               │    property graph      │
                                               └────────────────────────┘
```

- **Frontend** (`frontend/`) — React 18 + Tailwind, hash-based SPA. Talks only
  to the Flask API. Vite proxies `/api` in development.
- **Backend** (`backend/`) — Flask application factory, blueprint routes,
  validation, error envelope `{"error": {code, message}}`. All graph access is
  parameterised Cypher in `app/services/cypher.py`, executed via the official
  `neo4j` driver; credentials come from env vars only.
- **Demo backend** — setting no `COGNODB_URI` flips the app to an embedded
  dataset (`GRAPH_BACKEND=auto|demo`, NetworkX) with the **same function
  signatures and response shapes**, so the UI, tests, and offline development
  work without a database. The header pill always shows which backend is live.
- **Database** (`database/`) — `seed_data.py` (canonical dataset, self-validating),
  `seed.py` (idempotent loader), `queries/` (the Cypher library, console-ready).

---

## Graph data model

![Graph data model](docs/graph-model.svg)

Every entity node carries the base label `:Component` plus exactly one type
label. Edge direction always means **"relies on"**.

### Node types

| Label | Purpose | Key properties |
|---|---|---|
| `:Service` | Deployable unit of the system | `id, name, description, team, environment, status, language` |
| `:Database` | Data store or cache | `id, name, database_type, environment, status` |
| `:API` | External third-party API | `id, name, provider, status` |
| `:Library` | Code dependency (think CVE blast radius) | `id, name, version, language` |
| `:Infrastructure` | Platform primitives | `id, name, provider, environment, status` |
| `:Team` | Owning team (organisational, not a dependency) | `id, name` |

### Relationship types

| Type | From → To | Meaning |
|---|---|---|
| `DEPENDS_ON` | Service → Service/Infra | Hard runtime dependency |
| `CALLS` | Service → API | Outbound third-party call |
| `READS_FROM` / `WRITES_TO` | Service → Database | Separate read/write edges (parallel edges allowed) |
| `USES` | Service → Library | Vendored code (*"what if PyJWT has a CVE?"*) |
| `DEPLOYED_ON` | Service → Infrastructure | Runs on this platform |
| `OWNED_BY` | Service → Team | Ownership — **excluded** from impact/path traversals |

### Seed dataset (fully synthetic)

61 nodes / 123 relationships: **22** services, **6** databases, **8** APIs,
**12** libraries, **6** infrastructure, **7** teams — a small e-commerce
platform with shared databases, shared APIs, shared infra, and chains up to
5 hops (`Customer Portal → Checkout → Payment → Auth → PostgreSQL`).
Service-to-service dependencies are acyclic (validated on load); every service
has exactly one owning team; every library/API/database is reachable.

---

## The queries

All Cypher is **parameterised** (`$id`, `$q`, …) — no string concatenation ever
reaches the database. Full files: [`database/queries/`](database/queries) and
`backend/app/services/cypher.py`.

| # | Question | Shape |
|---|---|---|
| 1 | Component search | `WHERE toLower(n.name) CONTAINS toLower($q)` + label filter |
| 2 | Direct deps/dependents | single-hop `MATCH` out/in |
| 3 | **Impact analysis** ⭐ | variable-length `[*1..6]` over 6 rel types + per-node shortest chain |
| 4 | Why A depends on B | all paths `[*1..8]`, shortest first, `LIMIT $maxPaths` |
| 5 | Criticality | direct `[*1]` vs indirect `[*2..6]` disjoint counts |
| 6 | Leaderboard | whole-graph aggregate over a variable-length traversal |

The multi-hop requirement (≥ 2 hops) is met by query 3 — e.g. PostgreSQL → Auth
→ Payment → Checkout → Customer Portal. Queries 3 and 4 are the ones that would
be awkward relationally (see "Why a graph database?").

**Criticality scoring** — deliberately simple, entirely graph-derived:

# 🛡️ CODIT — Intelligent Codebase Audit & Architecture Platform

**Production-grade codebase intelligence, static AST security audits, graph-native blast-radius modeling, and explainable machine learning.**

---

## 🎯 Overview

**CODIT** is an autonomous, production-ready codebase audit and architecture intelligence platform. Given any software repository—via a public GitHub URL, a scoped private GitHub token, or a zero-retention local ZIP archive—CODIT constructs:

1. **A High-Fidelity Property Graph**: Maps services, internal modules, functions, external libraries, and relational dependencies with live Cypher traversals.
2. **Deep Static AST Audit**: Statically parses abstract syntax trees across Python, TypeScript, and JavaScript using Tree-sitter without executing untrusted code.
3. **Open-Source ML Models (ONNX & SHAP)**:
   - **ONNX Defect Model (`defect_model.onnx`)**: Multi-output ensemble regression predicting structural Fragility Index ($0.0 - 1.0$), Defect Risk Tier (`Low`, `Moderate`, `High`, `Critical`), Maintainability Index ($0 - 100$), and Technical Debt remediation person-days.
   - **SHAP Game-Theoretic Explainability**: Computes exact Shapley attributions ($\phi_i$) decomposing how architectural signals (AST complexity, circular dependencies, test isolation, secret density, duplication) add or subtract points from the baseline score.
4. **Prioritized Engineering Roadmap**: Synthesizes concrete remediation phases (Immediate Blockers, Core Reliability, Post-Launch Hardening) with exact `file:line` citations.
5. **Interactive Blueprints**: Dynamically renders architectural call graphs and multi-hop failure propagation cascades with bundled Mermaid.js.

---

## 🔒 Security & Sandboxing Guarantees

- **Zero Untrusted Code Execution**: All source files are parsed statically. Never imports, evaluates, or runs target code.
- **Pre-Extraction Defense**:
  - **Zip-Slip Guard**: Strictly validates canonical destination paths to prevent directory traversal attacks.
  - **Zip-Bomb Guard**: Enforces strict quotas before writing to disk (rejects cumulative uncompressed size $> 200\text{ MB}$, file count $> 5,000$, or directory depth $> 20$).
- **Zero Retention**: Uploaded ZIP archives and ephemeral cloned repositories are purged immediately post-audit (Constraint 7).
- **Hard Security Cap**: If an unaddressed critical CVE or hardcoded secret is detected, the security score is irrevocably capped at $\le 25$.

---

## 🏗️ Architecture & Tech Stack

```
                               ┌────────────────────────────────────────┐
                               │           CODIT FRONTEND               │
                               │   React 18 · Vite · Tailwind CSS       │
                               │   Bundled Mermaid.js · Dark Cyber UI   │
                               └──────────────────┬─────────────────────┘
                                                  │ REST APIs
                                                  ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                   CODIT BACKEND                                        │
│                           FastAPI · Starlette · Uvicorn                                │
├─────────────────────────┬─────────────────────────────┬────────────────----------------┤
│ 1. INGESTION ENGINE     │ 2. AST PARSER & GRAPH       │ 3. ML & EXPLAINABILITY ENGINE  │
│ • GitHub API Recursive  │ • Tree-sitter Walker        │ • ONNX Runtime v1.30.0         │
│ • Ephemeral Git Clone   │ • Iterative Stack Traversal │ • SHAP TreeExplainer           │
│ • Pre-Extraction Guards │ • openCypher Property Graph │ • Multi-Output Defect Model    │
└─────────────────────────┴─────────────────────────────┴────────────────────────────────┘
```

- **Backend**: Python 3.10+, FastAPI, Starlette, Uvicorn, Tree-sitter, NetworkX, ONNX Runtime, SHAP, Scikit-learn.
- **Frontend**: React 18, Vite, Tailwind CSS, bundled Mermaid.js, Cytoscape, Lucide icons.
- **Graph Storage**: CognoDB (Bolt / openCypher) with offline in-memory graph fallback.

---

## 🚀 Quick Start

### 1. Prerequisites
- **Python**: `3.10` or newer
- **Node.js**: `18.0` or newer (`npm`)

### 2. Backend Setup

```bash
# Create and activate virtual environment
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
# source .venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt

# Run backend API on :8000
python backend/run.py
```

### 3. Frontend Setup

```bash
cd frontend

# Install packages
npm install

# Run Vite development server
npm run dev

# Or build production bundle (served directly by backend on :8000)
npm run build
```

Once running, visit **`http://localhost:8000`** (or `http://localhost:5173` if running Vite dev server).

---

## 🧪 Testing & Verification

### Run Backend Test Suite (Pytest)
```bash
pytest -v
# 49 passed (100% test pass rate across ingestion, AST walker, collectors, graph, report, and security)
```

### Run End-to-End Test Suite (Playwright)
```bash
cd frontend
npx playwright test
# Tests all 5 primary routes and interactions
```

---

## 📡 REST API Reference

| Endpoint | Method | Description |
|---|:---:|---|
| `/api/health` | `GET` | Health check, active graph backend, and node counts |
| `/api/ingest/public` | `POST` | Ingest public GitHub repository (e.g. `https://github.com/owner/repo`) |
| `/api/ingest/zip` | `POST` | Upload and extract ZIP archive with pre-extraction defenses |
| `/api/ingest/private` | `POST` | Ephemeral clone using scoped read-only GitHub token |
| `/api/analyze/run` | `POST` | Trigger full audit scan, ONNX inference, and SHAP explainability |
| `/api/report` | `GET` | Retrieve complete canonical audit report, scores, findings, and ML metrics |
| `/api/report/markdown` | `GET` | Export report parity as Markdown document |
| `/api/report/html` | `GET` | Export report parity as standalone HTML / Print PDF |
| `/api/report/diagram/impact/{id:path}` | `GET` | Generate dynamic Mermaid blast radius diagram for component |
| `/api/components` | `GET` | Search indexed components by name or type |
| `/api/components/{id}/impact` | `GET` | Calculate multi-hop blast radius reach and failure chains |
| `/api/path` | `GET` | Shortest path and alternative dependency chains between two components |

---

## 📂 Repository Structure

```
codit/
├── backend/
│   ├── app/
│   │   ├── collectors/       # 5 audit signal collectors (security, test, etc.)
│   │   ├── delivery/         # Models, Markdown & HTML report exporters
│   │   ├── diagrams/         # Mermaid diagram generators
│   │   ├── graph/            # Assembler, schema, and CognoDB/Cypher service
│   │   ├── ingestion/        # GitHub API fetch, ZIP safe extract, Git clone
│   │   ├── ml/               # ONNX defect scorer & SHAP explainability engine
│   │   ├── parsers/ast/      # Iterative Tree-sitter stack walker
│   │   ├── routes/           # FastAPI REST routers (ingest, analyze, report, api)
│   │   └── state.py          # Unified in-memory state store
│   ├── tests/                # 49 unit, integration, and security tests
│   └── run.py                # Server entry point
├── frontend/
│   ├── src/
│   │   ├── components/       # UI components & MermaidViewer
│   │   ├── pages/            # AuditPage, IngestPage, Dashboard, ComponentDetail
│   │   ├── api.js            # REST client
│   │   └── App.jsx           # App shell, navigation & brand layout
│   ├── tests/                # Playwright E2E test specs
│   └── package.json
├── database/                 # Canonical seed datasets and Cypher queries
└── README.md
```

---

## ⚖️ License

MIT License. Developed for automated codebase audits and architectural intelligence.
