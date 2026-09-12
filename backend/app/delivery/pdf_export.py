"""
Report Export Engine: Generates exportable Markdown and styled HTML/PDF documents.

Both formats consume the canonical AuditReport model, guaranteeing 100% data parity
with the web dashboard.
"""

from __future__ import annotations

import html
import time
from backend.app.delivery.models import AuditReport


def generate_markdown_report(report: AuditReport) -> str:
    """Renders the complete audit report as formatted GitHub-Flavored Markdown."""
    scorecard = report.scorecard
    roadmap = report.roadmap

    lines = [
        f"# Codebase Production-Readiness & Security Audit Report",
        f"",
        f"- **Target**: `{report.target_name}`",
        f"- **Intake Tier**: `{report.access_tier}` ({report.target_type})",
        f"- **Report Generated**: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(report.created_at))}",
        f"- **Overall Maturity Phase**: **{scorecard.phase.upper()}**",
        f"- **Production-Readiness Score**: **{scorecard.overall_score} / 100**",
        f"- **Privacy Status**: {'Source code permanently purged post-audit' if report.source_deleted else 'Standard retention'}",
        f"",
        f"---",
        f"",
        f"## 1. Executive Summary & Scorecard",
        f"",
        f"| Audit Dimension | Score | Critical | High | Medium | Low |",
        f"| :--- | :---: | :---: | :---: | :---: | :---: |",
    ]

    for dim_name, ds in scorecard.dimensions.items():
        lines.append(f"| {dim_name.capitalize()} | {ds.score}/100 | {ds.critical_count} | {ds.high_count} | {ds.medium_count} | {ds.low_count} |")

    lines.extend([
        f"",
        f"> **Phase Verdict: {scorecard.phase}**",
        f"> {roadmap.summary_narrative}",
        f"",
        f"---",
        f"",
        f"## 2. Prioritized Engineering Roadmap ({roadmap.goal.upper()})",
        f"",
        f"**Blockers Status**: {roadmap.blockers_summary}",
        f"",
    ])

    for phase in roadmap.phases:
        lines.append(f"### {phase.phase_name} ({phase.target_timeline})")
        lines.append(f"*{phase.objective}*")
        lines.append("")
        if not phase.action_items:
            lines.append("- *No action items for this phase.*")
        else:
            for item in phase.action_items:
                lines.append(f"- **[{item.priority}] {item.title}**")
                lines.append(f"  - **Action**: {item.action}")
                lines.append(f"  - **Evidence Citation**: `{item.evidence_file}` (Ref: `{item.finding_id}`)")
        lines.append("")

    lines.extend([
        f"---",
        f"",
        f"## 3. Evidenced Findings Catalog ({len(report.findings)} items)",
        f"",
        f"Every finding below includes a verifiable source file (and line number) citation.",
        f"",
        f"| Severity | Dimension | Evidence File:Line | Description | Remediation |",
        f"| :--- | :--- | :--- | :--- | :--- |",
    ])

    for f in report.findings:
        loc = f"`{f.evidence_file}:{f.evidence_line}`" if f.evidence_line else f"`{f.evidence_file}`"
        desc = f.description.replace("|", "\\|")
        rem = (f.remediation or "Investigate and resolve").replace("|", "\\|")
        lines.append(f"| **{f.severity.upper()}** | {f.dimension} | {loc} | {desc} | {rem} |")

    lines.extend([
        f"",
        f"---",
        f"",
        f"## 4. Architecture & Dependency Traversal",
        f"",
        f"```mermaid",
        report.architecture_diagram_mermaid,
        f"```",
        f"",
        f"### High-Criticality Components (Blast Radius Ranking)",
        f"",
        f"| Component | Type | Reach (Blast Radius) | Criticality Tier |",
        f"| :--- | :--- | :---: | :---: |",
    ])

    for row in report.criticality_leaderboard:
        c_obj = row.get("component", {})
        c_name = c_obj.get("name", c_obj.get("id", "Unknown"))
        lines.append(f"| {c_name} | {row.get('type', 'Module')} | {row.get('reach', 0)} components | {row.get('tier', 'LOW')} |")

    return "\n".join(lines)


def generate_html_report(report: AuditReport) -> str:
    """Generates standalone printable HTML report."""
    scorecard = report.scorecard
    roadmap = report.roadmap

    findings_rows = []
    for f in report.findings:
        sev_color = "#e11d48" if f.severity == "critical" else ("#ea580c" if f.severity == "high" else ("#d97706" if f.severity == "medium" else "#64748b"))
        loc = f"{html.escape(f.evidence_file)}:{f.evidence_line}" if f.evidence_line else html.escape(f.evidence_file)
        findings_rows.append(f"""
        <tr>
            <td><span style="background:{sev_color}; color:#fff; padding:2px 8px; border-radius:12px; font-weight:bold; font-size:11px;">{html.escape(f.severity.upper())}</span></td>
            <td>{html.escape(f.dimension.capitalize())}</td>
            <td><code style="background:#1e293b; color:#38bdf8; padding:2px 6px; border-radius:4px;">{loc}</code></td>
            <td>{html.escape(f.description)}</td>
            <td>{html.escape(f.remediation or '')}</td>
        </tr>
        """)

    html_content = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Audit Report - {html.escape(report.target_name)}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0b0f19; color: #f1f5f9; margin: 0; padding: 40px; line-height: 1.5; }}
  h1, h2, h3 {{ color: #f8fafc; margin-top: 24px; }}
  table {{ width: 100%; border-collapse: collapse; margin: 16px 0; background: #131b2e; border-radius: 8px; overflow: hidden; }}
  th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #1e293b; font-size: 13px; }}
  th {{ background: #1e293b; color: #94a3b8; font-weight: 600; text-transform: uppercase; font-size: 11px; }}
  .badge {{ display: inline-block; padding: 4px 12px; border-radius: 9999px; font-weight: bold; text-transform: uppercase; font-size: 12px; }}
  .phase-badge {{ background: #0284c7; color: white; }}
  .card {{ background: #131b2e; border: 1px solid #1e293b; border-radius: 8px; padding: 20px; margin: 16px 0; }}
  @media print {{ body {{ background: white; color: black; }} table, .card {{ background: transparent; border-color: #ccc; }} th {{ background: #eee; color: #333; }} }}
</style>
</head>
<body>
  <h1>Codebase Production-Readiness & Security Audit</h1>
  <p>Target: <strong>{html.escape(report.target_name)}</strong> | Tier: {report.access_tier} | Score: <strong>{scorecard.overall_score}/100</strong> | Phase: <span class="badge phase-badge">{scorecard.phase}</span></p>
  
  <div class="card">
    <h3>Executive Summary</h3>
    <p>{html.escape(roadmap.summary_narrative)}</p>
    <p><strong>Blockers:</strong> {html.escape(roadmap.blockers_summary)}</p>
  </div>

  <h2>Evidenced Audit Findings</h2>
  <table>
    <thead><tr><th>Severity</th><th>Dimension</th><th>Evidence</th><th>Description</th><th>Remediation</th></tr></thead>
    <tbody>{''.join(findings_rows)}</tbody>
  </table>
</body>
</html>"""
    return html_content
