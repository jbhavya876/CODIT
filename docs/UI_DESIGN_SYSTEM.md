# CODIT Design System Specification: *Forensic Luxury*
**Version:** 3.0 · September 2026 · **Status:** Shipped on `ui/forensic-luxury-redesign`

---

## 1. Philosophical Grounding: *Forensic Luxury*

CODIT is an evidence-grade static codebase audit oracle and architecture intelligence platform. The user interface rejects generic AI SaaS templates, neon hacker clichés, and floating card kit conventions.

Instead, the interface merges two design legacies:
1. **FYNSEC-Style Atmospheric Defense Metrology**: Volumetric depth, hairline steel boundaries (`#2A2E35`), true geological obsidian ground (`#0A0B0D`), and focused laser signal accents in Acid-Lime (`#D4FF3A`).
2. **Squarespace-Grade Editorial Craft**: High-contrast editorial display typography (**Instrument Serif**), generous structural whitespace, disciplined typographic rhythm, and archival document fidelity.

### The Dual-Atmosphere System
- **The Chamber (Dark — `#0A0B0D`)**: The primary operational environment for repository intake, interactive graph exploration, and live scan telemetry. Designed for prolonged focus without OLED black-smear or cognitive fatigue.
- **The Dossier (Light — `#EFEAE0`)**: The archival audit deliverable. Cold-pressed unbleached bone paper with deep carbon ink typography (`#101114`), ruled ledger lines, rotating verification seals, and print stylesheets engineered for executive PDF and regulatory filing.

---

## 2. Design Tokens & Color Metrology

### 2.1 Core Substrate Palette

| Token Name | Hex | OKLCH Equivalent | Semantic Role |
|---|---|---|---|
| `chamber-bg` | `#0A0B0D` | `oklch(0.12 0.005 260)` | Primary Chamber canvas ground void |
| `chamber-surface` | `#15171B` | `oklch(0.18 0.008 260)` | Elevated telemetry card decks & HUD containers |
| `chamber-elevated` | `#1E2228` | `oklch(0.24 0.010 260)` | Focus states, interactive hover grounds |
| `chamber-border` | `#2A2E35` | `oklch(0.28 0.012 260)` | 1px hairline structural boundary lines |
| `dossier-bone` | `#EFEAE0` | `oklch(0.93 0.015 85)` | Primary Dossier paper ground |
| `dossier-surface` | `#F7F4EE` | `oklch(0.96 0.008 85)` | Dossier elevated table cards |
| `dossier-ink` | `#101114` | `oklch(0.15 0.005 260)` | Archival carbon typography (14.2:1 contrast) |
| `dossier-border` | `#D8D2C5` | `oklch(0.85 0.015 85)` | Dossier ruled ledger lines |
| `laser-lime` | `#D4FF3A` | `oklch(0.92 0.28 128)` | Brand precision laser signal & active indicator |

---

### 2.2 Two-Channel Severity Metrology

To comply with **WCAG 2.2 AA non-text contrast** and ensure 100% legibility under Protanopia, Deuteranopia, and Tritanopia, severity is never communicated by color alone:

| Level | Geometric Glyph | Hex Token | Dark Pill Style | Light Dossier Style | Cognitive Meaning |
|---|:---:|---|---|---|---|
| **Critical** | `◆ [CRIT]` | `#FF4A2B` | `bg-[#2A0E0B] text-[#FF4A2B] border-[#5A1C16]` | `bg-[#FDECEB] text-[#B91C1C] border-[#F87171]` | Diamond glyph; hard blocker; plaintext secret or CVE |
| **High** | `▲ [HIGH]` | `#FFB020` | `bg-[#281805] text-[#FFB020] border-[#5E3808]` | `bg-[#FEF6E7] text-[#B45309] border-[#FBBF24]` | Triangle glyph; cross-module blast hazard |
| **Medium** | `■ [MED]` | `#FACC15` | `bg-[#241F06] text-[#FACC15] border-[#564908]` | `bg-[#FEFCE8] text-[#854D0E] border-[#FDE047]` | Square glyph; maintainability debt or degraded dep |
| **Low** | `● [LOW]` | `#5DE6A8` | `bg-[#0B231A] text-[#5DE6A8] border-[#164E37]` | `bg-[#ECFDF5] text-[#047857] border-[#6EE7B7]` | Pip glyph; localized hygiene item |
| **Info** | `○ [INFO]` | `#8CC8FF` | `bg-[#0C1B2E] text-[#8CC8FF] border-[#1A3B66]` | `bg-[#F0F9FF] text-[#0369A1] border-[#BAE6FD]` | Ring glyph; architectural note or telemetry flag |

---

### 2.3 Decoupled Confidence Gauge

Confidence measures deterministic verification certainty and is strictly decoupled from severity:
- `[●●●] AST PROOF`: Tree-sitter syntactic node verification (deterministic).
- `[●●○] GRAPH HEUR`: Multi-hop openCypher graph reach heuristic.
- `[●○○] ESTIMATE`: Statistical ONNX model fragility correlation.

---

## 3. Typography Architecture

Self-hosted via `@fontsource` (zero runtime CDN dependencies):

| Family | Role | Weights | Fluid Scale |
|---|---|---|---|
| **Instrument Serif** | Display verdicts, section headers, brand mark | 400, italic | `clamp(2.5rem, 6vw, 5.5rem)` |
| **Geist Sans** | Interface UI, labels, descriptions, navigation | 400, 500, 600, 700 | `clamp(0.875rem, 1vw, 1.05rem)` |
| **JetBrains Mono** | Code citations (`file.py:47`), hashes, metrics | 400, 500, 600 | `clamp(0.75rem, 0.85vw, 0.925rem)` with `tabular-nums` |

---

## 4. The 9 Signature Moments

1. **Hero Constellation (`HeroConstellation.jsx`)**: HTML5 Canvas particle-and-edge living graph reacting to cursor velocity and proximity with laser tethers.
2. **The Verdict (`VerdictSeal.jsx` & `OdometerNumeral.jsx`)**: Massive score numeral counting up smoothly with physics-based stamped risk tier seal and hard cap warning ribbon.
3. **Live Scan Sequence (`IngestPage.jsx`)**: 5-stage staged pipeline with streaming terminal log and progress spine.
4. **Blast Radius Shockwave (`GraphPathInspector.jsx`)**: Multi-hop failure propagation analysis (*1..6 hops) in openCypher graph.
5. **SHAP Ledger (`SHAPLedger.jsx`)**: Double-entry accounting waterfall ledger showing exact marginal contributions from baseline to final score.
6. **Evidenced Findings Ledger (`AuditPage.jsx`)**: High-density tabular layout with AST code citations, expandable syntax peeks, and 1-click clipboard copy.
7. **Dossier Paper Mode**: Instant viewport transition into archival paper layout with print CSS for executive export.
8. **Trust & Safety Strip (`TrustStrip.jsx`)**: Persistent indicator verifying `0 lines executed · Zip guards active · Ephemeral sandbox · Retention: 0s`.
9. **Command Palette (`CommandPalette.jsx`)**: Universal `Cmd/Ctrl + K` fuzzy search dialog for instant keyboard-first navigation.

---

## 5. Developer Preview Route

Inspect all tokens, typography specimens, interactive odometers, and component primitives live at:
```
#/design-system
```
