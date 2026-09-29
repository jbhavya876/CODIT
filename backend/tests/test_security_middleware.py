"""
Tests for the CODIT security middleware stack.

Strategy:
  - All tests that are NOT testing the rate limiter use `rl_off_client`
    (rate limiting disabled via env var) to avoid interfering with other test
    suites that run in the same process and share the in-memory bucket state.
  - Rate limiter tests use a dedicated `rl_client` with RATE_LIMIT_ENABLED=true
    and use unique spoofed IPs (X-Forwarded-For) to get fresh isolated buckets.
    The limit (3/min) is enforced only by hitting the same IP 4 times.
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Ensure repo root is on sys.path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Keep general env clean — do not set RATE_LIMIT_GENERAL_RPM here.
# Individual fixtures manage the enabled/disabled state.
os.environ["RATE_LIMIT_ENABLED"] = "false"

from backend.app import create_app  # noqa: E402


def unique_ip() -> str:
    """Return a unique spoofed IP so each bucket test starts fresh."""
    n = uuid.uuid4().int
    return f"{10 + (n % 200)}.{n % 256}.{(n >> 8) % 256}.{(n >> 16) % 256}"


@pytest.fixture(scope="module")
def rl_off_client():
    """TestClient with rate limiting DISABLED — safe for any number of requests."""
    os.environ["RATE_LIMIT_ENABLED"] = "false"
    app = create_app()
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    # Restore default (was already false; restore for consistency)
    os.environ["RATE_LIMIT_ENABLED"] = "false"


@pytest.fixture(scope="module")
def rl_client():
    """TestClient with rate limiting ENABLED at the default production limits.

    Tests that use this fixture MUST use unique X-Forwarded-For IPs via
    unique_ip() to get isolated per-IP buckets.
    """
    os.environ["RATE_LIMIT_ENABLED"] = "true"
    app = create_app()
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    os.environ["RATE_LIMIT_ENABLED"] = "false"


# ---------------------------------------------------------------------------
# Security Headers
# ---------------------------------------------------------------------------

class TestSecurityHeaders:
    def test_x_content_type_options(self, rl_off_client):
        r = rl_off_client.get("/api/health")
        assert r.headers.get("x-content-type-options") == "nosniff"

    def test_x_frame_options(self, rl_off_client):
        r = rl_off_client.get("/api/health")
        assert r.headers.get("x-frame-options") == "DENY"

    def test_referrer_policy(self, rl_off_client):
        r = rl_off_client.get("/api/health")
        assert r.headers.get("referrer-policy") == "strict-origin-when-cross-origin"

    def test_csp_present(self, rl_off_client):
        r = rl_off_client.get("/api/health")
        assert "content-security-policy" in r.headers

    def test_csp_pera_connect_compatible(self, rl_off_client):
        """Verify CSP allows Pera Connect websocket bridge and SVG data: URI image generation."""
        r = rl_off_client.get("/api/health")
        csp = r.headers.get("content-security-policy", "")
        assert "wss://*.perawallet.app" in csp
        assert "https://*.perawallet.app" in csp
        assert "data:" in csp
        assert "blob:" in csp
        assert "https://*.algonode.cloud" in csp

    def test_xss_protection(self, rl_off_client):
        r = rl_off_client.get("/api/health")
        assert r.headers.get("x-xss-protection") == "1; mode=block"

    def test_permissions_policy(self, rl_off_client):
        r = rl_off_client.get("/api/health")
        assert "permissions-policy" in r.headers


# ---------------------------------------------------------------------------
# Rate Limiter
# ---------------------------------------------------------------------------

class TestRateLimiter:
    """All tests use unique IPs to get isolated buckets and avoid cross-test pollution."""

    def test_within_limit_succeeds(self, rl_client):
        """Requests under the general limit (120/min default) should succeed."""
        ip = unique_ip()
        headers = {"X-Forwarded-For": ip}
        for _ in range(5):
            r = rl_client.get("/api/health", headers=headers)
            assert r.status_code == 200, f"Expected 200 got {r.status_code}: {r.text}"

    def test_exceeds_ingest_limit_returns_429(self, rl_client):
        """Ingest limit is 10/min. Exhaust it with a unique IP and verify 429."""
        ip = unique_ip()
        headers = {"X-Forwarded-For": ip}
        limit = int(os.environ.get("RATE_LIMIT_INGEST_RPM", "10"))
        for _ in range(limit):
            rl_client.post("/api/ingest/public", json={"url": "https://github.com/x/y"}, headers=headers)
        # Next request should be rate-limited
        r = rl_client.post("/api/ingest/public", json={"url": "https://github.com/x/y"}, headers=headers)
        assert r.status_code == 429, f"Expected 429 got {r.status_code}"
        body = r.json()
        assert body["error"]["code"] == "rate_limited"

    def test_retry_after_header_present(self, rl_client):
        """429 responses must include a Retry-After header."""
        ip = unique_ip()
        headers = {"X-Forwarded-For": ip}
        limit = int(os.environ.get("RATE_LIMIT_INGEST_RPM", "10"))
        for _ in range(limit):
            rl_client.post("/api/ingest/public", json={"url": "https://github.com/x/y"}, headers=headers)
        r = rl_client.post("/api/ingest/public", json={"url": "https://github.com/x/y"}, headers=headers)
        assert r.status_code == 429
        assert "retry-after" in r.headers
        assert int(r.headers["retry-after"]) > 0

    def test_different_ips_are_isolated(self, rl_client):
        """Each IP gets its own bucket — unique IPs should all succeed independently."""
        for _ in range(10):
            ip = unique_ip()
            headers = {"X-Forwarded-For": ip}
            r = rl_client.get("/api/health", headers=headers)
            assert r.status_code == 200


# ---------------------------------------------------------------------------
# Request Guard — Body Size
# ---------------------------------------------------------------------------

class TestRequestBodySizeGuard:
    def test_normal_body_accepted(self, rl_off_client):
        """Small payload passes — route may fail for other reasons, but NOT 413."""
        r = rl_off_client.post(
            "/api/ingest/public",
            json={"url": "https://github.com/test/repo"},
        )
        assert r.status_code != 413

    def test_oversized_content_length_rejected(self, rl_off_client):
        """A request claiming 60 MB body is rejected before routing."""
        sixty_mb = 60 * 1024 * 1024
        r = rl_off_client.get(
            "/api/health",
            headers={"Content-Length": str(sixty_mb)},
        )
        assert r.status_code == 413
        assert r.json()["error"]["code"] == "request_too_large"


# ---------------------------------------------------------------------------
# Ingest URL Validation
# ---------------------------------------------------------------------------

class TestIngestURLValidation:
    def test_valid_github_url_passes_validation(self, rl_off_client):
        r = rl_off_client.post(
            "/api/ingest/public",
            json={"url": "https://github.com/owner/repo"},
        )
        # May fail for network reasons, but NOT with invalid_url
        assert r.json().get("error", {}).get("code") != "invalid_url"

    def test_javascript_url_rejected(self, rl_off_client):
        r = rl_off_client.post(
            "/api/ingest/public",
            json={"url": "javascript:alert(1)"},
        )
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "invalid_url"

    def test_http_url_rejected(self, rl_off_client):
        r = rl_off_client.post(
            "/api/ingest/public",
            json={"url": "http://github.com/owner/repo"},
        )
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "invalid_url"

    def test_arbitrary_domain_rejected(self, rl_off_client):
        r = rl_off_client.post(
            "/api/ingest/public",
            json={"url": "https://evil.com/path/to/thing"},
        )
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "invalid_url"

    def test_data_url_rejected(self, rl_off_client):
        r = rl_off_client.post(
            "/api/ingest/public",
            json={"url": "data:text/html,<h1>XSS</h1>"},
        )
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "invalid_url"


# ---------------------------------------------------------------------------
# ZIP Upload Size Validation
# ---------------------------------------------------------------------------

class TestZipSizeValidation:
    def test_oversized_zip_rejected(self, rl_off_client):
        """A ZIP larger than MAX_INDIVIDUAL_FILE_MB (default 5 MB) should 413."""
        big_content = b"PK" + b"\x00" * (6 * 1024 * 1024)  # ~6 MB fake zip
        r = rl_off_client.post(
            "/api/ingest/zip",
            files={"file": ("repo.zip", big_content, "application/zip")},
        )
        assert r.status_code == 413
        assert r.json()["error"]["code"] == "file_too_large"

    def test_non_zip_file_rejected(self, rl_off_client):
        r = rl_off_client.post(
            "/api/ingest/zip",
            files={"file": ("repo.tar.gz", b"\x00", "application/gzip")},
        )
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "invalid_file"
