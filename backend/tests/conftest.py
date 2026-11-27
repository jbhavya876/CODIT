"""
Pytest configuration for the CODIT backend test suite.

Global test environment setup:
  - Rate limiting is DISABLED by default so all existing tests can make
    multiple requests without hitting the in-process sliding-window buckets.
  - Individual test modules (e.g., test_security_middleware.py) that want to
    test rate-limiting behaviour re-enable it through their own fixtures.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_REPO_ROOT = str(Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


def pytest_configure(config):
    """Disable rate limiting for the whole test session by default."""
    os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
    config.addinivalue_line("markers", "perf: performance benchmark tests")
