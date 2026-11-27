"""Pure static-analysis core library shared by CODIT backend and codit-guard CLI."""

from codit_core.attribution import ATTRIBUTION_LIMITATION, CommitAttribution, attribute_commit
from codit_core.classify import (
    is_ci_path,
    is_gate_config_path,
    is_generated_path,
    is_test_file,
    is_test_path,
    language_of,
)
from codit_core.delta import AddedLine, CommitDelta, FileDelta, FileMetrics, PolicyThresholds, TestCaseMetric
from codit_core.detectors import DetectorRunResult, run_detectors
from codit_core.findings import CoreFinding
from codit_core.fingerprint import compute_fingerprint, normalize_match, normalize_path
from codit_core.secrets import SECRET_PATTERNS, SecretMatch, hash_secret_value, scan_text
from codit_core.testmetrics import ANALYZER_VERSION, extract_test_file_metrics

__all__ = [
    "ANALYZER_VERSION",
    "ATTRIBUTION_LIMITATION",
    "AddedLine",
    "CommitAttribution",
    "CommitDelta",
    "CoreFinding",
    "DetectorRunResult",
    "FileDelta",
    "FileMetrics",
    "PolicyThresholds",
    "SECRET_PATTERNS",
    "SecretMatch",
    "TestCaseMetric",
    "attribute_commit",
    "compute_fingerprint",
    "extract_test_file_metrics",
    "hash_secret_value",
    "is_ci_path",
    "is_gate_config_path",
    "is_generated_path",
    "is_test_file",
    "is_test_path",
    "language_of",
    "normalize_match",
    "normalize_path",
    "run_detectors",
    "scan_text",
]
