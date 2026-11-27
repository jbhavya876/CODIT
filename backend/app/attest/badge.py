"""
Server-rendered SVG assurance badges (P8).

Strict guarantees:
- Renders ONLY enumerated state tokens, enumerated phase names, and integers.
- Never accepts or renders any repository-derived free text.
- Every state conveys BOTH text AND distinct glyph (never hue alone).
- XML-escaped output.
"""

from __future__ import annotations

from typing import Optional
from xml.sax.saxutils import escape

VALID_STATES = frozenset({"VERIFIED", "ARCHIVE", "EXPIRED", "REVOKED"})

_STATE_STYLE = {
    "VERIFIED": {"bg": "#15321C", "fg": "#D4FF3A", "label": "VERIFIED", "glyph": "M5 10.5l3 3 6-6.5"},
    "ARCHIVE": {"bg": "#1E222B", "fg": "#EFEAE0", "label": "ARCHIVE — SOURCE NOT VERIFIED", "glyph": "M4 6h10v8H4z M4 9h10"},
    "EXPIRED": {"bg": "#3A2C12", "fg": "#F5B841", "label": "EXPIRED", "glyph": "M9 4.5v5l3 1.5"},
    "REVOKED": {"bg": "#3B1318", "fg": "#FF5D6C", "label": "REVOKED", "glyph": "M5 5l8 8 M13 5l-8 8"},
}


def render_badge_svg(
    *,
    state: str,
    score: Optional[int] = None,
    phase: Optional[str] = None,
    partial: bool = False,
) -> str:
    st = state if state in VALID_STATES else "EXPIRED"
    cfg = _STATE_STYLE[st]

    label_text = cfg["label"]
    if partial and st not in ("REVOKED",):
        label_text = f"{label_text} · PARTIAL"

    safe_label = escape(label_text)
    if st in ("REVOKED", "EXPIRED"):
        right_text = escape(st)
    else:
        int_score = max(0, min(100, int(score if score is not None else 0)))
        safe_phase = escape(phase if phase in ("Prototype", "MVP", "Production-track") else "Prototype")
        right_text = escape(f"{int_score}/100 {safe_phase}")

    left_w = max(92, len(label_text) * 7 + 34)
    right_w = max(96, len(right_text) * 7 + 20)
    total_w = left_w + right_w

    glyph_path = escape(cfg["glyph"])
    fg = cfg["fg"]
    bg = cfg["bg"]

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_w}" height="24" role="img" '
        f'aria-label="CODIT {safe_label}: {right_text}">'
        f'<title>CODIT {safe_label}: {right_text}</title>'
        f'<rect width="{total_w}" height="24" rx="2" fill="#0A0B0D"/>'
        f'<rect x="{left_w}" width="{right_w}" height="24" rx="2" fill="{bg}"/>'
        f'<path d="{glyph_path}" stroke="{fg}" stroke-width="1.6" fill="none" stroke-linecap="round" stroke-linejoin="round" transform="translate(4,3)"/>'
        f'<text x="24" y="16" fill="#EFEAE0" font-family="ui-monospace,SFMono-Regular,Menlo,monospace" font-size="11" font-weight="600">{safe_label}</text>'
        f'<text x="{left_w + 10}" y="16" fill="{fg}" font-family="ui-monospace,SFMono-Regular,Menlo,monospace" font-size="11" font-weight="700">{right_text}</text>'
        f'</svg>'
    )
