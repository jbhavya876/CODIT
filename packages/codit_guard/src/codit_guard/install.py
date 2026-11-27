"""Installers for Claude Code PreToolUse hooks, native git hooks, and pre-commit."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from typing import Any, Dict, List

import yaml

CLAUDE_HOOK_COMMAND = "codit-guard hook claude-code"
CLAUDE_HOOK_MATCHER = "Edit|Write|MultiEdit|Bash"


def install_claude_code_hook(repo_root: Path) -> Path:
    """Safely merge CODIT PreToolUse hook into `.claude/settings.json` without clobbering."""
    settings_path = repo_root / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)

    data: Dict[str, Any] = {}
    if settings_path.exists():
        try:
            loaded = json.loads(settings_path.read_text(encoding="utf-8-sig"))
            if isinstance(loaded, dict):
                data = loaded
        except json.JSONDecodeError:
            data = {}

    hooks = data.setdefault("hooks", {})
    pre_tool = hooks.setdefault("PreToolUse", [])
    if not isinstance(pre_tool, list):
        pre_tool = []
        hooks["PreToolUse"] = pre_tool

    # Check if command is already registered
    already_present = False
    for entry in pre_tool:
        if isinstance(entry, dict):
            for h in entry.get("hooks", []) or []:
                if isinstance(h, dict) and h.get("command") == CLAUDE_HOOK_COMMAND:
                    already_present = True
                    break

    if not already_present:
        pre_tool.append({
            "matcher": CLAUDE_HOOK_MATCHER,
            "hooks": [
                {
                    "type": "command",
                    "command": CLAUDE_HOOK_COMMAND,
                    "timeout": 10,
                }
            ],
        })

    settings_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return settings_path


def install_git_pre_commit_hook(repo_root: Path) -> Path:
    """Install native `.git/hooks/pre-commit` calling `codit-guard check --staged`."""
    hooks_dir = repo_root / ".git" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    hook_path = hooks_dir / "pre-commit"

    marker = "# codit-guard pre-commit"
    snippet = f"{marker}\ncodit-guard check --staged || exit $?\n"

    if hook_path.exists():
        existing = hook_path.read_text(encoding="utf-8", errors="replace")
        if marker not in existing:
            hook_path.write_text(existing.rstrip() + "\n\n" + snippet, encoding="utf-8")
    else:
        hook_path.write_text("#!/bin/sh\n" + snippet, encoding="utf-8")

    try:
        cur_mode = hook_path.stat().st_mode
        hook_path.chmod(cur_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except OSError:
        pass
    return hook_path


def install_pre_commit_config(repo_root: Path) -> Path:
    """Create or merge `.pre-commit-config.yaml` pointing to codit-guard hook."""
    cfg_path = repo_root / ".pre-commit-config.yaml"
    doc: Dict[str, Any] = {"repos": []}
    if cfg_path.exists():
        try:
            loaded = yaml.safe_load(cfg_path.read_text(encoding="utf-8-sig"))
            if isinstance(loaded, dict) and isinstance(loaded.get("repos"), list):
                doc = loaded
        except yaml.YAMLError:
            pass

    repos: List[Dict[str, Any]] = doc["repos"]
    has_codit = any(
        isinstance(r, dict) and any(h.get("id") == "codit-guard" for h in (r.get("hooks") or []) if isinstance(h, dict))
        for r in repos
    )
    if not has_codit:
        repos.append({
            "repo": "local",
            "hooks": [
                {
                    "id": "codit-guard",
                    "name": "codit-guard (staged diff verification check)",
                    "entry": "codit-guard check --staged",
                    "language": "system",
                    "pass_filenames": False,
                    "stages": ["pre-commit"],
                }
            ],
        })
    cfg_path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    return cfg_path
