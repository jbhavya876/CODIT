"""
ZIP archive ingestion with pre-extraction validation and Zip-Slip / Zip-Bomb defenses,
plus P1 allowlisted `.git/` subtree extraction for safe `dulwich` history inspection.
"""

from __future__ import annotations

import io
import logging
import os
import re
import shutil
import stat
import zipfile
from pathlib import Path
from typing import List, Tuple, Union

from backend.app.config import Config
from backend.app.ingestion.models import FileEntry, detect_language, is_ignored_path

log = logging.getLogger(__name__)

_GIT_OBJECT_RE = re.compile(r"^objects/[0-9a-f]{2}/[0-9a-f]{38}$")
_GIT_PACK_RE = re.compile(r"^objects/pack/pack-[0-9a-f]{40}\.(?:pack|idx)$")


class ZipSecurityError(ValueError):
    """Raised when a ZIP archive violates security constraints."""


class ZipSlipError(ZipSecurityError):
    """Raised when an entry attempts directory traversal."""


class ZipBombError(ZipSecurityError):
    """Raised when an archive exceeds size, file count, or depth thresholds."""


def _is_zip_symlink(info: zipfile.ZipInfo) -> bool:
    unix_mode = (info.external_attr >> 16) & 0o170000
    return unix_mode == stat.S_IFLNK


def _is_allowed_git_subpath(rel_under_git: str) -> bool:
    if rel_under_git in ("HEAD", "packed-refs", "shallow"):
        return True
    if rel_under_git.startswith("refs/") and not rel_under_git.endswith("/"):
        return True
    if _GIT_OBJECT_RE.match(rel_under_git):
        return True
    if _GIT_PACK_RE.match(rel_under_git):
        return True
    # Also accept generic objects/pack/*.pack and objects/pack/*.idx inside .git
    if rel_under_git.startswith("objects/pack/") and rel_under_git.count("/") == 2:
        if rel_under_git.endswith((".pack", ".idx")):
            return True
    return False


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

    if len(infolist) > max_file_count:
        raise ZipBombError(
            f"Archive contains {len(infolist)} files, exceeding maximum limit of {max_file_count}."
        )

    total_uncompressed_bytes = sum(info.file_size for info in infolist)
    if total_uncompressed_bytes > max_repo_size_bytes:
        raise ZipBombError(
            f"Archive total uncompressed size ({total_uncompressed_bytes / (1024*1024):.1f}MB) "
            f"exceeds maximum allowed limit of {Config.MAX_REPO_SIZE_MB}MB."
        )

    resolved_target = target_dir.resolve()

    for info in infolist:
        raw_name = info.filename

        if os.path.isabs(raw_name) or (len(raw_name) >= 2 and raw_name[1] == ":"):
            raise ZipSlipError(
                f"Zip-Slip vulnerability detected: absolute path in entry '{raw_name}'."
            )

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

        dest_path = (target_dir / raw_name).resolve()
        try:
            dest_path.relative_to(resolved_target)
        except ValueError as exc:
            raise ZipSlipError(
                f"Zip-Slip vulnerability detected: entry '{raw_name}' escapes destination directory."
            ) from exc

        parts = Path(normalized).parts
        if len(parts) > max_depth:
            raise ZipBombError(
                f"Archive exceeds maximum directory depth limit ({max_depth}) with path '{raw_name}'."
            )

        if info.file_size > max_individual_file_bytes:
            raise ZipBombError(
                f"File '{raw_name}' size ({info.file_size / (1024*1024):.1f}MB) "
                f"exceeds individual file limit of {Config.MAX_INDIVIDUAL_FILE_MB}MB."
            )


def _open_zip(archive_source: Union[str, Path, bytes, io.BytesIO]) -> zipfile.ZipFile:
    if isinstance(archive_source, bytes):
        return zipfile.ZipFile(io.BytesIO(archive_source), "r")
    return zipfile.ZipFile(archive_source, "r")


def extract_zip(
    archive_source: Union[str, Path, bytes, io.BytesIO],
    destination_dir: Path,
) -> List[FileEntry]:
    """
    Extracts validated ZIP archive and returns normalized FileEntry list.
    Guarantees pre-validation before extracting any file.
    """
    destination_dir.mkdir(parents=True, exist_ok=True)
    zip_ref = _open_zip(archive_source)

    try:
        validate_zip_metadata(zip_ref, destination_dir)
        zip_ref.extractall(destination_dir)

        entries: List[FileEntry] = []
        resolved_dest = destination_dir.resolve()

        for root, dirs, files in os.walk(resolved_dest):
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


def extract_git_history_from_zip(
    archive_source: Union[str, Path, bytes, io.BytesIO],
    git_dest_dir: Path,
) -> Tuple[bool, Optional[str]]:
    """
    Safely extract ONLY allowlisted `.git/` objects and refs into `git_dest_dir/.git`.

    Drops `config`, `hooks/`, `info/`, `objects/info/alternates`, `commondir`,
    `gitdir`, `worktrees/`, and `modules/`, rejects symlinks and `.git`-as-file,
    and writes a fresh minimal `.git/config`.

    Returns (extracted_ok, reason_if_not_assessed).
    """
    zip_ref = _open_zip(archive_source)
    try:
        validate_zip_metadata(zip_ref, git_dest_dir)
        infolist = zip_ref.infolist()

        git_entries: List[Tuple[zipfile.ZipInfo, str]] = []
        for info in infolist:
            norm = info.filename.replace("\\", "/")
            while norm.startswith("./"):
                norm = norm[2:]
            if norm == ".git" or norm.startswith(".git/"):
                if _is_zip_symlink(info):
                    return False, "unsafe_git_symlink"
                if norm == ".git" and not info.is_dir():
                    return False, "unsafe_git_metadata"
                if norm.startswith(".git/") and not info.is_dir():
                    rel_under_git = norm[len(".git/"):]
                    git_entries.append((info, rel_under_git))

        if not git_entries:
            return False, "no_history_in_archive"

        dot_git_out = (git_dest_dir / ".git").resolve()
        dot_git_out.mkdir(parents=True, exist_ok=True)

        extracted_any_head_or_ref = False
        for info, rel_under_git in git_entries:
            if not _is_allowed_git_subpath(rel_under_git):
                # Explicitly drop config, hooks/*, info/*, objects/info/alternates, worktrees/*, modules/*
                continue

            target_path = (dot_git_out / rel_under_git).resolve()
            try:
                target_path.relative_to(dot_git_out)
            except ValueError:
                return False, "unsafe_git_path"

            target_path.parent.mkdir(parents=True, exist_ok=True)
            with zip_ref.open(info, "r") as src, open(target_path, "wb") as dst:
                shutil.copyfileobj(src, dst)
            if rel_under_git == "HEAD" or rel_under_git.startswith("refs/"):
                extracted_any_head_or_ref = True

        if not extracted_any_head_or_ref:
            return False, "no_history_in_archive"

        # Always write a fresh, clean config file with zero hooks/fsmonitor/alternates
        (dot_git_out / "config").write_text(
            "[core]\n\trepositoryformatversion = 0\n\tbare = false\n",
            encoding="utf-8",
        )
        return True, None
    finally:
        zip_ref.close()


def purge_extracted_files(target_dir: Path) -> bool:
    """Deletes extracted directories immediately (Constraint 7)."""
    if target_dir.exists():
        try:
            shutil.rmtree(target_dir, ignore_errors=True)
            log.info("Purged extracted directory %s", target_dir)
            return True
        except Exception as exc:
            log.error("Failed to purge directory %s: %s", target_dir, exc)
            return False
    return True
