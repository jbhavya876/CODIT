"""Pure static-analysis core library shared by CODIT backend and codit-guard CLI."""

from codit_core.classify import (
    is_ci_path,
    is_gate_config_path,
    is_generated_path,
    is_test_file,
    is_test_path,
    language_of,
)
from codit_core.findings import CoreFinding
from codit_core.fingerprint import compute_fingerprint, normalize_match, normalize_path
from codit_core.secrets import SECRET_PATTERNS, SecretMatch, hash_secret_value, scan_text

__all__ = [
    "CoreFinding",
    "SECRET_PATTERNS",
    "SecretMatch",
    "compute_fingerprint",
    "hash_secret_value",
    "is_ci_path",
    "is_gate_config_path",
    "is_generated_path",
    "is_test_file",
    "is_test_path",
    "language_of",
    "normalize_match",
    "normalize_path",
    "scan_text",
]
