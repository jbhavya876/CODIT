"""
Tree-sitter parser initialization for Python, JavaScript, and TypeScript.
"""

from __future__ import annotations

import logging
from typing import Optional

from tree_sitter import Language, Parser

log = logging.getLogger(__name__)

_PARSERS = {}


def get_parser(language: str) -> Optional[Parser]:
    """Retrieves or creates a cached tree-sitter Parser for the specified language."""
    lang_key = language.lower()
    if lang_key in _PARSERS:
        return _PARSERS[lang_key]

    parser = None
    try:
        if lang_key == "python":
            import tree_sitter_python as tspy
            py_lang = Language(tspy.language())
            parser = Parser(py_lang)
        elif lang_key in ("javascript", "jsx"):
            import tree_sitter_javascript as tsjs
            js_lang = Language(tsjs.language())
            parser = Parser(js_lang)
        elif lang_key in ("typescript", "tsx"):
            import tree_sitter_typescript as tsts
            ts_lang = Language(tsts.language_tsx() if "tsx" in lang_key else tsts.language_typescript())
            parser = Parser(ts_lang)
    except Exception as exc:
        log.warning("Failed to initialize tree-sitter parser for %s: %s", language, exc)

    if parser:
        _PARSERS[lang_key] = parser
    return parser
