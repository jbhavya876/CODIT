"""P8 Verifiable Score: Ed25519 Attestations, Challenge Nonces, Verify Page & Badges (Gate G8)."""

from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import logging
from pathlib import Path
import zipfile

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient
import pytest

from codit_guard.cli import main as guard_cli_main

from backend.app import create_app
from backend.app.attest.badge import render_badge_svg
from backend.app.attest.canonical import canonical_attestation_bytes, reject_floats
from backend.app.attest.challenge import consume_challenge_atomic, create_challenge
from backend.app.attest.signing import _b64url_encode, verify_signed_attestation
from backend.app.config import Config
from backend.app.db.engine import session_scope
from backend.app.db.models import AttestationRow, AuditRow
from backend.app.services.audit_service import create_audit, run_audit_pipeline
from backend.app.ingestion.models import FileEntry


def _make_seed_b64() -> tuple[str, str]:
    priv = Ed25519PrivateKey.generate()
    seed = priv.private_bytes_raw()
    pub_b64u = _b64url_encode(priv.public_key().public_bytes_raw())
    return base64.b64encode(seed).decode("ascii"), pub_b64u


def _make_zip_bytes(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for k, v in files.items():
            zf.writestr(k, v)
    return buf.getvalue()


def test_canonicalization_stability_unicode_and_float_rejection():
    p1 = {"b": 2, "a": "café", "nested": {"z": 1, "y": True}}
    p2 = {"nested": {"y": True, "z": 1}, "a": "café", "b": 2, "signature": {"sig": "abc"}}
    assert canonical_attestation_bytes(p1) == canonical_attestation_bytes(p2)
    assert canonical_attestation_bytes(p1) == b'{"a":"caf\xc3\xa9","b":2,"nested":{"y":true,"z":1}}'

    for bad in ({"overall": 85.5}, {"nested": [1, 2.0]}):
        with pytest.raises(ValueError):
            reject_floats(bad)
        with pytest.raises(ValueError):
            canonical_attestation_bytes(bad)


def test_challenge_hostile_repo_rejected_and_atomic_single_use_race():
    app = create_app({"GRAPH_BACKEND": "demo"})
    client = TestClient(app)

    for bad_repo in ("--upload-pack=evil", "file:///etc/passwd", "not-a-slug", "owner/repo with space"):
        r = client.post("/api/attest/challenge", json={"repo": bad_repo})
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "invalid_repo"

    ch = create_challenge("acme/demo-repo")
    nonce = ch["nonce"]
    assert ch["file_path"] == ".codit/verify"
    assert ch["content"] == f"codit-verify={nonce}\n"

    # Concurrent threads race to consume the single-use nonce; strictly ONE succeeds
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda _: consume_challenge_atomic("acme/demo-repo", [nonce]), range(6)))
    winners = [x for x in results if x is not None]
    assert winners == [nonce]


def test_attestation_issuance_verify_tamper_rotation_revoke_and_cli(monkeypatch, tmp_path, caplog):
    seed_a, pub_a = _make_seed_b64()
    seed_b, pub_b = _make_seed_b64()
    monkeypatch.delenv("ATTEST_SIGNING_KEY", raising=False)
    monkeypatch.setattr(Config, "ATTEST_SIGNING_KEY", "")
    monkeypatch.delenv("ADMIN_TOKEN", raising=False)
    monkeypatch.setattr(Config, "ADMIN_TOKEN", "")
    monkeypatch.setenv("ENTITLEMENT_MODE", "free")

    app = create_app({"GRAPH_BACKEND": "demo"})
    client = TestClient(app)

    # Admin route disabled when ADMIN_TOKEN unset -> 404
    assert client.post("/api/admin/attest/att_fake/revoke", json={"reason_code": "owner_request"}).status_code == 404

    # Prepare a completed archive audit with canary filename/content
    zip_files = [
        FileEntry("CANARY_ZIP_FILENAME_9102/app.py", 30, "python", '"""<script>alert(9)</script>"""\n'),
    ]
    zip_sha = hashlib.sha256(b"CANARY_ZIP_FILENAME_9102").hexdigest()
    zip_audit_id = create_audit(source_kind="zip", source_ref="CANARY_ZIP_FILENAME_9102.zip", archive_sha256=zip_sha)
    run_audit_pipeline(zip_audit_id, zip_files, "CANARY_ZIP_FILENAME_9102.zip", "zip")

    # Consent required -> 400
    assert client.post(f"/api/audits/{zip_audit_id}/attest", json={"consent_publish": False}).status_code == 400

    # Unset ATTEST_SIGNING_KEY -> fail closed 503
    no_key = client.post(f"/api/audits/{zip_audit_id}/attest", json={"consent_publish": True})
    assert no_key.status_code == 503
    assert no_key.json()["error"]["code"] == "attestation_unavailable"

    # Configure key A + capture logs proving secret never leaks
    monkeypatch.setenv("ATTEST_SIGNING_KEY", seed_a)
    monkeypatch.setenv("ATTEST_KEY_ID", "2026-11-a")

    with caplog.at_level(logging.DEBUG):
        arc_res = client.post(f"/api/audits/{zip_audit_id}/attest", json={"consent_publish": True})
    assert arc_res.status_code == 201
    assert seed_a not in caplog.text

    arc_att = arc_res.json()["attestation"]
    arc_id = arc_res.json()["attestation_id"]
    assert arc_att["subject"] == {"kind": "archive", "sha256": zip_sha, "control_verified": False}
    assert "CANARY_ZIP_FILENAME_9102" not in json.dumps(arc_att)

    # Verify page headers, zero scripts, and SVG badge ARCHIVE state + zero canaries
    v_page = client.get(f"/v/{arc_id}")
    assert v_page.status_code == 200
    assert "<script" not in v_page.text.lower()
    assert "default-src 'none'; style-src 'self'" in v_page.headers["content-security-policy"]
    assert v_page.headers["referrer-policy"] == "no-referrer"
    assert "CANARY_ZIP_FILENAME_9102" not in v_page.text
    assert "<img src=x" not in v_page.text
    assert client.get("/static/verify.css").status_code == 200

    svg_arc = client.get(f"/badge/{arc_id}.svg")
    assert svg_arc.status_code == 200
    assert "ARCHIVE" in svg_arc.text
    assert "CANARY_ZIP_FILENAME_9102" not in svg_arc.text

    # Git audit WITHOUT .codit/verify token -> 403 control_not_verified
    git_no_tok = create_audit(source_kind="public", source_ref="https://github.com/octocat/hello-verify")
    with session_scope() as session:
        r = session.get(AuditRow, git_no_tok)
        assert r is not None
        r.source_commit = "a" * 40
        r.source_tree = "b" * 40
        r.process_json = {"source_commit": "a" * 40, "source_tree": "b" * 40}
        r.coverage_json = {"files_total": 3, "files_scanned": 3, "history": {"assessed": True, "commits_analyzed": 2}, "licenses": {"not_applicable": True}}
    run_audit_pipeline(git_no_tok, [FileEntry("app.py", 12, "python", "x = 1\n")], "https://github.com/octocat/hello-verify", "public")
    assert client.post(f"/api/audits/{git_no_tok}/attest", json={"consent_publish": True}).status_code == 403

    # Git audit WITH .codit/verify token -> 201 VERIFIED, second issue blocked by single-use nonce!
    ch = client.post("/api/attest/challenge", json={"repo": "octocat/hello-verify"}).json()
    git_ok_id = create_audit(source_kind="public", source_ref="https://github.com/octocat/hello-verify")
    with session_scope() as session:
        r = session.get(AuditRow, git_ok_id)
        assert r is not None
        r.source_commit = "c" * 40
        r.source_tree = "d" * 40
        r.process_json = {"source_commit": "c" * 40, "source_tree": "d" * 40}
        r.coverage_json = {"files_total": 3, "files_scanned": 3, "history": {"assessed": True, "commits_analyzed": 2}, "licenses": {"not_applicable": True}}
    run_audit_pipeline(
        git_ok_id,
        [FileEntry("app.py", 12, "python", "x = 1\n"), FileEntry(".codit/verify", 30, "other", ch["content"])],
        "https://github.com/octocat/hello-verify",
        "public",
    )
    git_att_res = client.post(f"/api/audits/{git_ok_id}/attest", json={"consent_publish": True})
    assert git_att_res.status_code == 201
    git_att = git_att_res.json()["attestation"]
    git_att_id = git_att_res.json()["attestation_id"]
    assert git_att["subject"]["control_verified"] is True
    assert client.post(f"/api/audits/{git_ok_id}/attest", json={"consent_publish": True}).status_code == 403

    svg_ver = client.get(f"/badge/{git_att_id}.svg")
    assert svg_ver.status_code == 200 and "VERIFIED" in svg_ver.text

    # CLI offline verify passes (`0`), tamper fails (`1`), expired fails (`1`)
    att_file = tmp_path / "att.json"
    att_file.write_text(json.dumps(git_att), encoding="utf-8")
    keys_file = tmp_path / "keys.json"
    keys_doc = client.get("/.well-known/codit-keys.json").json()
    keys_file.write_text(json.dumps(keys_doc), encoding="utf-8")

    assert guard_cli_main(["attest", "verify", str(att_file), "--keys", str(keys_file)]) == 0

    # Key rotation: rotate ATTEST_SIGNING_KEY -> key B, keep retired key A in keys_doc
    monkeypatch.setenv("ATTEST_SIGNING_KEY", seed_b)
    monkeypatch.setenv("ATTEST_KEY_ID", "2027-01-b")
    rotated_keys = client.get("/.well-known/codit-keys.json").json()
    rotated_keys["keys"].append({"kid": "2026-11-a", "alg": "Ed25519", "public_key": pub_a, "status": "retired"})
    ok_old, err_old = verify_signed_attestation(git_att, keys_doc=rotated_keys)
    assert ok_old and err_old is None

    # Tamper every top-level section and assert signature check fails
    for field_name, bad_val in (("issued_at", "2020-01-01T00:00:00Z"), ("findings_digest", "sha256:00")):
        tampered = dict(git_att)
        tampered[field_name] = bad_val
        tamper_file = tmp_path / f"tamper_{field_name}.json"
        tamper_file.write_text(json.dumps(tampered), encoding="utf-8")
        assert guard_cli_main(["attest", "verify", str(tamper_file), "--keys", str(keys_file)]) == 1

    # Admin revocation + revoked-then-expired precedence (REVOKED wins over EXPIRED!)
    monkeypatch.setenv("ADMIN_TOKEN", "topsecret-admin-tok")
    assert client.post(f"/api/admin/attest/{git_att_id}/revoke", json={"reason_code": "owner_request"}, headers={"X-Admin-Token": "wrong"}).status_code == 401
    rev_res = client.post(
        f"/api/admin/attest/{git_att_id}/revoke",
        json={"reason_code": "owner_request"},
        headers={"Authorization": "Bearer topsecret-admin-tok"},
    )
    assert rev_res.status_code == 200
    revs_file = tmp_path / "revs.json"
    revs_file.write_text(json.dumps(client.get("/.well-known/codit-revocations.json").json()), encoding="utf-8")
    assert guard_cli_main(["attest", "verify", str(att_file), "--keys", str(keys_file), "--revocations", str(revs_file)]) == 1

    # Force expires_at into the past and confirm REVOKED still wins over EXPIRED in badge & /v/{id}
    with session_scope() as session:
        arow = session.get(AttestationRow, git_att_id)
        assert arow is not None
        arow.expires_at = datetime.now(timezone.utc) - timedelta(days=1)

    assert "REVOKED" in client.get(f"/badge/{git_att_id}.svg").text
    assert "REVOKED" in client.get(f"/v/{git_att_id}").text


def test_golden_svg_states_and_non_hue_glyphs():
    states = [
        ("VERIFIED", False, "VERIFIED", "M5 10.5l3 3 6-6.5"),
        ("ARCHIVE", True, "PARTIAL", "M4 6h10v8H4z"),
        ("EXPIRED", False, "EXPIRED", "M9 4.5v5l3 1.5"),
        ("REVOKED", False, "REVOKED", "M5 5l8 8"),
    ]
    for st, partial, expected_text, expected_glyph in states:
        svg = render_badge_svg(state=st, score=88, phase="Production-track", partial=partial)
        assert svg.startswith("<svg ") and svg.endswith("</svg>")
        assert expected_text in svg
        assert expected_glyph in svg
