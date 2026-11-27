"""Single-use atomic repository-control verification challenges (`.codit/verify`)."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from sqlalchemy import update

from backend.app.attest.canonical import utc_iso_second
from backend.app.db.engine import session_scope
from backend.app.db.models import AttestChallengeRow
from backend.app.history.acquire import HistoryAcquisitionError, validate_github_repo_input

CHALLENGE_TTL_HOURS = 24


class InvalidChallengeRepoError(ValueError):
    """Raised when challenge repo slug fails host/slug validation."""


def create_challenge(repo: str) -> Dict[str, str]:
    try:
        owner, name = validate_github_repo_input(repo)
    except HistoryAcquisitionError as exc:
        raise InvalidChallengeRepoError(str(exc)) from exc

    canonical_repo = f"{owner}/{name}"
    nonce = secrets.token_urlsafe(16)
    now = datetime.now(timezone.utc)
    expires = now + timedelta(hours=CHALLENGE_TTL_HOURS)

    with session_scope() as session:
        session.add(
            AttestChallengeRow(
                nonce=nonce,
                repo=canonical_repo,
                created_at=now,
                expires_at=expires,
                used_at=None,
            )
        )

    return {
        "repo": canonical_repo,
        "nonce": nonce,
        "file_path": ".codit/verify",
        "content": f"codit-verify={nonce}\n",
        "expires_at": utc_iso_second(expires),
    }


def consume_challenge_atomic(repo: str, candidate_nonces: List[str], now: Optional[datetime] = None) -> Optional[str]:
    """
    Atomically claim one unused, unexpired challenge nonce bound to `repo`.
    Uses SQL `UPDATE ... WHERE used_at IS NULL AND expires_at > :now` requiring `rowcount == 1`.
    """
    if not candidate_nonces or not repo:
        return None
    cur = now or datetime.now(timezone.utc)
    with session_scope() as session:
        for nonce in candidate_nonces:
            res = session.execute(
                update(AttestChallengeRow)
                .where(
                    AttestChallengeRow.nonce == nonce,
                    AttestChallengeRow.repo == repo,
                    AttestChallengeRow.used_at.is_(None),
                    AttestChallengeRow.expires_at > cur,
                )
                .values(used_at=cur)
            )
            if res.rowcount == 1:
                return nonce
    return None
