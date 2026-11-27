"""Detectors AGT-005 (trivially-true assertions, AST-level) & AGT-006 (loosened assertions)."""

from __future__ import annotations

import re
from typing import List, Optional, Set, Tuple

from codit_core.delta import CommitDelta, FileDelta
from codit_core.detectors.rules_catalog import make_core_finding
from codit_core.findings import CoreFinding
from codit_core.testmetrics import _get_parser, _node_text

_STRICT_REMOVED_RE = re.compile(
    r"(?:assertEqual|assertStrictEqual|assertIn|assert\s+.+==|\.toBe\(|\.toEqual\(|\.toStrictEqual\()"
)
_LOOSE_ADDED_RE = re.compile(
    r"(?:is\s+not\s+None|!=\s*None|\.toBeTruthy\(|\.toBeDefined\(|isinstance\([^,]+,\s*object\s*\))"
)


def _norm_expr(s: str) -> str:
    return re.sub(r"\s+", "", s).strip()


def _is_trivially_true_py_expr(node, src_bytes: bytes) -> Optional[str]:
    t = node.type
    txt = _node_text(node, src_bytes).strip()
    if t == "true":
        return "assert_true"
    if t == "integer":
        try:
            if int(txt, 0) != 0:
                return "assert_truthy_literal"
        except ValueError:
            pass
    if t == "string" and len(txt) >= 3:
        return "assert_string_literal"
    if t == "not_operator":
        arg = node.child_by_field_name("argument")
        if arg is not None and arg.type == "false":
            return "assert_not_false"
    if t == "boolean_operator":
        op = node.child_by_field_name("operator")
        right = node.child_by_field_name("right")
        left = node.child_by_field_name("left")
        if op is not None and _node_text(op, src_bytes).strip() == "or":
            if (right is not None and right.type == "true") or (left is not None and left.type == "true"):
                return "assert_or_true"
    if t == "comparison_operator":
        children = [c for c in node.children if c.type not in ("==", "!=")]
        if len(children) == 2 and any(c.type == "==" for c in node.children):
            if _norm_expr(_node_text(children[0], src_bytes)) == _norm_expr(_node_text(children[1], src_bytes)):
                return "assert_x_eq_x"
    return None


def _scan_python_line_ast(line_text: str) -> Optional[str]:
    stripped = line_text.strip()
    if not stripped or stripped.startswith("#"):
        return None
    src = stripped.encode("utf-8", errors="replace")
    tree = _get_parser("python").parse(src)
    for node in tree.root_node.children:
        if node.type == "assert_statement":
            exprs = [c for c in node.children if c.type not in ("assert", ",")]
            if exprs:
                form = _is_trivially_true_py_expr(exprs[0], src)
                if form:
                    return form
        elif node.type == "expression_statement":
            for sub in node.children:
                if sub.type == "call":
                    fn = sub.child_by_field_name("function")
                    args = sub.child_by_field_name("arguments")
                    if fn is None or args is None:
                        continue
                    fn_txt = _node_text(fn, src).strip()
                    arg_nodes = [a for a in args.children if a.type not in ("(", ")", ",")]
                    if fn_txt.endswith(".assertTrue") and arg_nodes:
                        if arg_nodes[0].type == "true":
                            return "assertTrue(True)"
                    if fn_txt.endswith(".assertEqual") and len(arg_nodes) >= 2:
                        if _norm_expr(_node_text(arg_nodes[0], src)) == _norm_expr(_node_text(arg_nodes[1], src)):
                            return "assertEqual(X, X)"
    return None


def _scan_js_line_ast(line_text: str, language: Optional[str]) -> Optional[str]:
    stripped = line_text.strip()
    if not stripped or stripped.startswith("//") or stripped.startswith("/*"):
        return None
    lang_key = "typescript" if language == "typescript" else "javascript"
    src = stripped.encode("utf-8", errors="replace")
    tree = _get_parser(lang_key).parse(src)

    stack = [tree.root_node]
    while stack:
        cur = stack.pop()
        if cur.type == "call_expression":
            fn = cur.child_by_field_name("function")
            args = cur.child_by_field_name("arguments")
            if fn is not None and fn.type == "member_expression" and args is not None:
                prop = fn.child_by_field_name("property")
                obj = fn.child_by_field_name("object")
                prop_name = _node_text(prop, src) if prop is not None else ""
                if obj is not None and obj.type == "call_expression":
                    exp_fn = obj.child_by_field_name("function")
                    exp_args = obj.child_by_field_name("arguments")
                    if exp_fn is not None and _node_text(exp_fn, src).strip() == "expect" and exp_args is not None:
                        exp_list = [a for a in exp_args.children if a.type not in ("(", ")", ",")]
                        matcher_list = [a for a in args.children if a.type not in ("(", ")", ",")]
                        if exp_list:
                            subject_txt = _norm_expr(_node_text(exp_list[0], src))
                            if prop_name == "toBeTruthy" and subject_txt == "true":
                                return "expect(true).toBeTruthy()"
                            if prop_name in ("toBe", "toEqual", "toStrictEqual") and matcher_list:
                                matcher_txt = _norm_expr(_node_text(matcher_list[0], src))
                                if subject_txt == "true" and matcher_txt == "true":
                                    return f"expect(true).{prop_name}(true)"
                                if subject_txt and subject_txt == matcher_txt:
                                    return f"expect(X).{prop_name}(X)"
        for ch in reversed(cur.children):
            stack.append(ch)
    return None


def detect_agt005_agt006(commit: CommitDelta) -> List[CoreFinding]:
    findings: List[CoreFinding] = []

    for f in commit.files:
        if f.kind != "test" and f.language not in ("python", "javascript", "typescript"):
            continue

        # AGT-005 on added lines in test files (or any python/js source file with added asserts)
        if f.kind == "test" or any("assert" in al.text or "expect(" in al.text for al in f.added):
            for al in f.added:
                if f.language == "python":
                    form = _scan_python_line_ast(al.text)
                elif f.language in ("javascript", "typescript"):
                    form = _scan_js_line_ast(al.text, f.language)
                else:
                    form = None
                if form:
                    findings.append(
                        make_core_finding(
                            rule_id="AGT-005",
                            evidence_file=f.path,
                            evidence_line=al.lineno,
                            confidence="high",
                            severity="high",
                            basis="AST PROOF",
                            commit_sha=commit.sha,
                            match_key=f"{f.path}:{form}:{al.text.strip()}",
                            params={
                                "short": commit.short,
                                "form": form,
                                "path": f.path,
                            },
                        )
                    )

        # AGT-006 heuristic: surviving test case with unchanged assertion count, strict removed -> loose added
        if (
            f.kind == "test"
            and f.before is not None
            and f.after is not None
            and not f.before.metrics_unavailable
            and not f.after.metrics_unavailable
        ):
            before_map = {c.name: c for c in f.before.cases}
            unchanged_count_cases = [
                c for c in f.after.cases
                if c.name in before_map and c.assertions == before_map[c.name].assertions and c.assertions > 0
            ]
            if unchanged_count_cases:
                removed_strict = any(_STRICT_REMOVED_RE.search(rl) for rl in f.removed_lines)
                loose_hits = [al for al in f.added if _LOOSE_ADDED_RE.search(al.text)]
                if removed_strict and loose_hits:
                    findings.append(
                        make_core_finding(
                            rule_id="AGT-006",
                            evidence_file=f.path,
                            evidence_line=loose_hits[0].lineno,
                            confidence="low",
                            severity="low",
                            basis="PATTERN",
                            commit_sha=commit.sha,
                            match_key=f"{f.path}:{loose_hits[0].text.strip()}",
                            params={
                                "short": commit.short,
                                "path": f.path,
                            },
                        )
                    )

    return findings
