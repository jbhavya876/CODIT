"""
ZIP archive ingestion with pre-extraction validation and Zip-Slip / Zip-Bomb defenses.

Security constraints:
- Non-negotiable Constraint 2: Validate against zip-slip before ANY file is written to disk.
- Non-negotiable Constraint 3: Check against size/count/depth limits BEFORE extraction begins.
- Non-negotiable Constraint 7: Real cleanup/deletion of extracted files.
"""

from __future__ import annotations

import io
import logging
import os
import shutil
import zipfile
from pathlib import Path
from typing import List, Union

from backend.app.config import Config
from backend.app.ingestion.models import FileEntry, detect_language, is_ignored_path

log = logging.getLogger(__name__)


class ZipSecurityError(ValueError):
    """Raised when a ZIP archive violates security constraints."""


class ZipSlipError(ZipSecurityError):
    """Raised when an entry attempts directory traversal."""


class ZipBombError(ZipSecurityError):
    """Raised when an archive exceeds size, file count, or depth thresholds."""


def validate_zip_metadata(zip_ref: zipfile.ZipFile, target_dir: Path) -> None:
    """
    Validates 100% of archive entries BEFORE any file is written to disk.
    Enforces Zip-Slip, Zip-Bomb, nesting depth, and size limits.
    """
    max_file_count = Config.MAX_FILE_COUNT
    max_repo_size_bytes = Config.MAX_REPO_SIZE_MB * 1024 * 1024
    max_individual_file_bytes = Config.MAX_INDIVIDUAL_FILE_MB * 1024 * 1024
    max_depth = 20

    infolist = zip_ref.infolist()

    # 1. Total entry count limit check (pre-extraction)
    if len(infolist) > max_file_count:
        raise ZipBombError(
            f"Archive contains {len(infolist)} files, exceeding maximum limit of {max_file_count}."
        )

    # 2. Cumulative uncompressed size check (pre-extraction)
    total_uncompressed_bytes = sum(info.file_size for info in infolist)
    if total_uncompressed_bytes > max_repo_size_bytes:
        raise ZipBombError(
            f"Archive total uncompressed size ({total_uncompressed_bytes / (1024*1024):.1f}MB) "
            f"exceeds maximum allowed limit of {Config.MAX_REPO_SIZE_MB}MB."
        )

    resolved_target = target_dir.resolve()

    # 3. Comprehensive entry-by-entry validation (pre-extraction)
    for info in infolist:
        raw_name = info.filename

        # Check for absolute path indicators (Unix or Windows drive letter)
        if os.path.isabs(raw_name) or (len(raw_name) >= 2 and raw_name[1] == ":"):
            raise ZipSlipError(
                f"Zip-Slip vulnerability detected: absolute path in entry '{raw_name}'."
            )

        # Check for path traversal tokens
        normalized = os.path.normpath(raw_name)
        if (
            normalized.startswith("..")
            or "/../" in raw_name
            or "\\..\\" in raw_name
            or raw_name.startswith("../")
            or raw_name.startswith("..\\")
        ):
            raise ZipSlipError(
                f"Zip-Slip vulnerability detected: traversal sequence in entry '{raw_name}'."
            )

        # Check resolved extraction path strictly resides within target_dir
        dest_path = (target_dir / raw_name).resolve()
        try:
            dest_path.relative_to(resolved_target)
        except ValueError:
            raise ZipSlipError(
                f"Zip-Slip vulnerability detected: entry '{raw_name}' escapes destination directory."
            )

        # Check nesting depth
        parts = Path(normalized).parts
        if len(parts) > max_depth:
            raise ZipBombError(
                f"Archive exceeds maximum directory depth limit ({max_depth}) with path '{raw_name}'."
            )

        # Check individual file size limit
        if info.file_size > max_individual_file_bytes:
            raise ZipBombError(
                f"File '{raw_name}' size ({info.file_size / (1024*1024):.1f}MB) "
                f"exceeds individual file limit of {Config.MAX_INDIVIDUAL_FILE_MB}MB."
            )


def extract_zip(
    archive_source: Union[str, Path, bytes, io.BytesIO],
    destination_dir: Path,
) -> List[FileEntry]:
    """
    Extracts validated ZIP archive and returns normalized FileEntry list.
    Guarantees pre-validation before extracting any file.
    """
    destination_dir.mkdir(parents=True, exist_ok=True)

    if isinstance(archive_source, (str, Path)):
        zip_ref = zipfile.ZipFile(archive_source, "r")
    elif isinstance(archive_source, bytes):
        zip_ref = zipfile.ZipFile(io.BytesIO(archive_source), "r")
    else:
        zip_ref = zipfile.ZipFile(archive_source, "r")

    try:
        # Pre-extraction validation — will raise if invalid
        validate_zip_metadata(zip_ref, destination_dir)

        # Safe extraction of all entries
        zip_ref.extractall(destination_dir)

        # Collect normalized file manifest
        entries: List[FileEntry] = []
        resolved_dest = destination_dir.resolve()

        for root, dirs, files in os.walk(resolved_dest):
            # Prune ignored directories in-place for fast traversal
            dirs[:] = [d for d in dirs if not is_ignored_path(d)]

            for file_name in files:
                full_path = Path(root) / file_name
                rel_path = full_path.relative_to(resolved_dest).as_posix()

                if is_ignored_path(rel_path):
                    continue

                size = full_path.stat().st_size
                lang = detect_language(rel_path)

                content = ""
                try:
                    with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()
                except Exception as exc:
                    log.warning("Could not read file %s as text: %s", rel_path, exc)

                entries.append(FileEntry(
                    path=rel_path,
                    size=size,
                    language=lang,
                    content=content,
                ))

        return entries
    finally:
        zip_ref.close()


def purge_extracted_files(target_dir: Path) -> bool:
    """
    Deletes the extracted source directory immediately (Constraint 7).
    """
    if target_dir.exists():
        try:
            shutil.rmtree(target_dir, ignore_errors=True)
            log.info("Purged extracted directory %s", target_dir)
            return True
        except Exception as exc:
            log.error("Failed to purge directory %s: %s", target_dir, exc)
            return False
    return True
