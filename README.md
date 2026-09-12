# 🛡️ CODIT — Intelligent Codebase Audit & Architecture Platform

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg?logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688.svg?logo=fastapi)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18-61DAFB.svg?logo=react)](https://reactjs.org/)
[![ONNX Runtime](https://img.shields.io/badge/ONNX_Runtime-1.30.0-005CED.svg?logo=onnx)](https://onnxruntime.ai/)
[![Tree-sitter](https://img.shields.io/badge/Tree--sitter-AST_Parser-orange.svg)](https://tree-sitter.github.io/tree-sitter/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **Production-grade codebase intelligence, static AST security audits, graph-native blast-radius modeling, and explainable machine learning.**

---

## 🎯 Overview

**CODIT** is an autonomous codebase audit and architectural intelligence platform. Given any software repository—via a public GitHub URL, a scoped private repository access token, or a zero-retention ZIP archive—CODIT performs deep static inspection and synthesizes actionable engineering intelligence:

1. **High-Fidelity Property Graph**: Maps services, internal modules, functions, external libraries, and relational dependencies with live openCypher traversals.
2. **Deep Static AST Audit**: Statically parses abstract syntax trees across Python, TypeScript, and JavaScript using Tree-sitter without executing untrusted code.
3. **Open-Source ML Models (ONNX & SHAP)**:
   - **ONNX Defect Model (`defect_model.onnx`)**: Multi-output ensemble regression predicting structural Fragility Index ($0.0 - 1.0$), Defect Risk Tier (`Low`, `Moderate`, `High`, `Critical`), Maintainability Index ($0 - 100$), and Technical Debt remediation person-days.
   - **SHAP Game-Theoretic Explainability**: Computes exact Shapley attributions ($\phi_i$) decomposing how architectural signals (AST complexity, coupling density, secret exposure, test coverage, duplication) add or subtract points from the baseline score.
4. **Prioritized Engineering Roadmap**: Synthesizes concrete remediation phases (*Immediate Blockers*, *Core Reliability*, *Post-Launch Hardening*) with exact `file:line` citations.
5. **Interactive Blueprints**: Dynamically visualizes architectural call graphs and multi-hop failure propagation cascades with bundled Mermaid.js.

---

## 🔒 Security & Sandboxing Guarantees

- **Zero Untrusted Code Execution**: All source files are parsed purely statically. CODIT never imports, compiles, evaluates, or executes uploaded or cloned code.
- **Pre-Extraction Defenses**:
  - **Zip-Slip Guard**: Strictly validates canonical extraction targets to prevent directory traversal outside the sandbox.
  - **Zip-Bomb Guard**: Enforces strict quotas prior to uncompressing (rejects archives with $> 200\text{ MB}$ uncompressed size, $> 5,000$ files, or path depth $> 20$).
- **Zero Retention**: Uploaded ZIP archives and ephemeral cloned repositories are purged immediately post-audit.
- **Hard Security Cap**: If an unpatched critical CVE or hardcoded secret is detected, the repository security score is capped at $\le 25$.

---

## 🏗️ Architecture & Tech Stack

```
                                ┌────────────────────────────────────────┐
                                │             CODIT FRONTEND             │
                                │   React 18 · Vite · Tailwind CSS       │
                                │   Bundled Mermaid.js · Dark Cyber UI   │
                                └──────────────────┬─────────────────────┘
                                                   │ REST / JSON
                                                   ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                    CODIT BACKEND                                       │
│                            FastAPI · Starlette · Uvicorn                               │
├─────────────────────────┬─────────────────────────────┬────────────────────────────────┤
│ 1. INGESTION ENGINE     │ 2. AST PARSER & GRAPH       │ 3. ML & EXPLAINABILITY ENGINE  │
│ • GitHub API Recursive  │ • Tree-sitter AST Walker    │ • ONNX Runtime v1.30.0         │
│ • Ephemeral Git Clone   │ • Iterative Stack Traversal │ • SHAP TreeExplainer           │
│ • Pre-Extraction Guards │ • openCypher Property Graph │ • Multi-Output Defect Model    │
└─────────────────────────┴─────────────────────────────┴────────────────────────────────┘
```

- **Backend**: Python 3.10+, FastAPI, Starlette, Uvicorn, Tree-sitter, NetworkX, ONNX Runtime, SHAP, Scikit-learn.
- **Frontend**: React 18, Vite, Tailwind CSS, bundled Mermaid.js, Cytoscape, Lucide icons.
- **Graph Storage**: CognoDB (Bolt / openCypher) with offline in-memory graph fallback.

---

## 🌐 Graph Data Model

The codebase graph represents architectural components as nodes and their relationships as directed edges where the direction indicates dependency (**"relies on"**):

### Node Labels
| Label | Description | Key Properties |
|---|---|---|
| `:Service` | Deployable service or backend application | `id, name, description, team, status, language` |
| `:Database` | Data store, cache, or message broker | `id, name, database_type, environment, status` |
| `:API` | External third-party API or SaaS integration | `id, name, provider, status` |
| `:Library` | Dependency package or vendored library | `id, name, version, language` |
| `:Infrastructure` | Cloud resources, container host, or mesh | `id, name, provider, environment, status` |
| `:Team` | Owning engineering team | `id, name` |

### Relationship Types
| Relationship | From → To | Semantics |
|---|---|---|
| `DEPENDS_ON` | Service → Service / Infra | Hard runtime dependency |
| `CALLS` | Service → API | Outbound API call |
| `READS_FROM` / `WRITES_TO` | Service → Database | Data access edges (supports parallel read/write) |
| `USES` | Service → Library | Code dependency / package vulnerability radius |
| `DEPLOYED_ON` | Service → Infrastructure | Execution environment |
| `OWNED_BY` | Service → Team | Organizational ownership (excluded from impact traversals) |

---

## 🧠 Explainable Machine Learning (ONNX & SHAP)

CODIT integrates open-source machine learning models to eliminate subjective risk heuristics:

### 1. ONNX Defect Risk Regressor (`defect_model.onnx`)
A multi-output ensemble regression model exported to ONNX format (opset 15) and executed via `onnxruntime`. The model evaluates 10 structural features:
- `file_count` & `total_loc`
- `component_count` & `coupling_density`
- `critical_vulns`, `high_vulns`, and `medium_vulns`
- `secret_leaks` (high-entropy credential instances)
- `duplication_pct`
- `test_coverage_ratio`

**Outputs:**
- **Fragility Score** ($0.0 - 1.0$)
- **Maintainability Index** ($0 - 100$)
- **Estimated Remediation Effort** (person-days)
- **Defect Risk Tier** (`Low`, `Moderate`, `High`, `Critical`)

### 2. SHAP Game-Theoretic Decomposition
Using Shapley values ($\phi_i$), CODIT explains the exact delta each architectural metric contributes to the final assessment:
$$\text{Score} = \mathbb{E}[f(X)] + \sum_{i=1}^{M} \phi_i$$
This ensures every defect finding and score deduction is mathematically transparent and reproducible.

---

## 🚀 Quick Start

### 1. Prerequisites
- **Python**: `3.10` or newer
- **Node.js**: `18.0` or newer (`npm`)

### 2. Backend Setup

```bash
# Clone repository
git clone https://github.com/charmi-reddy/Dependency-Detective.git codit
cd codit

# Create and activate virtual environment
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt

# Start backend server on :8000
python backend/run.py
```

### 3. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Option A: Start Vite development server on :5173
npm run dev

# Option B: Build production bundle (served directly by FastAPI on :8000)
npm run build
```

Open **`http://localhost:8000`** in your browser (or `http://localhost:5173` if running the Vite dev server).

---

## 🧪 Testing & Quality Assurance

### Run Backend Test Suite (Pytest)
```bash
cd backend
pytest -v
# 49 passed (100% test pass rate across ingestion, AST walker, collectors, graph, report, and security)
```

### Run End-to-End Test Suite (Playwright)
```bash
cd frontend
npx playwright test
```

---

## 📡 REST API Reference

| Endpoint | Method | Description |
|---|:---:|---|
| `/api/health` | `GET` | Health check, active graph backend, and node counts |
| `/api/ingest/public` | `POST` | Ingest public GitHub repository (e.g. `https://github.com/owner/repo`) |
| `/api/ingest/zip` | `POST` | Upload and inspect ZIP archive with pre-extraction defenses |
| `/api/ingest/private` | `POST` | Ephemeral clone using scoped read-only GitHub token |
| `/api/analyze/run` | `POST` | Trigger full audit scan, ONNX inference, and SHAP explainability |
| `/api/report` | `GET` | Retrieve complete canonical audit report, scores, findings, and ML metrics |
| `/api/report/markdown` | `GET` | Export report parity as Markdown document |
| `/api/report/html` | `GET` | Export report parity as standalone HTML / Print PDF |
| `/api/report/diagram/impact/{component_id:path}` | `GET` | Generate dynamic Mermaid blast radius diagram for component |
| `/api/components` | `GET` | Search indexed components by name or type |
| `/api/components/{id}/impact` | `GET` | Calculate multi-hop blast radius reach and failure chains |
| `/api/path` | `GET` | Shortest path and alternative dependency chains between components |

---

## 📂 Repository Structure

```
codit/
├── backend/
│   ├── app/
│   │   ├── collectors/       # 5 audit signal collectors (security, tests, duplication, etc.)
│   │   ├── delivery/         # Models, Markdown & HTML report exporters
│   │   ├── diagrams/         # Dynamic Mermaid diagram generators
│   │   ├── graph/            # Graph assembler, schema, and CognoDB/Cypher service
│   │   ├── ingestion/        # GitHub API fetch, ZIP safe extract, Git clone
│   │   ├── ml/               # ONNX defect scorer & SHAP explainability engine
│   │   │   └── models/       # Trained defect_model.onnx model binary
│   │   ├── parsers/ast/      # Iterative Tree-sitter stack walker
│   │   ├── routes/           # FastAPI REST routers (ingest, analyze, report, api)
│   │   └── state.py          # Unified in-memory state store
│   ├── tests/                # 49 unit, integration, and security tests
│   ├── requirements.txt      # Python dependencies (FastAPI, Tree-sitter, ONNX, SHAP)
│   └── run.py                # Server entry point
├── frontend/
│   ├── src/
│   │   ├── components/       # UI components & MermaidViewer
│   │   ├── pages/            # AuditPage, IngestPage, Dashboard, ComponentDetail
│   │   ├── api.js            # REST client
│   │   └── App.jsx           # App shell, navigation & CODIT brand layout
│   ├── tests/                # Playwright E2E test specs
│   └── package.json
├── database/                 # Canonical seed datasets and Cypher queries
└── README.md
```

---

## ⚖️ License

Distributed under the **MIT License**. See `LICENSE` for more information.
