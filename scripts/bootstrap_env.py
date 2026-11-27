"""
Generate runtime secret values (`ADMIN_TOKEN`, `COOKIE_SECRET`) directly into a
0600 env file without echoing any secret values to stdout.
"""

from __future__ import annotations

import argparse
import os
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def bootstrap_env_file(env_path: Path, *, public_base_url: str = "https://coditt.xyz") -> list[str]:
    existing_lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    kv: dict[str, str] = {}
    for line in existing_lines:
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        kv[k.strip()] = v.strip()

    written: list[str] = []
    if not kv.get("ADMIN_TOKEN"):
        kv["ADMIN_TOKEN"] = secrets.token_urlsafe(32)
        written.append("ADMIN_TOKEN")
    if not kv.get("COOKIE_SECRET"):
        kv["COOKIE_SECRET"] = secrets.token_urlsafe(32)
        written.append("COOKIE_SECRET")
    if not kv.get("PUBLIC_BASE_URL"):
        kv["PUBLIC_BASE_URL"] = public_base_url
        written.append("PUBLIC_BASE_URL")

    env_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(env_path), os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        for k, v in kv.items():
            fh.write(f"{k}={v}\n")
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap local 0600 env file without printing secrets.")
    parser.add_argument("--env-file", default=str(ROOT / ".secrets" / "prod.env"))
    parser.add_argument("--public-base-url", default="https://coditt.xyz")
    args = parser.parse_args()
    keys = bootstrap_env_file(Path(args.env_file), public_base_url=args.public_base_url)
    print(f"Updated {args.env_file} (mode 0600); populated keys: {', '.join(keys) if keys else 'none (already set)'}")


if __name__ == "__main__":
    main()
