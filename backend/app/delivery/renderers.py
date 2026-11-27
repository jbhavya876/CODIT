"""
Escaped Jinja2 HTML, Markdown, and PDF export renderers for all 4 report profiles (P7).
Strict CSP meta on all HTML exports (`default-src 'none'; style-src 'unsafe-inline'; img-src data:`).
"""

from __future__ import annotations

import html
import json
from typing import Any, Dict, List

from jinja2 import Environment, select_autoescape

_JINJA_ENV = Environment(autoescape=select_autoescape(enabled_extensions=("html", "xml"), default=True))

_TECHNICAL_HTML = _JINJA_ENV.from_string("""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src data:;">
<title>CODIT Technical Report</title>
<style>
  body { font-family: system-ui, sans-serif; background: #0A0B0D; color: #EFEAE0; margin: 0; padding: 32px; line-height: 1.5; }
  h1, h2, h3 { color: #EFEAE0; }
  table { width: 100%; border-collapse: collapse; margin: 14px 0; background: #121418; }
  th, td { padding: 10px; text-align: left; border-bottom: 1px solid #262A34; font-size: 13px; vertical-align: top; }
  th { color: #A6A197; font-size: 11px; text-transform: uppercase; }
  .pill { display: inline-block; padding: 3px 10px; border: 1px solid #D4FF3A; color: #D4FF3A; font-size: 12px; }
  .box { border: 1px solid #262A34; padding: 16px; margin: 16px 0; background: #121418; }
</style>
</head>
<body>
  <h1>CODIT Technical Assurance Report</h1>
  <p>Score: <strong>{{ data.scorecard.overall_score }}/100</strong> | Phase: <span class="pill">{{ data.scorecard.phase }}</span> | Rubric: {{ data.rubric_version }}</p>
  <div class="box">
    <h3>Methodology</h3>
    <p>{{ data.methodology }}</p>
    <p><strong>Effort Range:</strong> {{ data.effort.person_days.min }}..{{ data.effort.person_days.max }} person-days (likely {{ data.effort.person_days.likely }})</p>
  </div>
  {% if data.not_assessed %}
  <div class="box">
    <h3>Coverage Gaps</h3>
    <ul>{% for na in data.not_assessed %}<li>{{ na.text }}</li>{% endfor %}</ul>
  </div>
  {% endif %}
  <div class="box">
    <h3>Process Integrity</h3>
    {% if data.process.assessed %}
      <p>Commits analyzed: {{ data.process.coverage.commits_analyzed or 0 }}</p>
      <p><em>{{ data.process.attribution_limitation }}</em></p>
    {% else %}
      <p>{{ data.process.status_text }}</p>
    {% endif %}
  </div>
  <div class="box">
    <h3>Licenses</h3>
    <p><em>{{ data.licenses.disclaimer }}</em></p>
    <p>Resolved: {{ data.licenses.coverage.resolved or 0 }} / {{ data.licenses.coverage.total or 0 }} ({{ data.licenses.coverage.resolved_pct or 0 }}%)</p>
  </div>
  <h2>Findings ({{ data.findings|length }})</h2>
  <table>
    <thead><tr><th>Severity</th><th>Rule</th><th>Dimension</th><th>Location</th><th>Description</th></tr></thead>
    <tbody>
      {% for f in data.findings %}
      <tr>
        <td>{{ f.severity|upper }}</td>
        <td>{{ f.rule_id }}</td>
        <td>{{ f.dimension }}</td>
        <td><code>{{ f.evidence_file }}{% if f.evidence_line %}:{{ f.evidence_line }}{% endif %}</code></td>
        <td>{{ f.description }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
</body>
</html>""")

_DILIGENCE_HTML = _JINJA_ENV.from_string("""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src data:;">
<title>CODIT Due Diligence Report</title>
<style>
  body { font-family: system-ui, sans-serif; background: #EFEAE0; color: #0A0B0D; margin: 0; padding: 32px; line-height: 1.5; }
  h1, h2 { border-bottom: 1px solid #0A0B0D; padding-bottom: 4px; }
  table { width: 100%; border-collapse: collapse; margin: 12px 0; }
  th, td { padding: 8px; border-bottom: 1px solid #C8C1B4; text-align: left; font-size: 13px; }
  .box { border: 1px solid #0A0B0D; padding: 14px; margin: 14px 0; }
</style>
</head>
<body>
  <h1>Due Diligence Technical &amp; IP Ledger</h1>
  <div class="box">
    <h2>1. Verdict &amp; Coverage</h2>
    <p>Score: <strong>{{ data.verdict_and_coverage.overall_score }}/100</strong> | Phase: <strong>{{ data.verdict_and_coverage.phase }}</strong> | Rubric: {{ data.verdict_and_coverage.rubric_version }}</p>
    <p>Files scanned: {{ data.verdict_and_coverage.coverage.files_scanned }} / {{ data.verdict_and_coverage.coverage.files_total }}</p>
    {% for na in data.verdict_and_coverage.not_assessed %}<p>{{ na.text }}</p>{% endfor %}
  </div>
  <h2>2. Red-Flag Register</h2>
  <ul>{% for rf in data.red_flag_register %}<li><strong>{{ rf.blocker_code }}</strong>: {{ rf.summary }} (refs: {{ rf.appendix_refs|join(', ') }})</li>{% endfor %}</ul>
  <h2>3. IP &amp; Licensing Register</h2>
  <p><em>{{ data.ip_and_licensing_register.disclaimer }}</em></p>
  <h2>4. Process-Integrity Timeline</h2>
  <p><em>{{ data.process_integrity_timeline.attribution_limitation }}</em></p>
  {% if not data.process_integrity_timeline.assessed %}<p>{{ data.process_integrity_timeline.status_text }}</p>{% endif %}
  <h2>5. Key-Person Exposure</h2>
  {% if data.key_person_exposure.assessed %}
    <p>Top share: {{ data.key_person_exposure.top_contributor_share_pct }}% | Single-owner directories: {{ data.key_person_exposure.single_owner_dirs_count }}</p>
    <ul>{% for c in data.key_person_exposure.contributors %}<li>{{ c.label }}: {{ c.commits }} commits ({{ c.share_pct }}%)</li>{% endfor %}</ul>
  {% else %}<p>{{ data.key_person_exposure.status_text }}</p>{% endif %}
  <h2>6. Remediation Estimate</h2>
  <p>{{ data.remediation_estimate.person_days.min }}..{{ data.remediation_estimate.person_days.max }} person-days (likely {{ data.remediation_estimate.person_days.likely }})</p>
  {% if data.remediation_estimate.monetary_range %}
    <p>Monetary range: {{ data.remediation_estimate.monetary_range.min }}..{{ data.remediation_estimate.monetary_range.max }} ({{ data.remediation_estimate.monetary_range.unit }})</p>
  {% endif %}
  <h2>7. Methodology &amp; Limitations</h2>
  <p>{{ data.methodology_and_limitations.methodology }}</p>
  <h2>8. Appendix</h2>
  <table>
    <thead><tr><th>ID</th><th>Rule</th><th>Severity</th><th>File</th><th>Description</th></tr></thead>
    <tbody>{% for item in data.appendix %}<tr><td>{{ item.finding_id }}</td><td>{{ item.rule_id }}</td><td>{{ item.severity }}</td><td>{{ item.evidence_file }}</td><td>{{ item.description }}</td></tr>{% endfor %}</tbody>
  </table>
</body>
</html>""")

_EXECUTIVE_HTML = _JINJA_ENV.from_string("""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src data:;">
<title>CODIT Executive Summary</title>
<style>
  @page { size: letter; margin: 16mm; }
  body { font-family: system-ui, sans-serif; background: #EFEAE0; color: #0A0B0D; margin: 0; padding: 28px; line-height: 1.45; }
  .seal { border: 2px solid #0A0B0D; padding: 14px; margin-bottom: 16px; }
</style>
</head>
<body>
  <div class="seal">
    <h1>Executive Summary &mdash; {{ data.verdict_seal.phase }}</h1>
    <p>Score: <strong>{{ data.verdict_seal.overall_score }}/100</strong> | Rubric {{ data.rubric_version }}</p>
  </div>
  <h2>Risk Themes</h2>
  <ul>{% for t in data.themes %}<li><strong>{{ t.title }}</strong>: {{ t.rationale }}</li>{% endfor %}</ul>
  <h2>Prioritized Actions</h2>
  <ol>{% for a in data.actions %}<li>{{ a.text }}</li>{% endfor %}</ol>
  <h2>Remediation Range</h2>
  <p>{{ data.remediation_range.person_days.min }}..{{ data.remediation_range.person_days.max }} person-days (likely {{ data.remediation_range.person_days.likely }})</p>
  <h2>What This Does Not Cover</h2>
  <ul>{% for item in data.what_this_does_not_cover %}<li>{{ item }}</li>{% endfor %}</ul>
  <p><small>{{ data.methodology }}</small></p>
</body>
</html>""")


def render_profile_html(profile: str, data: Dict[str, Any]) -> str:
    if profile == "diligence":
        return _DILIGENCE_HTML.render(data=data)
    if profile == "executive":
        return _EXECUTIVE_HTML.render(data=data)
    if profile == "underwriting":
        escaped = html.escape(json.dumps(data, indent=2))
        return (
            "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>"
            "<meta http-equiv='Content-Security-Policy' content=\"default-src 'none'; style-src 'unsafe-inline'; img-src data:;\">"
            f"<title>Underwriting</title></head><body><pre>{escaped}</pre></body></html>"
        )
    return _TECHNICAL_HTML.render(data=data)


def render_profile_markdown(profile: str, data: Dict[str, Any]) -> str:
    if profile == "diligence":
        vc = data["verdict_and_coverage"]
        lines = [
            f"# CODIT Due Diligence Report",
            f"",
            f"- **Score**: {vc['overall_score']}/100 ({vc['phase']}, Rubric {vc['rubric_version']})",
            f"- **Files Scanned**: {vc['coverage']['files_scanned']} / {vc['coverage']['files_total']}",
            "",
            "## 1. Verdict & Coverage Gaps",
        ]
        lines.extend([f"- {n['text']}" for n in vc["not_assessed"]] or ["- Full scope assessed."])
        lines.extend(["", "## 2. Red-Flag Register"])
        lines.extend([f"- **{r['blocker_code']}**: {r['summary']} (refs: {', '.join(r['appendix_refs'])})" for r in data["red_flag_register"]] or ["- None."])
        lines.extend(["", "## 3. IP & Licensing Register", f"*{data['ip_and_licensing_register']['disclaimer']}*"])
        lines.extend(["", "## 4. Process-Integrity Timeline", f"*{data['process_integrity_timeline']['attribution_limitation']}*"])
        if not data["process_integrity_timeline"]["assessed"]:
            lines.append(data["process_integrity_timeline"]["status_text"])
        lines.extend(["", "## 5. Key-Person Exposure"])
        if data["key_person_exposure"]["assessed"]:
            lines.append(f"- Top share: {data['key_person_exposure']['top_contributor_share_pct']}%")
        else:
            lines.append(data["key_person_exposure"]["status_text"])
        est = data["remediation_estimate"]
        lines.extend([
            "",
            "## 6. Remediation Estimate",
            f"- Effort: {est['person_days']['min']}..{est['person_days']['max']} person-days (likely {est['person_days']['likely']})",
            "",
            "## 7. Methodology & Limitations",
            data["methodology_and_limitations"]["methodology"],
            "",
            f"## 8. Appendix ({len(data['appendix'])} items)",
        ])
        for item in data["appendix"]:
            lines.append(f"- `{item['finding_id']}` [{item['severity']}] `{item['rule_id']}` `{item['evidence_file']}` — {item['description']}")
        return "\n".join(lines)

    if profile == "executive":
        seal = data["verdict_seal"]
        lines = [
            f"# CODIT Executive Summary — {seal['phase']} ({seal['overall_score']}/100)",
            "",
            "## Risk Themes",
        ]
        lines.extend([f"- **{t['title']}**: {t['rationale']}" for t in data["themes"]])
        lines.extend(["", "## Prioritized Actions"])
        lines.extend([f"{i}. {a['text']}" for i, a in enumerate(data["actions"], 1)])
        pd = data["remediation_range"]["person_days"]
        lines.extend(["", f"## Remediation Range", f"- {pd['min']}..{pd['max']} person-days (likely {pd['likely']})", "", "## What This Does Not Cover"])
        lines.extend([f"- {w}" for w in data["what_this_does_not_cover"]])
        lines.extend(["", data["methodology"]])
        return "\n".join(lines)

    if profile == "underwriting":
        return json.dumps(data, indent=2)

    # Technical markdown fallback summarizing technical dict
    sc = data["scorecard"]
    lines = [
        f"# CODIT Technical Report — {sc['overall_score']}/100 ({sc['phase']})",
        "",
        f"> {data['methodology']}",
        "",
        f"## Licenses",
        f"*{data['licenses']['disclaimer']}*",
        "",
        f"## Process Integrity",
        f"*{data['process']['attribution_limitation']}*",
    ]
    if not data["process"]["assessed"]:
        lines.append(data["process"]["status_text"])
    return "\n".join(lines)


def _pdf_escape(text: str) -> str:
    ascii_safe = text.encode("latin-1", "replace").decode("latin-1")
    return ascii_safe.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def render_minimal_pdf(title: str, lines: List[str]) -> bytes:
    """Emit a deterministic, valid minimal PDF 1.4 binary document with escaped text lines."""
    clipped = [f"{title}"] + lines[:55]
    stream_cmds = ["BT", "/F1 10 Tf", "48 760 Td", "13 TL"]
    for idx, line in enumerate(clipped):
        escaped = _pdf_escape(line[:110])
        if idx == 0:
            stream_cmds.append(f"({escaped}) Tj")
        else:
            stream_cmds.append(f"T* ({escaped}) Tj")
    stream_cmds.append("ET")
    stream_bytes = "\n".join(stream_cmds).encode("latin-1")

    objects = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n",
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj\n",
        f"4 0 obj << /Length {len(stream_bytes)} >>\nstream\n".encode("latin-1") + stream_bytes + b"\nendstream endobj\n",
        b"5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n",
    ]

    buf = bytearray(b"%PDF-1.4\n")
    offsets: List[int] = [0]
    for obj in objects:
        offsets.append(len(buf))
        buf.extend(obj)
    xref_pos = len(buf)
    buf.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("latin-1"))
    for off in offsets[1:]:
        buf.extend(f"{off:010d} 00000 n \n".encode("latin-1"))
    buf.extend(
        f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode("latin-1")
    )
    return bytes(buf)
