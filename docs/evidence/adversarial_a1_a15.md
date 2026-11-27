# Adversarial Verification Evidence (`a1`–`a15`, Zero Skipped / Zero `xfail`)

| ID | Attack Vector | Verification Test |
|---|---|---|
| `a1` | ZIP `.git/config` `core.fsmonitor` script | `backend/tests/test_p1_history.py::test_adversarial_a1_a2_a3_a5_zip_git_attacks` |
| `a2` | `.git/hooks/*` executable triggers | `backend/tests/test_p1_history.py::test_adversarial_a1_a2_a3_a5_zip_git_attacks` |
| `a3` | `objects/info/alternates` host path leak | `backend/tests/test_p1_history.py::test_adversarial_a1_a2_a3_a5_zip_git_attacks` |
| `a4` | Oversized blob / delta pack resource bounds | `backend/tests/test_p10_hardening.py::test_adversarial_a4_oversized_blob_and_a11_commit_cap` |
| `a5` | `.git` symlink / `gitdir:` pointer escape | `backend/tests/test_p1_history.py::test_adversarial_a1_a2_a3_a5_zip_git_attacks` |
| `a6` | Gitlink / submodule & symlink tree entries | `backend/tests/test_p1_history.py::test_gitlink_and_symlink_and_bad_tree_paths_a6_a7` |
| `a7` | Tree entries `..`, `/abs`, and NUL bytes | `backend/tests/test_p1_history.py::test_gitlink_and_symlink_and_bad_tree_paths_a6_a7` |
| `a8` | Prompt injection in commit text (`"Ignore previous..."`) | `backend/tests/test_p7_reports.py::test_canary_isolation_underwriting_and_llm_payload_and_a8_a9_a10` |
| `a9` | Author name `<script>` XSS injection | `backend/tests/test_p7_reports.py::test_canary_isolation_underwriting_and_llm_payload_and_a8_a9_a10` |
| `a10` | File path `"><img src=x onerror=...>` injection | `backend/tests/test_p7_reports.py::test_canary_isolation_underwriting_and_llm_payload_and_a8_a9_a10` |
| `a11` | High commit count bounding (`max_commits` cap) | `backend/tests/test_p10_hardening.py::test_adversarial_a4_oversized_blob_and_a11_commit_cap` |
| `a12` | URL / branch flag injection (`--upload-pack=`, `file://`, `ext::`) | `backend/tests/test_p7_reports.py::test_audits_lifecycle_entitlements_and_a12_validation` |
| `a13` | Forged, tampered, expired, revoked attestations & nonce race | `backend/tests/test_p8_attestations.py::test_challenge_hostile_repo_rejected_and_atomic_single_use_race`, `test_attestation_issuance_verify_tamper_rotation_revoke_and_cli` |
| `a14` | `.codit.yml` policy-edit evasion in PR | `backend/tests/test_p4_guard.py::test_a14_policy_edit_attack_uses_base_policy` |
| `a15` | Oversized hook payload & ambiguous `old_string` | `backend/tests/test_p4_guard.py::test_claude_code_hook_adversarial_a15_and_blocking` |
