# CODIT Frontend Redesign — Architectural & Design Notes

## 1. Pass 1 — Design Token Plan

### 1.1 Color Architecture (Geological Obsidian Substrate)
- **Bedrock / Base (`#080B11`)**: Deepest geological obsidian ground. Eliminates generic near-black or navy washes.
- **Surface / Panel (`#0E1420`)**: Instrument panel substrate. Provides high contrast against bedrock.
- **Card / Container (`#111827`)**: Sub-level containers and active inputs.
- **Elevated / Active State (`#151E30`)**: Active selection, drawer background, and focused states.
- **Hairline Border (`#1A2438`)**: Crisp, 1px non-glowing boundaries that delineate components without decorative fuzz.
- **High-Contrast Focus Ring (`#38BDF8`)**: Strict WCAG 2.1 AAA keyboard focus indicator (`:focus-visible`).

### 1.2 Two-Channel Severity Metrology
To ensure complete legibility under protanopia, deuteranopia, tritanopia, and grayscale viewing, every severity indicator is simultaneously encoded with geometric shape, hue, and text label:
- **`CRITICAL`**: `◆ [CRIT]` — Crimson (`#F43F5E` on `#1E0A10`, border `#5C1220`)
- **`HIGH`**: `▲ [HIGH]` — Amber-Orange (`#FB923C` on `#201205`, border `#5C2805`)
- **`MEDIUM`**: `■ [MED]` — Gold (`#FACC15` on `#1D1805`, border `#544405`)
- **`LOW`**: `● [LOW]` — Sky Cyan (`#38BDF8` on `#071927`, border `#0C3852`)
- **`INFO`**: `○ [INFO]` — Slate (`#94A3B8` on `#111827`, border `#1E293B`)

### 1.3 Decoupled 3-Pip Confidence Metrology
Severity is decoupled from statistical confidence:
- `[●●●] AST PROOF`: Deterministic Tree-sitter AST syntax node verification.
- `[●●○] GRAPH HEUR`: Multi-hop reach & topological dependency heuristic.
- `[●○○] ESTIMATE`: Statistical ONNX fragility pattern correlation.

### 1.4 Typography Roles
- **Body & Structural Text**: `Inter`, clean Swiss grotesque sans-serif with tabular numerals (`font-variant-numeric: tabular-nums`).
- **Data & Citations**: `JetBrains Mono` / `SFMono-Regular`, strictly reserved for AST citations (`file:line`), openCypher queries, rule IDs, and telemetry metrics. Never used as decorative label chrome.

---

## 2. Pass 2 — Anti-Cliché Self-Critique (Section 3 Banned Defaults)

1. **Warm cream / terracotta palette**: 
   - *Status*: **REJECTED**. Substrate is strictly geological obsidian (`#080B11`, `#0E1420`).
2. **Near-black with acid-green vermilion**: 
   - *Status*: **REJECTED**. Balanced multi-attribute telemetry with cohesive, functional palette tokens.
3. **Broadsheet / newspaper layout**: 
   - *Status*: **REJECTED**. Layout is structured as a technical flight deck instrument with density driven by actual AST findings.
4. **The SaaS-card kit (uniform rounded cards with drop shadows)**: 
   - *Status*: **REJECTED**. Findings are structured as an Evidence Ledger table; cards in HUD represent distinct computational models (ONNX, SHAP, Scorecard) rather than interchangeable blocks.
5. **Template chrome (middle dots `A · B · C`, decorative `→`, fake all-caps eyebrows)**: 
   - *Status*: **REJECTED**. Replaced with pipe dividers (`|`), monospaced functional tags, and functional action verbs.
6. **Numbered step markers (`01 / 02 / 03`) on non-sequences**: 
   - *Status*: **REJECTED**. Numbers are strictly restricted to sequential processes (e.g. 5-stage ingestion pipeline, 3-phase engineering roadmap).
7. **Scattered motion**: 
   - *Status*: **REJECTED**. Transitions are subtle and functional; `@media (prefers-reduced-motion: reduce)` disables all animations.
8. **Accenting a single headline word with italics/color**: 
   - *Status*: **REJECTED**. Clean, uniform typographic weight.
9. **Cybersecurity-Dribbble house style (glowing 3D orb/shield/blob)**: 
   - *Status*: **REJECTED**. No glowing 3D spheres or shields. Telemetry is grounded entirely in CODIT's computed AST signals and openCypher topology.

---

## 3. Dependency & API Contract Audit

- **New Dependencies**: Zero (0) new external npm packages added. Built entirely using standard Tailwind CSS and existing project dependencies (`@perawallet/connect`, `algosdk`, `mermaid`, `react`, `react-dom`).
- **Backend & API Integrity**: Unmodified. All API endpoints (`/api/ingest/*`, `/api/report`, `/api/analyze`, `/api/components/*`, `/api/dependencies/*`, `/api/criticality/*`, `/api/path`) maintain exact response shapes and contracts.
- **Backend Tests**: 68 / 68 passing in `backend/tests/`.
- **Frontend Tests**: 13 / 13 passing in `test_routes_comprehensive.mjs`.
