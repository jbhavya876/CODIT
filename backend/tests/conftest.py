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


def pytest_configure(config):
    """Disable rate limiting for the whole test session by default."""
    os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
