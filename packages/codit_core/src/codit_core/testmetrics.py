"""
Tree-sitter test suite metrics extractor for Python and JS/TS (P3).

Lazy-loads tree-sitter grammars inside functions so CLI import time stays <= 300ms.
Produces whitespace- and comment-invariant normalized body hashes.
"""

from __future__ import annotations

import hashlib
import re
from functools import lru_cache
from typing import Any, List, Optional, Tuple

from codit_core.classify import language_of
from codit_core.delta import FileMetrics, TestCaseMetric

ANALYZER_VERSION = "1.0.0"
MAX_TEST_FILE_BYTES = 512 * 1024


@lru_cache(maxsize=4)
def _get_parser(lang_key: str):
    """Lazy-import tree-sitter and grammars only when analyzing test/source files."""
    import tree_sitter
    import tree_sitter_javascript
    import tree_sitter_python
    import tree_sitter_typescript

    if lang_key == "python":
        language = tree_sitter.Language(tree_sitter_python.language())
    elif lang_key == "javascript":
        language = tree_sitter.Language(tree_sitter_javascript.language())
    elif lang_key == "typescript":
        language = tree_sitter.Language(tree_sitter_typescript.language_typescript())
    elif lang_key == "tsx":
        language = tree_sitter.Language(tree_sitter_typescript.language_tsx())
    else:
        raise ValueError(f"Unsupported language key: {lang_key}")
    return tree_sitter.Parser(language)


def _node_text(node, source_bytes: bytes) -> str:
    return source_bytes[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _body_hash(body_node, source_bytes: bytes) -> str:
    """
    Hash leaf AST tokens inside test body excluding comments & whitespace.
    Invariant to whitespace/formatting/comment edits and function renames.
    """
    tokens: List[str] = []
    stack = [body_node]
    while stack:
        cur = stack.pop()
        if cur.type in ("comment", "newline", "indent", "dedent"):
            continue
        if not cur.children:
            txt = source_bytes[cur.start_byte : cur.end_byte].decode("utf-8", errors="replace").strip()
            if txt:
                tokens.append(f"{cur.type}:{txt}")
        else:
            for child in reversed(cur.children):
                stack.append(child)
    joined = "\x1f".join(tokens)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]


def _classify_python_decorators(dec_texts: List[str]) -> Tuple[str, bool]:
    """Return (skipped: none|unconditional|conditional, focused: bool)."""
    skipped = "none"
    for dt in dec_texts:
        compact = re.sub(r"\s+", "", dt)
        if "pytest.mark.skipif" in compact or "unittest.skipIf" in compact or "unittest.skipUnless" in compact:
            if skipped == "none":
                skipped = "conditional"
        elif "pytest.mark.skip" in compact or "unittest.skip" in compact:
            skipped = "unconditional"
        elif "pytest.mark.xfail" in compact:
            if "strict=True" not in compact:
                if skipped == "none":
                    skipped = "conditional"
    return skipped, False


def _has_module_pytestmark_skip(root_node, source_bytes: bytes) -> str:
    for child in root_node.children:
        if child.type == "expression_statement":
            txt = re.sub(r"\s+", "", _node_text(child, source_bytes))
            if txt.startswith("pytestmark=") and "skip" in txt:
                return "conditional" if "skipif" in txt else "unconditional"
    return "none"


def _analyze_python_test_file(source: str) -> FileMetrics:
    src_bytes = source.replace("\r\n", "\n").encode("utf-8", errors="replace")
    parser = _get_parser("python")
    tree = parser.parse(src_bytes)
    root = tree.root_node

    mod_skip = _has_module_pytestmark_skip(root, src_bytes)
    cases: List[TestCaseMetric] = []

    def count_python_assertions(body_node) -> int:
        count = 0
        stack = [body_node]
        while stack:
            cur = stack.pop()
            if cur.type == "assert_statement":
                count += 1
            elif cur.type == "call":
                fn = cur.child_by_field_name("function")
                if fn is not None and fn.type == "attribute":
                    attr = fn.child_by_field_name("attribute")
                    if attr is not None and _node_text(attr, src_bytes).startswith("assert"):
                        count += 1
            elif cur.type == "with_statement":
                header = _node_text(cur, src_bytes).split(":", 1)[0]
                if "pytest.raises(" in header or "pytest.warns(" in header:
                    count += 1
            for child in reversed(cur.children):
                stack.append(child)
        return count

    def top_body_skip(body_node) -> str:
        for stmt in body_node.children:
            if stmt.type == "expression_statement":
                txt = re.sub(r"\s+", "", _node_text(stmt, src_bytes))
                if txt.startswith("pytest.skip(") or txt.startswith("self.skipTest("):
                    return "unconditional"
            elif stmt.type not in ("comment", "pass_statement"):
                # Inspect only top executable statements before test body diverges
                if stmt.type == "expression_statement":
                    continue
                break
        return "none"

    def process_fn(fn_node, dec_texts: List[str], prefix: str = "") -> None:
        name_node = fn_node.child_by_field_name("name")
        body_node = fn_node.child_by_field_name("body")
        if name_node is None or body_node is None:
            return
        fn_name = _node_text(name_node, src_bytes)
        if not fn_name.startswith("test_"):
            return

        full_name = f"{prefix}{fn_name}"
        skipped, focused = _classify_python_decorators(dec_texts)
        if skipped == "none" and mod_skip != "none":
            skipped = mod_skip
        if skipped == "none":
            skipped = top_body_skip(body_node)

        assertions = count_python_assertions(body_node)
        cases.append(
            TestCaseMetric(
                name=full_name,
                assertions=assertions,
                skipped=skipped,  # type: ignore[arg-type]
                focused=focused,
                body_hash=_body_hash(body_node, src_bytes),
                line=fn_node.start_point[0] + 1,
            )
        )

    def handle_block(parent_node, class_decs: List[str] | None = None, prefix: str = "") -> None:
        for child in parent_node.children:
            if child.type == "decorated_definition":
                decs = list(class_decs or [])
                definition = None
                for sub in child.children:
                    if sub.type == "decorator":
                        decs.append(_node_text(sub, src_bytes))
                    elif sub.type in ("function_definition", "async_function_definition", "class_definition"):
                        definition = sub
                if definition is not None:
                    if definition.type in ("function_definition", "async_function_definition"):
                        process_fn(definition, decs, prefix=prefix)
                    elif definition.type == "class_definition":
                        handle_class(definition, decs)
            elif child.type in ("function_definition", "async_function_definition"):
                process_fn(child, list(class_decs or []), prefix=prefix)
            elif child.type == "class_definition" and not prefix:
                handle_class(child, [])

    def handle_class(cls_node, cls_decs: List[str]) -> None:
        name_node = cls_node.child_by_field_name("name")
        body_node = cls_node.child_by_field_name("body")
        if name_node is None or body_node is None:
            return
        cls_name = _node_text(name_node, src_bytes)
        bases_node = cls_node.child_by_field_name("superclasses")
        bases_txt = _node_text(bases_node, src_bytes) if bases_node is not None else ""
        if not cls_name.startswith("Test") and "TestCase" not in bases_txt:
            return
        handle_block(body_node, class_decs=cls_decs, prefix=f"{cls_name}.")

    handle_block(root)
    return FileMetrics(cases=tuple(cases))


def _unquote_js_string(raw: str) -> Optional[str]:
    s = raw.strip()
    if len(s) >= 2 and s[0] in ("'", '"') and s[-1] == s[0]:
        return s[1:-1]
    if len(s) >= 2 and s[0] == "`" and s[-1] == "`" and "${" not in s:
        return s[1:-1]
    return None


def _analyze_js_ts_test_file(source: str, path: str) -> FileMetrics:
    src_bytes = source.replace("\r\n", "\n").encode("utf-8", errors="replace")
    lower = path.lower()
    if lower.endswith((".tsx", ".jsx")):
        lang_key = "tsx" if lower.endswith(".tsx") else "javascript"
    elif lower.endswith((".ts", ".mts", ".cts")):
        lang_key = "typescript"
    else:
        lang_key = "javascript"

    parser = _get_parser(lang_key)
    tree = parser.parse(src_bytes)
    cases: List[TestCaseMetric] = []

    def count_js_assertions(body_node) -> int:
        count = 0
        stack = [body_node]
        while stack:
            cur = stack.pop()
            if cur.type == "call_expression":
                fn = cur.child_by_field_name("function")
                if fn is not None:
                    fn_txt = _node_text(fn, src_bytes).strip()
                    if fn_txt == "expect":
                        # Exclude expect(...) inside expect.assertions / expect.hasAssertions? That's member_expression below.
                        count += 1
                    elif fn_txt == "assert" or (fn_txt.startswith("assert.") and not fn_txt.startswith("expect.")):
                        count += 1
            for child in reversed(cur.children):
                stack.append(child)
        return count

    def parse_callee_kind(fn_node) -> Tuple[str, str, bool]:
        """
        Return (role: 'describe'|'test'|'', skipped: 'none'|'unconditional', focused: bool).
        Handles it, test, it.skip, test.skip, xit, xtest, it.only, test.only, fit,
        it.each(...)('title', fn), describe, describe.skip, xdescribe, describe.only, fdescribe, it.todo.
        """
        txt = re.sub(r"\s+", "", _node_text(fn_node, src_bytes))
        # Strip .each(...) invocation if present: e.g. it.each([...]) -> it
        each_base = re.sub(r"\.each\([^)]*\)$", "", txt)
        if fn_node.type == "call_expression":
            inner_fn = fn_node.child_by_field_name("function")
            if inner_fn is not None:
                inner_txt = re.sub(r"\s+", "", _node_text(inner_fn, src_bytes))
                if inner_txt.endswith(".each"):
                    each_base = inner_txt[: -len(".each")]

        if each_base in ("describe",):
            return "describe", "none", False
        if each_base in ("describe.skip", "xdescribe"):
            return "describe", "unconditional", False
        if each_base in ("describe.only", "fdescribe"):
            return "describe", "none", True
        if each_base in ("it", "test"):
            return "test", "none", False
        if each_base in ("it.skip", "test.skip", "xit", "xtest", "it.todo", "test.todo"):
            return "test", "unconditional", False
        if each_base in ("it.only", "test.only", "fit"):
            return "test", "none", True
        return "", "none", False

    def walk(node, describe_titles: List[str], inherited_skip: str, inherited_focus: bool) -> None:
        if node.type == "call_expression":
            fn_node = node.child_by_field_name("function")
            args_node = node.child_by_field_name("arguments")
            if fn_node is not None and args_node is not None:
                role, sk, foc = parse_callee_kind(fn_node)
                arg_nodes = [c for c in args_node.children if c.type not in ("(", ")", ",")]
                if role == "describe" and len(arg_nodes) >= 2:
                    title = _unquote_js_string(_node_text(arg_nodes[0], src_bytes)) or f"<dynamic@L{node.start_point[0]+1}>"
                    cb = arg_nodes[1]
                    next_skip = "unconditional" if (inherited_skip == "unconditional" or sk == "unconditional") else "none"
                    walk(cb, describe_titles + [title], next_skip, inherited_focus or foc)
                    return
                if role == "test" and len(arg_nodes) >= 1:
                    raw_t = _unquote_js_string(_node_text(arg_nodes[0], src_bytes))
                    title = raw_t if raw_t is not None else f"<dynamic@L{node.start_point[0]+1}>"
                    full_name = " > ".join(describe_titles + [title]) if describe_titles else title
                    cb = next((a for a in reversed(arg_nodes) if a.type in ("arrow_function", "function_expression", "function")), None)
                    assertions = count_js_assertions(cb) if cb is not None else 0
                    b_hash = _body_hash(cb, src_bytes) if cb is not None else hashlib.sha256(full_name.encode()).hexdigest()[:16]
                    final_skip = "unconditional" if (inherited_skip == "unconditional" or sk == "unconditional") else "none"
                    cases.append(
                        TestCaseMetric(
                            name=full_name,
                            assertions=assertions,
                            skipped=final_skip,  # type: ignore[arg-type]
                            focused=inherited_focus or foc,
                            body_hash=b_hash,
                            line=node.start_point[0] + 1,
                        )
                    )
                    return

        for child in node.children:
            walk(child, describe_titles, inherited_skip, inherited_focus)

    walk(tree.root_node, [], "none", False)
    return FileMetrics(cases=tuple(cases))


def extract_test_file_metrics(path: str, content: Optional[str]) -> FileMetrics:
    """Extract normalized TestCaseMetrics for Python or JS/TS test files."""
    if content is None:
        return FileMetrics(metrics_unavailable=True)
    if len(content.encode("utf-8", errors="replace")) > MAX_TEST_FILE_BYTES:
        return FileMetrics(metrics_unavailable=True)
    lang = language_of(path)
    if lang == "python":
        return _analyze_python_test_file(content)
    if lang in ("javascript", "typescript"):
        return _analyze_js_ts_test_file(content, path)
    return FileMetrics(unsupported_framework=True)
