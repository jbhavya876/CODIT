"""Application configuration, sourced entirely from environment variables."""

from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

root_env = Path(__file__).resolve().parents[2] / ".env"
backend_env = Path(__file__).resolve().parents[1] / ".env"
for env_path in (root_env, backend_env):
    if env_path.exists():
        load_dotenv(env_path)

_REPO_ROOT = Path(__file__).resolve().parents[2]


class Config:
    # Runtime environment & database
    ENV = os.getenv("ENV", "development").lower()
    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{(_REPO_ROOT / '.data' / 'codit.db').as_posix()}",
    )
    JOB_WORKERS = int(os.getenv("JOB_WORKERS", "2"))

    # "cognodb"   -> connect to CognoDB (requires COGNODB_*)
    # "demo"      -> embedded in-memory dataset (offline development / tests)
    # "auto"      -> use CognoDB when COGNODB_URI is set, otherwise demo
    GRAPH_BACKEND = os.getenv("GRAPH_BACKEND", "auto")

    COGNODB_URI = os.getenv("COGNODB_URI", "")
    COGNODB_USERNAME = os.getenv("COGNODB_USERNAME", "cognodb")
    COGNODB_PASSWORD = os.getenv("COGNODB_PASSWORD", "")

    # Depth guardrail for variable-length traversals
    IMPACT_MAX_DEPTH = int(os.getenv("IMPACT_MAX_DEPTH", "6"))

    # GitHub integration & Ingestion limits
    GITHUB_APP_ID = os.getenv("GITHUB_APP_ID", "")
    GITHUB_APP_PRIVATE_KEY = os.getenv("GITHUB_APP_PRIVATE_KEY", "")
    GITHUB_API_TOKEN = os.getenv("GITHUB_API_TOKEN", "")
    MAX_REPO_SIZE_MB = int(os.getenv("MAX_REPO_SIZE_MB", "200"))
    MAX_FILE_COUNT = int(os.getenv("MAX_FILE_COUNT", "5000"))
    MAX_INDIVIDUAL_FILE_MB = int(os.getenv("MAX_INDIVIDUAL_FILE_MB", "5"))
    INGESTION_TIMEOUT_SECONDS = int(os.getenv("INGESTION_TIMEOUT_SECONDS", "120"))

    # Security & Vulnerability Analysis
    OSV_API_URL = os.getenv("OSV_API_URL", "https://api.osv.dev/v1/query")
    DETECT_SECRETS_CONFIG = os.getenv("DETECT_SECRETS_CONFIG", "./config/secrets-baseline.json")

    # LLM Roadmap & Executive Narrative Synthesis
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    ROADMAP_MODEL = os.getenv("ROADMAP_MODEL", "claude-sonnet-5")
    EXEC_LLM_ENABLED = os.getenv("EXEC_LLM_ENABLED", "true").lower() != "false"

    # Worker Sandbox Resource Bounds
    SANDBOX_NETWORK_MODE = os.getenv("SANDBOX_NETWORK_MODE", "none")
    SANDBOX_CPU_LIMIT = int(os.getenv("SANDBOX_CPU_LIMIT", "1"))
    SANDBOX_MEMORY_LIMIT_MB = int(os.getenv("SANDBOX_MEMORY_LIMIT_MB", "1024"))
    SANDBOX_WALLTIME_SECONDS = int(os.getenv("SANDBOX_WALLTIME_SECONDS", "180"))

    # Data Retention, Staging & Cleanup
    AUDIT_RETENTION_HOURS = int(os.getenv("AUDIT_RETENTION_HOURS", os.getenv("REPORT_RETENTION_HOURS", "24")))
    REPORT_RETENTION_HOURS = AUDIT_RETENTION_HOURS
    STAGING_DIR = os.getenv("STAGING_DIR", (_REPO_ROOT / ".data" / "staging").as_posix())
    STAGING_TTL_MINUTES = int(os.getenv("STAGING_TTL_MINUTES", "15"))

    # History Ingestion Limits
    HISTORY_MAX_COMMITS = int(os.getenv("HISTORY_MAX_COMMITS", "500"))
    HISTORY_MAX_DAYS = int(os.getenv("HISTORY_MAX_DAYS", "365"))
    HISTORY_MAX_FILES_PER_COMMIT = int(os.getenv("HISTORY_MAX_FILES_PER_COMMIT", "200"))
    HISTORY_MAX_BLOB_KB = int(os.getenv("HISTORY_MAX_BLOB_KB", "1024"))
    HISTORY_TRANSFER_MAX_MB = int(os.getenv("HISTORY_TRANSFER_MAX_MB", "200"))
    HISTORY_WALLTIME_SECONDS = int(os.getenv("HISTORY_WALLTIME_SECONDS", "120"))
    HISTORY_MEM_MB = int(os.getenv("HISTORY_MEM_MB", "1024"))

    # License Lookup Controls
    DEPSDEV_BASE_URL = os.getenv("DEPSDEV_BASE_URL", "https://api.deps.dev").rstrip("/")
    LICENSE_LOOKUP_CONCURRENCY = int(os.getenv("LICENSE_LOOKUP_CONCURRENCY", "8"))
    LICENSE_LOOKUP_BUDGET_SECONDS = int(os.getenv("LICENSE_LOOKUP_BUDGET_SECONDS", "25"))

    # Attestations & Admin
    ATTESTATION_RETENTION_DAYS = int(os.getenv("ATTESTATION_RETENTION_DAYS", "30"))
    ATTEST_TTL_DAYS = int(os.getenv("ATTEST_TTL_DAYS", "90"))
    ATTEST_SIGNING_KEY = os.getenv("ATTEST_SIGNING_KEY", "")
    ATTEST_KEY_ID = os.getenv("ATTEST_KEY_ID", "")
    ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
    PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "https://coditt.xyz").rstrip("/")
    COOKIE_SECRET = os.getenv("COOKIE_SECRET", "")

    # x402 Algorand MainNet payment configuration.
    X402_FACILITATOR_URL = os.getenv("X402_FACILITATOR_URL", "").rstrip("/")
    X402_NETWORK = os.getenv(
        "X402_NETWORK",
        "algorand:wGHE2Pwdvd7S12BL5FaOP20EGYesN73ktiC1qzkkit8=",
    )
    X402_PAY_TO = os.getenv("X402_PAY_TO", "")
    X402_ASSET = os.getenv("X402_ASSET", "31566704")
    X402_AMOUNT = os.getenv("X402_AMOUNT", "1000000")
    X402_MAX_TIMEOUT_SECONDS = int(os.getenv("X402_MAX_TIMEOUT_SECONDS", "120"))
    X402_DECIMALS = int(os.getenv("X402_DECIMALS", "6"))
    X402_FEE_PAYER = os.getenv("X402_FEE_PAYER", "")
    X402_RESOURCE_URL = os.getenv("X402_RESOURCE_URL", "")

    # CORS
    _cors_raw = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:4173")
    CORS_ORIGINS: list[str] = [o.strip() for o in _cors_raw.split(",") if o.strip()]

    # Rate Limiting (sliding window, per IP, per route group)
    RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "true").lower() != "false"
    RATE_LIMIT_GENERAL_RPM = int(os.getenv("RATE_LIMIT_GENERAL_RPM", "120"))
    RATE_LIMIT_INGEST_RPM = int(os.getenv("RATE_LIMIT_INGEST_RPM", "10"))
    RATE_LIMIT_ANALYZE_RPM = int(os.getenv("RATE_LIMIT_ANALYZE_RPM", "4"))
    RATE_LIMIT_REPORT_RPM = int(os.getenv("RATE_LIMIT_REPORT_RPM", "20"))
    RATE_LIMIT_AUDITS_RPM = int(os.getenv("RATE_LIMIT_AUDITS_RPM", "4"))
    RATE_LIMIT_ATTEST_RPM = int(os.getenv("RATE_LIMIT_ATTEST_RPM", "6"))
    RATE_LIMIT_PUBLIC_RPM = int(os.getenv("RATE_LIMIT_PUBLIC_RPM", "120"))
    RATE_LIMIT_ADMIN_RPM = int(os.getenv("RATE_LIMIT_ADMIN_RPM", "10"))

    # Request Guards
    MAX_REQUEST_BODY_MB = int(os.getenv("MAX_REQUEST_BODY_MB", "50"))
    REQUEST_TIMEOUT_SECONDS = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "300"))
    ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "*")
