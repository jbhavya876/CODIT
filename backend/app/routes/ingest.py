"""
Ingestion routes for Public GitHub repos, Private GitHub repos, and ZIP uploads.
"""

from __future__ import annotations

import io
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from backend.app.config import Config
from backend.app.ingestion.github_fetch import fetch_public_repo, GitHubIngestionError
from backend.app.ingestion.git_clone import clone_private_repo, GitCloneError
from backend.app.ingestion.models import FileEntry
from backend.app.ingestion.zip_extract import extract_zip, purge_extracted_files, ZipSecurityError
from backend.app.state import get_active_codebase, set_active_codebase

router = APIRouter(prefix="/api/ingest", tags=["ingestion"])


class PublicRepoRequest(BaseModel):
    url: str
    ref: Optional[str] = "main"


class PrivateRepoRequest(BaseModel):
    repo: str
    token: str
    branch: Optional[str] = None


@router.get("/status")
def ingestion_status():
    current = get_active_codebase()
    return {
        "active_target": current["target"],
        "type": current["type"],
        "file_count": current.get("file_count", 0),
        "languages": current.get("languages", {}),
        "total_size_kb": current.get("total_size_kb", 0),
    }


@router.post("/public")
def ingest_public_repo(payload: PublicRepoRequest):
    try:
        entries = fetch_public_repo(payload.url, ref=payload.ref or "main")
        summary = set_active_codebase(payload.url, "public", entries)
        return {
            "status": "ok",
            "message": f"Successfully ingested public repository: {payload.url}",
            **summary,
        }
    except GitHubIngestionError as exc:
        raise HTTPException(status_code=400, detail={"code": "github_ingest_error", "message": str(exc)})
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"code": "ingest_error", "message": str(exc)})


@router.post("/zip")
async def ingest_zip_upload(file: UploadFile = File(...)):
    # Validate filename
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_file", "message": "Only .zip archive uploads are supported."},
        )

    # Read uploaded bytes
    content = await file.read()
    temp_dir = Path(tempfile.mkdtemp(prefix="audit_zip_"))

    try:
        entries = extract_zip(content, temp_dir)
        summary = set_active_codebase(file.filename, "zip", entries, temp_dir=temp_dir)
        return {
            "status": "ok",
            "message": f"Successfully extracted and validated ZIP archive '{file.filename}'.",
            **summary,
        }
    except ZipSecurityError as exc:
        # Pre-extraction security failure (Zip-Slip or Zip-Bomb)
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
def ingest_private_repo(payload: PrivateRepoRequest):
    temp_dir = Path(tempfile.mkdtemp(prefix="audit_clone_"))
    try:
        entries = clone_private_repo(
            repo_slug=payload.repo,
            access_token=payload.token,
            destination_dir=temp_dir,
            branch=payload.branch,
        )
        summary = set_active_codebase(payload.repo, "private", entries, temp_dir=temp_dir)
        return {
            "status": "ok",
            "message": f"Successfully cloned private repository: {payload.repo}",
            **summary,
        }
    except GitCloneError as exc:
        purge_extracted_files(temp_dir)
        raise HTTPException(status_code=400, detail={"code": "git_clone_error", "message": str(exc)})
    except Exception as exc:
        purge_extracted_files(temp_dir)
        raise HTTPException(status_code=500, detail={"code": "private_ingest_error", "message": str(exc)})
