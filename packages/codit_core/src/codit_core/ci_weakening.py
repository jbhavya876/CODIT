"""GitHub Actions CI weakening (AGT-007) and quality gate lowering (AGT-008) detection."""

from __future__ import annotations

import configparser
import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import yaml

try:
    import tomllib  # Python 3.11+
except ImportError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

MAX_CI_FILE_BYTES = 128 * 1024

_STEP_CLASSES: List[Tuple[str, re.Pattern[str]]] = [
    (
        "test",
        re.compile(
            r"\b(pytest|py\.test|tox|nox|unittest|jest|vitest|mocha|ava|cypress run|playwright test|npm (run )?test|yarn test|pnpm( run)? test|go test|cargo test)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "lint",
        re.compile(
            r"\b(ruff|flake8|pylint|eslint|stylelint|prettier\s+--check|black\s+--check|isort\s+--check)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "typecheck",
        re.compile(r"\b(mypy|pyright|tsc(\s|$)|pytype)\b", re.IGNORECASE),
    ),
    (
        "audit",
        re.compile(
            r"\b(pip-audit|npm audit|yarn audit|safety check|trivy|semgrep|bandit|gitleaks|trufflehog|codeql|osv-scanner)\b",
            re.IGNORECASE,
        ),
    ),
]

_SWALLOW_RE = re.compile(
    r"(?:\|\|\s*(?:true|exit\s+0|:)\b|;\s*true\s*$|--passWithNoTests|--exit-zero)",
    re.IGNORECASE,
)
_COV_FAIL_UNDER_RE = re.compile(r"--cov-fail-under(?:=|\s+)(\d+(?:\.\d+)?)")


@dataclass(frozen=True)
class CiStepInfo:
    workflow: str
    job_id: str
    step_key: str
    step_class: str
    continue_on_error: bool
    if_false: bool
    swallows_error: bool
    cov_fail_under: Optional[float]


@dataclass(frozen=True)
class CiWeakeningEvent:
    rule_id: str  # "AGT-007" | "AGT-008"
    path: str
    change: str
    step_class: str = "test"
    severity: str = "high"


def _classify_step_text(step: Dict[str, Any]) -> Optional[str]:
    combined = " ".join(
        str(step.get(k) or "")
        for k in ("run", "name", "uses")
    )
    for cls_name, pat in _STEP_CLASSES:
        if pat.search(combined):
            return cls_name
    return None


def _is_if_false(val: Any) -> bool:
    if val is False:
        return True
    if isinstance(val, str):
        cleaned = val.strip().lower().replace("${{", "").replace("}}", "").strip()
        return cleaned == "false"
    return False


def extract_github_workflow_steps(path: str, text: Optional[str]) -> List[CiStepInfo]:
    if not text or len(text.encode("utf-8", errors="replace")) > MAX_CI_FILE_BYTES:
        return []
    try:
        doc = yaml.safe_load(text)
    except yaml.YAMLError:
        return []
    if not isinstance(doc, dict):
        return []
    jobs = doc.get("jobs")
    if not isinstance(jobs, dict):
        return []

    steps_out: List[CiStepInfo] = []
    for job_id, job in jobs.items():
        if not isinstance(job, dict):
            continue
        job_coe = bool(job.get("continue-on-error") is True)
        job_if_false = _is_if_false(job.get("if"))
        raw_steps = job.get("steps")
        if not isinstance(raw_steps, list):
            continue
        for idx, step in enumerate(raw_steps):
            if not isinstance(step, dict):
                continue
            cls_name = _classify_step_text(step)
            if not cls_name:
                continue
            run_str = str(step.get("run") or "")
            step_coe = job_coe or bool(step.get("continue-on-error") is True)
            step_if_false = job_if_false or _is_if_false(step.get("if"))
            swallows = bool(_SWALLOW_RE.search(run_str))
            cov_match = _COV_FAIL_UNDER_RE.search(run_str)
            cov_val = float(cov_match.group(1)) if cov_match else None
            step_key = f"{job_id}:{step.get('id') or step.get('name') or cls_name}:{idx}"
            steps_out.append(
                CiStepInfo(
                    workflow=path,
                    job_id=str(job_id),
                    step_key=step_key,
                    step_class=cls_name,
                    continue_on_error=step_coe,
                    if_false=step_if_false,
                    swallows_error=swallows,
                    cov_fail_under=cov_val,
                )
            )
    return steps_out


def analyze_github_workflow_changes(
    workflow_deltas: List[Tuple[str, str, Optional[str], Optional[str]]],
    before_all_workflows: Optional[Dict[str, str]] = None,
    after_all_workflows: Optional[Dict[str, str]] = None,
) -> List[CiWeakeningEvent]:
    """
    Analyze `.github/workflows/*.y*ml` changes in a commit/PR for AGT-007 (and CI cov-fail-under AGT-008).
    workflow_deltas: list of (status, path, before_text, after_text).
    """
    events: List[CiWeakeningEvent] = []
    after_steps_all: List[CiStepInfo] = []
    if after_all_workflows:
        for wp, wt in after_all_workflows.items():
            after_steps_all.extend(extract_github_workflow_steps(wp, wt))

    for status, path, before_text, after_text in workflow_deltas:
        b_steps = extract_github_workflow_steps(path, before_text)
        a_steps = extract_github_workflow_steps(path, after_text)
        if not after_all_workflows:
            after_steps_all.extend(a_steps)

        if status == "D" and b_steps:
            # Check if every removed step class still exists across remaining/added workflows
            after_classes = {s.step_class for s in after_steps_all}
            missing_classes = {s.step_class for s in b_steps} - after_classes
            if missing_classes:
                for mc in sorted(missing_classes):
                    events.append(
                        CiWeakeningEvent(
                            rule_id="AGT-007",
                            path=path,
                            step_class=mc,
                            change="workflow_deleted",
                            severity="high",
                        )
                    )
            continue

        # Pair steps by (job_id, step_class) with fallback on index
        used_after: set[int] = set()
        for bs in b_steps:
            matched_idx: Optional[int] = None
            for idx, as_ in enumerate(a_steps):
                if idx in used_after:
                    continue
                if as_.job_id == bs.job_id and as_.step_class == bs.step_class:
                    matched_idx = idx
                    break
            if matched_idx is None:
                # Check if class still present anywhere in after workflows (avoid false positive on step move)
                still_anywhere = any(s.step_class == bs.step_class for s in after_steps_all)
                if not still_anywhere:
                    events.append(
                        CiWeakeningEvent(
                            rule_id="AGT-007",
                            path=path,
                            step_class=bs.step_class,
                            change="step_removed",
                            severity="high",
                        )
                    )
                continue

            used_after.add(matched_idx)
            as_ = a_steps[matched_idx]
            if not bs.continue_on_error and as_.continue_on_error:
                events.append(
                    CiWeakeningEvent(
                        rule_id="AGT-007",
                        path=path,
                        step_class=bs.step_class,
                        change="continue-on-error: true",
                        severity="high",
                    )
                )
            if not bs.swallows_error and as_.swallows_error:
                events.append(
                    CiWeakeningEvent(
                        rule_id="AGT-007",
                        path=path,
                        step_class=bs.step_class,
                        change="exit-code swallowed",
                        severity="high",
                    )
                )
            if not bs.if_false and as_.if_false:
                events.append(
                    CiWeakeningEvent(
                        rule_id="AGT-007",
                        path=path,
                        step_class=bs.step_class,
                        change="if: false guard added",
                        severity="high",
                    )
                )
            if bs.cov_fail_under is not None and (as_.cov_fail_under is None or as_.cov_fail_under < bs.cov_fail_under):
                events.append(
                    CiWeakeningEvent(
                        rule_id="AGT-008",
                        path=path,
                        step_class="test",
                        change=f"cov-fail-under {bs.cov_fail_under:g} -> {as_.cov_fail_under if as_.cov_fail_under is not None else 'removed'}",
                        severity="medium",
                    )
                )

        # Also catch brand-new weakened steps in newly added workflows/steps
        for idx, as_ in enumerate(a_steps):
            if idx in used_after:
                continue
            if as_.continue_on_error:
                events.append(
                    CiWeakeningEvent(
                        rule_id="AGT-007",
                        path=path,
                        step_class=as_.step_class,
                        change="continue-on-error: true",
                        severity="high",
                    )
                )
            if as_.swallows_error:
                events.append(
                    CiWeakeningEvent(
                        rule_id="AGT-007",
                        path=path,
                        step_class=as_.step_class,
                        change="exit-code swallowed",
                        severity="high",
                    )
                )

    return events


def _eslint_rank(val: Any) -> Optional[int]:
    if isinstance(val, list) and val:
        val = val[0]
    if val in (0, "off"):
        return 0
    if val in (1, "warn"):
        return 1
    if val in (2, "error"):
        return 2
    return None


def analyze_gate_config_change(
    path: str,
    before_text: Optional[str],
    after_text: Optional[str],
) -> Tuple[List[CiWeakeningEvent], Optional[str]]:
    """
    Compare quality gate thresholds/severities statically for AGT-008.
    Returns (events, optional_note_code) — executable JS configs yield 'unsupported', never a guess.
    """
    norm = path.replace("\\", "/").lower()
    fname = norm.rsplit("/", 1)[-1]
    if not before_text or not after_text:
        return [], None

    if fname.endswith((".js", ".cjs", ".mjs", ".ts")):
        return [], "unsupported_executable_gate_config"

    events: List[CiWeakeningEvent] = []

    if fname == "pyproject.toml":
        try:
            b_doc = tomllib.loads(before_text)
            a_doc = tomllib.loads(after_text)
            b_fu = b_doc.get("tool", {}).get("coverage", {}).get("report", {}).get("fail_under")
            a_fu = a_doc.get("tool", {}).get("coverage", {}).get("report", {}).get("fail_under")
            if isinstance(b_fu, (int, float)) and isinstance(a_fu, (int, float)) and a_fu < b_fu:
                events.append(CiWeakeningEvent("AGT-008", path, f"coverage.fail_under {b_fu} -> {a_fu}", severity="medium"))
            elif isinstance(b_fu, (int, float)) and a_fu is None:
                events.append(CiWeakeningEvent("AGT-008", path, f"coverage.fail_under {b_fu} removed", severity="medium"))
        except Exception:
            pass
        return events, None

    if fname == ".coveragerc":
        try:
            bp = configparser.ConfigParser()
            ap = configparser.ConfigParser()
            bp.read_string(before_text)
            ap.read_string(after_text)
            if bp.has_option("report", "fail_under"):
                b_fu = float(bp.get("report", "fail_under"))
                if not ap.has_option("report", "fail_under"):
                    events.append(CiWeakeningEvent("AGT-008", path, f"fail_under {b_fu:g} removed", severity="medium"))
                else:
                    a_fu = float(ap.get("report", "fail_under"))
                    if a_fu < b_fu:
                        events.append(CiWeakeningEvent("AGT-008", path, f"fail_under {b_fu:g} -> {a_fu:g}", severity="medium"))
        except Exception:
            pass
        return events, None

    if fname == "tsconfig.json":
        try:
            b_json = json.loads(before_text)
            a_json = json.loads(after_text)
            b_strict = b_json.get("compilerOptions", {}).get("strict")
            a_strict = a_json.get("compilerOptions", {}).get("strict")
            if b_strict is True and a_strict is False:
                events.append(CiWeakeningEvent("AGT-008", path, "tsconfig strict true -> false", severity="medium"))
        except Exception:
            pass
        return events, None

    if fname in ("package.json", "jest.config.json"):
        try:
            b_json = json.loads(before_text)
            a_json = json.loads(after_text)
            b_ct = b_json.get("jest", {}).get("coverageThreshold", b_json.get("coverageThreshold", {}))
            a_ct = a_json.get("jest", {}).get("coverageThreshold", a_json.get("coverageThreshold", {}))
            if isinstance(b_ct, dict) and isinstance(a_ct, dict):
                b_glob = b_ct.get("global", {})
                a_glob = a_ct.get("global", {})
                if isinstance(b_glob, dict):
                    for metric, b_val in b_glob.items():
                        a_val = a_glob.get(metric) if isinstance(a_glob, dict) else None
                        if isinstance(b_val, (int, float)) and (
                            a_val is None or (isinstance(a_val, (int, float)) and a_val < b_val)
                        ):
                            events.append(
                                CiWeakeningEvent(
                                    "AGT-008",
                                    path,
                                    f"jest.coverageThreshold.{metric} {b_val} -> {a_val}",
                                    severity="medium",
                                )
                            )
        except Exception:
            pass
        return events, None

    if fname.startswith(".eslintrc"):
        try:
            b_doc = yaml.safe_load(before_text) or {}
            a_doc = yaml.safe_load(after_text) or {}
            b_rules = b_doc.get("rules", {}) if isinstance(b_doc, dict) else {}
            a_rules = a_doc.get("rules", {}) if isinstance(a_doc, dict) else {}
            if isinstance(b_rules, dict) and isinstance(a_rules, dict):
                for rule_name, b_val in b_rules.items():
                    b_rank = _eslint_rank(b_val)
                    a_rank = _eslint_rank(a_rules.get(rule_name)) if rule_name in a_rules else 0
                    if b_rank is not None and a_rank is not None and a_rank < b_rank:
                        events.append(
                            CiWeakeningEvent(
                                "AGT-008",
                                path,
                                f"eslint {rule_name} severity {b_rank} -> {a_rank}",
                                severity="medium",
                            )
                        )
        except Exception:
            pass
        return events, None

    return [], None
