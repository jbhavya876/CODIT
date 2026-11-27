# CODIT Frontend Design Notes (Synced to Shipped Forensic Luxury Tokens — D7 Resolved)

## 1. Authoritative Design Token Set: *Forensic Luxury*

The shipped tokens live in `frontend/tailwind.config.js`, `frontend/src/index.css`, and `docs/UI_DESIGN_SYSTEM.md`:
- **Chamber (Operational Dark HUD)**: `#0A0B0D` base (`chamber-bg`), `#15171B` surface, `#1E2228` elevated, `#2A2E35` border.
- **Dossier (Archival Paper & Verify Page)**: `#EFEAE0` bone paper, `#F7F4EE` surface, `#D8D2C5` ruled border, `#101114` ink, `#575A65` muted ink.
- **Single Brand Accent**: `#D4FF3A` (`laser-lime`).
- **Two-Channel Severity (Glyph + Label + Hue)**: Critical `◆ CRIT` (`#FF4A2B`), High `▲ HIGH` (`#FFB020`), Medium `■ MED` (`#FACC15`), Low `● LOW` (`#5DE6A8`), Info `○ INFO` (`#8CC8FF`).
- **Decoupled Confidence Basis Chips**: `[●●●] AST PROOF`, `[●●●] HISTORY PROOF`, `[●●○] GRAPH HEUR`, `[●●○] PATTERN`, `[●○○] ESTIMATE`.
- **Self-Hosted Typefaces**: `Instrument Serif` (display verdicts), `Geist Sans` (UI/body), `JetBrains Mono` (`tabular-nums` citations, SHAs, metrics).

## 2. Two-Pillar IA & Honesty Guarantees

- Top-level navigation remains **Audit Cockpit** (`#/audit`) and **Ingest Repo** (`#/ingest`), with Process (`?tab=process`), Licenses (`?tab=licenses`), Reports (`?tab=reports`), Attest (`?tab=attest`), and Guard drawer inside Audit Cockpit.
- `backend/app/static/verify.css` is generated from the shared Dossier-light tokens via `scripts/export_tokens_css.py`.
- `TrustStrip` reflects real runtime posture from `/api/health` (`0 lines executed · Zip guards active · Static analysis only · Time & memory limits · Source retention: 0s · Results kept 24h`).
