"""
Ingestion routes for Public GitHub repos, Private GitHub repos, and ZIP uploads.

Backed by per-audit staging and signed cookies via `audit_service` (ADR-0001).
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel

from backend.app.config import Config
from backend.app.ingestion.git_clone import GitCloneError, clone_private_repo
from backend.app.ingestion.github_fetch import GitHubIngestionError, fetch_public_repo
from backend.app.ingestion.models import FileEntry
from backend.app.ingestion.zip_extract import ZipSecurityError, extract_zip, purge_extracted_files
from backend.app.services import audit_service

router = APIRouter(prefix="/api/ingest", tags=["ingestion"])


class PublicRepoRequest(BaseModel):
    url: str
    ref: Optional[str] = "main"


class PrivateRepoRequest(BaseModel):
    repo: str
    token: str
    branch: Optional[str] = None


def get_active_codebase(request: Optional[Request] = None) -> Dict[str, Any]:
    """Legacy wrapper reading from staged audit cookie or latest staged manifest."""
    audit_id = audit_service.get_audit_id_from_request(request)
    if audit_id:
        staged = audit_service.get_staged_codebase(audit_id)
        if staged is not None:
            return staged
        row = audit_service.get_audit_row(audit_id)
        if row is not None:
            cov = row.coverage_json or {}
            return {
                "audit_id": row.id,
                "target": row.source_ref,
                "type": row.source_kind,
                "entries": [],
                "languages": {},
                "file_count": cov.get("files_total", 0),
                "total_size_kb": 0,
                "temp_dir": None,
            }
    return audit_service.get_latest_staged_codebase()


def set_active_codebase(
    target: str,
    target_type: str,
    entries: List[FileEntry],
    temp_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Legacy wrapper that stages entries under a fresh audit_id."""
    audit_id, summary = audit_service.create_staged_audit(target, target_type, entries, temp_dir=temp_dir)
    summary["audit_id"] = audit_id
    return summary


@router.get("/status")
def ingestion_status(request: Request):
    current = get_active_codebase(request)
    return {
        "active_target": current["target"],
        "type": current["type"],
        "file_count": current.get("file_count", 0),
        "languages": current.get("languages", {}),
        "total_size_kb": current.get("total_size_kb", 0),
    }


@router.post("/public")
def ingest_public_repo(payload: PublicRepoRequest, response: Response):
    url = payload.url.strip()
    if not url.startswith("https://github.com/"):
        raise HTTPException(
            status_code=400,
            detail={
                "code": "invalid_url",
                "message": "Only public GitHub repository URLs (https://github.com/...) are supported.",
            },
        )
    try:
        entries = fetch_public_repo(url, ref=payload.ref or "main")
        audit_id, summary = audit_service.create_staged_audit(url, "public", entries)
        audit_service.set_audit_cookie(response, audit_id)
        return {
            "status": "ok",
            "audit_id": audit_id,
            "message": f"Successfully ingested public repository: {url}",
            "target": summary["target"],
            "type": summary["type"],
            "languages": summary["languages"],
            "file_count": summary["file_count"],
            "total_size_kb": summary["total_size_kb"],
            "temp_dir": summary["temp_dir"],
        }
    except GitHubIngestionError as exc:
        raise HTTPException(status_code=400, detail={"code": "github_ingest_error", "message": str(exc)})
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"code": "ingest_error", "message": str(exc)})


@router.post("/zip")
async def ingest_zip_upload(response: Response, file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_file", "message": "Only .zip archive uploads are supported."},
        )

    content = await file.read()
    max_bytes = Config.MAX_INDIVIDUAL_FILE_MB * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail={
                "code": "file_too_large",
                "message": (
                    f"Uploaded archive exceeds the maximum allowed size of "
                    f"{Config.MAX_INDIVIDUAL_FILE_MB} MB."
                ),
            },
        )
    temp_dir = Path(tempfile.mkdtemp(prefix="audit_zip_"))

    try:
        entries = extract_zip(content, temp_dir)
        audit_id, summary = audit_service.create_staged_audit(
            file.filename, "zip", entries, temp_dir=temp_dir
        )
        if response is not None:
            audit_service.set_audit_cookie(response, audit_id)
        return {
            "status": "ok",
            "audit_id": audit_id,
            "message": f"Successfully extracted and validated ZIP archive '{file.filename}'.",
            "target": summary["target"],
            "type": summary["type"],
            "languages": summary["languages"],
            "file_count": summary["file_count"],
            "total_size_kb": summary["total_size_kb"],
            "temp_dir": summary["temp_dir"],
        }
    except ZipSecurityError as exc:
        purge_extracted_files(temp_dir)
        raise HTTPException(
            status_code=400,
            detail={"code": "zip_security_violation", "message": str(exc)},
        )
    except Exception as exc:
        purge_extracted_files(temp_dir)
        raise HTTPException(
            status_code=500,
            detail={"code": "zip_extraction_failed", "message": str(exc)},
        )


@router.post("/private")
def ingest_private_repo(payload: PrivateRepoRequest, response: Response):
    temp_dir = Path(tempfile.mkdtemp(prefix="audit_clone_"))
    try:
        entries = clone_private_repo(
            repo_slug=payload.repo,
            access_token=payload.token,
            destination_dir=temp_dir,
            branch=payload.branch,
        )
        audit_id, summary = audit_service.create_staged_audit(
            payload.repo, "private", entries, temp_dir=temp_dir
        )
        audit_service.set_audit_cookie(response, audit_id)
        return {
            "status": "ok",
            "audit_id": audit_id,
            "message": f"Successfully cloned private repository: {payload.repo}",
            "target": summary["target"],
            "type": summary["type"],
            "languages": summary["languages"],
            "file_count": summary["file_count"],
            "total_size_kb": summary["total_size_kb"],
            "temp_dir": summary["temp_dir"],
        }
    except GitCloneError as exc:
        purge_extracted_files(temp_dir)
        raise HTTPException(status_code=400, detail={"code": "git_clone_error", "message": str(exc)})
    except Exception as exc:
        purge_extracted_files(temp_dir)
        raise HTTPException(status_code=500, detail={"code": "private_ingest_error", "message": str(exc)})
