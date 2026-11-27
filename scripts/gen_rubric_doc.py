"""
Generate `docs/RUBRIC.md` deterministically from `rubric.py`, `effort_model.py`, and `codit_core/rules.yaml`.

Run:
    python scripts/gen_rubric_doc.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from codit_core.detectors.rules_catalog import load_rules_catalog

from backend.app.scoring.effort_model import EFFORT_FALLBACK_BY_SEVERITY, EFFORT_MODEL_VERSION, EFFORT_TABLE
from backend.app.scoring.rubric import RUBRIC_2_0_0


def render_rubric_markdown() -> str:
    lines: list[str] = [
        "# CODIT Scoring Rubric `2.0.0` & Effort Model",
        "",
        "> **Generated deterministically** by `scripts/gen_rubric_doc.py` from `backend/app/scoring/rubric.py`, "
        "`backend/app/scoring/effort_model.py`, and `packages/codit_core/src/codit_core/rules.yaml`. Do not hand-edit.",
        "",
        "Static analysis of repository contents and history. No code is executed. A score is a deterministic "
        "signal over observed evidence — never a certification, legal opinion, or guarantee.",
        "",
        "**Core principle:** *A badge must not reward missing evidence.*",
        "",
        "## 1. Dimension Weights (`2.0.0`)",
        "",
        "| Dimension | Weight | Confidence Scaling | Notes |",
        "|---|---:|---|---|",
    ]
    for dim in RUBRIC_2_0_0["dimensions_order"]:
        w = RUBRIC_2_0_0["weights"][dim]
        scaling = "Applied (`1.0 / 0.75 / 0.5`)" if dim in RUBRIC_2_0_0["new_dimensions"] else "Unscaled (`1.0`, matches `1.0.0`)"
        note = {
            "security": "Static security collector + `AGT-010` (secrets committed to history).",
            "tests": "Test ratio, shallow assertions, framework config checks.",
            "agent_integrity": "`AGT-001..009`, `AGT-011`, `AGT-012`, `GRD-001`, `GRD-002`; requires git history.",
            "scalability": "N+1 query shapes, sync calls in async paths, connection management.",
            "licenses": "`LIC-001..008`; requires >=90% production dependency resolution (or `not_applicable` if no dependencies).",
            "duplication": "Repeated AST/structural code blocks across modules.",
            "maintainability": "Module complexity, monolith boundaries, coupling metrics.",
        }[dim]
        lines.append(f"| `{dim}` | `{w:.2f}` | {scaling} | {note} |")

    lines.extend([
        "",
        f"Total weight: `{sum(RUBRIC_2_0_0['weights'].values()):.2f}`.",
        "",
        "When a dimension is not assessed, its weight is excluded and the remaining assessed dimensions are "
        "renormalized: `overall = round_half_up(sum(w_i * s_i) / sum(w_i))` using `int(x + 0.5)`.",
        "",
        "## 2. Severity Deductions & Confidence Multipliers",
        "",
        "| Severity | Base Deduction |",
        "|---|---:|",
    ])
    for sev, pts in RUBRIC_2_0_0["severity_deductions"].items():
        lines.append(f"| `{sev}` | `{pts}` |")

    lines.extend([
        "",
        "Confidence multipliers (applied to `agent_integrity` and `licenses` only): "
        + ", ".join(f"`{k}` = `{v}x`" for k, v in RUBRIC_2_0_0["confidence_multipliers"].items())
        + ".",
        "",
        "## 3. Hard Score Caps",
        "",
        f"- `security`: capped at `{RUBRIC_2_0_0['caps']['security_critical']}` when any `critical` security finding is present.",
        f"- `licenses`: capped at `{RUBRIC_2_0_0['caps']['licenses_critical']}` on any `critical` finding, `{RUBRIC_2_0_0['caps']['licenses_high']}` on any `high` finding.",
        f"- `agent_integrity`: capped at `{RUBRIC_2_0_0['caps']['agent_integrity_recent_90d']}` when any `high`-confidence `high`/`critical` AGT finding falls within the most recent 90 days of the analyzed history window, and `{RUBRIC_2_0_0['caps']['agent_integrity_three_commits_90d']}` when 3+ distinct commits carry such findings.",
        "",
        "## 4. Phase Gate Rules",
        "",
        "- **Production-track**: `overall >= 80`, `security >= 75`, `tests >= 70`, `agent_integrity >= 60`, `licenses >= 60` (or `not_applicable`), zero `critical` findings, **and every weighted dimension is either `assessed` or `not_applicable`**. Production-track is strictly unattainable without assessed process integrity (*a badge must not reward missing evidence*).",
        "- **MVP**: `overall >= 55`, `security >= 50`, and zero `critical` findings.",
        "- **Prototype**: all other states.",
        "",
        "### Phase Qualifiers & Blockers",
        "",
        "Qualifiers emitted when evidence is partial or absent:",
    ])
    for code, desc in RUBRIC_2_0_0["qualifier_descriptions"].items():
        lines.append(f"- `{code}`: {desc}")

    lines.append("")
    lines.append("Blocker codes: " + ", ".join(f"`{b}`" for b in RUBRIC_2_0_0["blocker_codes"]) + ".")
    lines.extend([
        "",
        "## 5. Rule Catalog (Process Integrity, Guard & License Rules)",
        "",
        "| Rule ID | Dimension | Severity | Basis | Summary | Rationale |",
        "|---|---|---|---|---|---|",
    ])
    catalog = load_rules_catalog()
    for rid in sorted(catalog.keys()):
        meta = catalog[rid]
        dim = meta.get("dimension", "-")
        sev = meta.get("default_severity", "-")
        basis = meta.get("basis", "-")
        title = str(meta.get("title", "")).replace("|", "\\|")
        rationale = str(meta.get("rationale", "")).replace("|", "\\|")
        lines.append(f"| `{rid}` | `{dim}` | `{sev}` | `{basis}` | {title} | {rationale} |")

    lines.extend([
        "",
        f"## 6. Effort Estimation Model (`effort_model_version` `{EFFORT_MODEL_VERSION}`)",
        "",
        "Person-days are reported as an explicit assumption-labeled range (`min..max` with `likely`, assuming 8 engineering hours per person-day). "
        "ONNX ML model outputs are never combined with or added to this effort model.",
        "",
        "| Rule Key | Min (h) | Likely (h) | Max (h) | Unit |",
        "|---|---:|---:|---:|---|",
    ])
    for rkey, (mn, lk, mx, unit) in EFFORT_TABLE.items():
        lines.append(f"| `{rkey}` | `{mn}` | `{lk}` | `{mx}` | {unit} |")

    lines.extend([
        "",
        "Fallback hours per unlisted finding by severity: "
        + ", ".join(
            f"`{sev}` = `{vals[0]}/{vals[1]}/{vals[2]}`"
            for sev, vals in EFFORT_FALLBACK_BY_SEVERITY.items()
            if sev != "info"
        )
        + ".",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    out_path = ROOT / "docs" / "RUBRIC.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_rubric_markdown(), encoding="utf-8")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
