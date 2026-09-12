"""
Tree-sitter AST walker for Python, JavaScript, and TypeScript source files.

Extracts imports/requires, top-level definitions (classes, functions), and call expressions.
Resolves relative and internal imports against the repository file manifest.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

from backend.app.ingestion.models import FileEntry
from backend.app.parsers.ast.language_grammars import get_parser

log = logging.getLogger(__name__)


@dataclass
class ImportStatement:
    source: str
    resolved_path: Optional[str] = None
    imported_symbols: List[str] = field(default_factory=list)
    is_relative: bool = False
    line: int = 1


@dataclass
class DefinitionItem:
    name: str
    kind: str  # "function", "class", "route"
    line: int = 1


@dataclass
class CallItem:
    callee: str
    line: int = 1


@dataclass
class FileAstSummary:
    path: str
    language: str
    imports: List[ImportStatement] = field(default_factory=list)
    defines: List[DefinitionItem] = field(default_factory=list)
    calls: List[CallItem] = field(default_factory=list)


def resolve_import_path(
    source: str,
    current_file_path: str,
    known_paths: Set[str],
    language: str,
) -> Optional[str]:
    """
    Resolves relative or module imports to actual repository file paths.
    E.g. './Button' in 'frontend/src/App.jsx' -> 'frontend/src/components/Button.jsx'
    E.g. '..services.cypher' in 'backend/app/routes/api.py' -> 'backend/app/services/cypher.py'
    """
    current_dir = Path(current_file_path).parent

    # 1. Relative imports starting with . or ..
    if source.startswith("."):
        # Python style relative import (e.g. .services or ..services.cypher)
        if language == "python":
            dots = 0
            while dots < len(source) and source[dots] == ".":
                dots += 1
            remainder = source[dots:]
            target_dir = current_dir
            for _ in range(dots - 1):
                target_dir = target_dir.parent

            rel_mod_path = remainder.replace(".", "/") if remainder else ""
            candidate = (target_dir / rel_mod_path).as_posix().lstrip("./") if rel_mod_path else target_dir.as_posix().lstrip("./")

            for ext in (".py", "/__init__.py", ""):
                test_path = candidate + ext
                if test_path in known_paths:
                    return test_path
        else:
            # JS/TS relative import (e.g. ./Button, ../api)
            target = (current_dir / source).resolve()
            # Normalize relative to repo root (assuming cwd is repo root)
            rel_candidate = os.path.normpath(str(current_dir / source)).replace("\\", "/")
            if rel_candidate.startswith("./"):
                rel_candidate = rel_candidate[2:]

            for ext in ("", ".js", ".jsx", ".ts", ".tsx", "/index.js", "/index.jsx", "/index.ts", "/index.tsx"):
                test_path = rel_candidate + ext
                if test_path in known_paths:
                    return test_path

    # 2. Internal non-relative imports (e.g. 'backend.app.services.cypher' or 'src/utils')
    if language == "python":
        mod_as_path = source.replace(".", "/")
        for ext in (".py", "/__init__.py"):
            test_p = mod_as_path + ext
            if test_p in known_paths:
                return test_p
            # Check prefixed paths
            for kp in known_paths:
                if kp.endswith(test_p):
                    return kp

    # 3. Check direct match in known_paths
    if source in known_paths:
        return source

    return None


def _extract_python_ast(code_bytes: bytes, file_path: str, known_paths: Set[str]) -> FileAstSummary:
    """Extracts imports, definitions, and calls from Python using tree-sitter."""
    parser = get_parser("python")
    summary = FileAstSummary(path=file_path, language="python")
    if not parser:
        return summary

    try:
        tree = parser.parse(code_bytes)
    except Exception as exc:
        log.warning("Tree-sitter parse error for %s: %s", file_path, exc)
        return summary

    cursor = tree.walk()

    def visit(node):
        # 1. import statement: import x, import x.y.z as foo
        if node.type == "import_statement":
            for child in node.children:
                if child.type == "dotted_name":
                    source = child.text.decode("utf-8")
                    resolved = resolve_import_path(source, file_path, known_paths, "python")
                    summary.imports.append(ImportStatement(
                        source=source,
                        resolved_path=resolved,
                        imported_symbols=[source],
                        is_relative=source.startswith("."),
                        line=node.start_point.row + 1,
                    ))
                elif child.type == "aliased_import":
                    dname = child.child_by_field_name("name")
                    if dname:
                        source = dname.text.decode("utf-8")
                        resolved = resolve_import_path(source, file_path, known_paths, "python")
                        summary.imports.append(ImportStatement(
                            source=source,
                            resolved_path=resolved,
                            imported_symbols=[source],
                            is_relative=source.startswith("."),
                            line=node.start_point.row + 1,
                        ))

        # 2. import from statement: from x.y import a, b
        elif node.type == "import_from_statement":
            module_name_node = node.child_by_field_name("module_name")
            rel_prefix = ""
            # Count relative dots if present
            for child in node.children:
                if child.type == "relative_import":
                    rel_prefix = child.text.decode("utf-8")
                    break

            mod_name = module_name_node.text.decode("utf-8") if module_name_node else ""
            full_source = rel_prefix + mod_name

            symbols = []
            for child in node.children:
                if child.type == "dotted_name" and child != module_name_node:
                    symbols.append(child.text.decode("utf-8"))
                elif child.type == "identifier" and child != module_name_node:
                    symbols.append(child.text.decode("utf-8"))

            resolved = resolve_import_path(full_source, file_path, known_paths, "python")
            summary.imports.append(ImportStatement(
                source=full_source,
                resolved_path=resolved,
                imported_symbols=symbols,
                is_relative=full_source.startswith("."),
                line=node.start_point.row + 1,
            ))

        # 3. definitions: function and class definitions
        elif node.type == "function_definition":
            name_node = node.child_by_field_name("name")
            if name_node:
                summary.defines.append(DefinitionItem(
                    name=name_node.text.decode("utf-8"),
                    kind="function",
                    line=node.start_point.row + 1,
                ))

        elif node.type == "class_definition":
            name_node = node.child_by_field_name("name")
            if name_node:
                summary.defines.append(DefinitionItem(
                    name=name_node.text.decode("utf-8"),
                    kind="class",
                    line=node.start_point.row + 1,
                ))

        # 4. calls: function or method invocations
        elif node.type == "call":
            func_node = node.child_by_field_name("function")
            if func_node:
                summary.calls.append(CallItem(
                    callee=func_node.text.decode("utf-8"),
                    line=node.start_point.row + 1,
                ))

        for child in node.children:
            visit(child)

    visit(tree.root_node)
    return summary


def _extract_js_ts_ast(code_bytes: bytes, file_path: str, known_paths: Set[str], language: str) -> FileAstSummary:
    """Extracts imports, definitions, and calls from JS/TS using tree-sitter."""
    parser = get_parser(language)
    summary = FileAstSummary(path=file_path, language=language)
    if not parser:
        return summary

    try:
        tree = parser.parse(code_bytes)
    except Exception as exc:
        log.warning("Tree-sitter parse error for %s: %s", file_path, exc)
        return summary

    def visit(node):
        # 1. ES module import: import { a, b } from './c'
        if node.type == "import_statement":
            source_node = node.child_by_field_name("source")
            if source_node:
                raw_src = source_node.text.decode("utf-8").strip("'\"`")
                resolved = resolve_import_path(raw_src, file_path, known_paths, language)
                symbols = []
                clause = node.child_by_field_name("clause") or node
                for child in clause.children:
                    if child.type in ("import_specifier", "identifier"):
                        symbols.append(child.text.decode("utf-8"))
                summary.imports.append(ImportStatement(
                    source=raw_src,
                    resolved_path=resolved,
                    imported_symbols=symbols,
                    is_relative=raw_src.startswith("."),
                    line=node.start_point.row + 1,
                ))

        # 2. CommonJS require: const x = require('./x')
        elif node.type == "call_expression":
            func_node = node.child_by_field_name("function")
            args_node = node.child_by_field_name("arguments")
            if func_node and func_node.text.decode("utf-8") == "require" and args_node:
                if args_node.children and len(args_node.children) >= 2:
                    arg_text = args_node.children[1].text.decode("utf-8").strip("'\"`")
                    resolved = resolve_import_path(arg_text, file_path, known_paths, language)
                    summary.imports.append(ImportStatement(
                        source=arg_text,
                        resolved_path=resolved,
                        imported_symbols=["default"],
                        is_relative=arg_text.startswith("."),
                        line=node.start_point.row + 1,
                    ))
            elif func_node:
                summary.calls.append(CallItem(
                    callee=func_node.text.decode("utf-8"),
                    line=node.start_point.row + 1,
                ))

        # 3. definitions: function and class declarations
        elif node.type in ("function_declaration", "method_definition"):
            name_node = node.child_by_field_name("name")
            if name_node:
                summary.defines.append(DefinitionItem(
                    name=name_node.text.decode("utf-8"),
                    kind="function",
                    line=node.start_point.row + 1,
                ))

        elif node.type == "class_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                summary.defines.append(DefinitionItem(
                    name=name_node.text.decode("utf-8"),
                    kind="class",
                    line=node.start_point.row + 1,
                ))

        # Arrow function assignments: const handleClick = () => {}
        elif node.type == "variable_declarator":
            val_node = node.child_by_field_name("value")
            name_node = node.child_by_field_name("name")
            if val_node and val_node.type in ("arrow_function", "function_expression") and name_node:
                summary.defines.append(DefinitionItem(
                    name=name_node.text.decode("utf-8"),
                    kind="function",
                    line=node.start_point.row + 1,
                ))

        for child in node.children:
            visit(child)

    visit(tree.root_node)
    return summary


def parse_codebase_ast(files: List[FileEntry]) -> Dict[str, FileAstSummary]:
    """
    Parses all JavaScript/TypeScript and Python source files across the codebase.
    Returns a dictionary mapping file path -> FileAstSummary.
    """
    known_paths = {f.path for f in files}
    results: Dict[str, FileAstSummary] = {}

    for entry in files:
        if not entry.content:
            continue

        code_bytes = entry.content.encode("utf-8")
        if entry.language == "python":
            results[entry.path] = _extract_python_ast(code_bytes, entry.path, known_paths)
        elif entry.language in ("javascript", "typescript"):
            results[entry.path] = _extract_js_ts_ast(code_bytes, entry.path, known_paths, entry.language)

    return results
