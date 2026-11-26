"""Test-only deterministic git repository builder for P1/P2/P3 scenarios and adversarial tests."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Dict, Optional


class GitRepoBuilder:
    """Builds isolated deterministic git repositories in temporary directories."""

    def __init__(self, root: Path, default_branch: str = "main"):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._tick = 0
        self._git(["init", "-b", default_branch])
        self._git(["config", "user.name", "Test Author"])
        self._git(["config", "user.email", "author@example.test"])

    def _git(self, args: list[str], extra_env: Optional[Dict[str, str]] = None) -> str:
        env = os.environ.copy()
        env["GIT_CONFIG_NOSYSTEM"] = "1"
        env["GIT_CONFIG_GLOBAL"] = os.devnull
        if extra_env:
            env.update(extra_env)
        proc = subprocess.run(
            ["git", *args],
            cwd=str(self.root),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.decode('utf-8', 'replace')}")
        return proc.stdout.decode("utf-8", "replace").strip()

    def write(self, rel_path: str, content: str | bytes) -> Path:
        target = self.root / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            target.write_bytes(content)
        else:
            target.write_text(content, encoding="utf-8", newline="\n")
        return target

    def remove(self, rel_path: str) -> None:
        target = self.root / rel_path
        if target.exists():
            target.unlink()

    def commit(
        self,
        message: str,
        *,
        author_name: str = "Test Author",
        author_email: str = "author@example.test",
        days_ago: Optional[int] = None,
    ) -> str:
        self._tick += 1
        ts = 1764000000 + (self._tick * 60)
        if days_ago is not None:
            ts = 1764200000 - (days_ago * 86400)
        date_str = f"{ts} +0000"
        env = {
            "GIT_AUTHOR_NAME": author_name,
            "GIT_AUTHOR_EMAIL": author_email,
            "GIT_COMMITTER_NAME": author_name,
            "GIT_COMMITTER_EMAIL": author_email,
            "GIT_AUTHOR_DATE": date_str,
            "GIT_COMMITTER_DATE": date_str,
        }
        self._git(["add", "-A"], extra_env=env)
        self._git(["commit", "--allow-empty", "-m", message], extra_env=env)
        return self._git(["rev-parse", "HEAD"])
