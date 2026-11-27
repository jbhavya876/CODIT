# CODIT Scoring Rubric `2.0.0` & Effort Model

> **Generated deterministically** by `scripts/gen_rubric_doc.py` from `backend/app/scoring/rubric.py`, `backend/app/scoring/effort_model.py`, and `packages/codit_core/src/codit_core/rules.yaml`. Do not hand-edit.

Static analysis of repository contents and history. No code is executed. A score is a deterministic signal over observed evidence — never a certification, legal opinion, or guarantee.

**Core principle:** *A badge must not reward missing evidence.*

## 1. Dimension Weights (`2.0.0`)

| Dimension | Weight | Confidence Scaling | Notes |
|---|---:|---|---|
| `security` | `0.30` | Unscaled (`1.0`, matches `1.0.0`) | Static security collector + `AGT-010` (secrets committed to history). |
| `tests` | `0.20` | Unscaled (`1.0`, matches `1.0.0`) | Test ratio, shallow assertions, framework config checks. |
| `agent_integrity` | `0.15` | Applied (`1.0 / 0.75 / 0.5`) | `AGT-001..009`, `AGT-011`, `AGT-012`, `GRD-001`, `GRD-002`; requires git history. |
| `scalability` | `0.12` | Unscaled (`1.0`, matches `1.0.0`) | N+1 query shapes, sync calls in async paths, connection management. |
| `licenses` | `0.10` | Applied (`1.0 / 0.75 / 0.5`) | `LIC-001..008`; requires >=90% production dependency resolution (or `not_applicable` if no dependencies). |
| `duplication` | `0.07` | Unscaled (`1.0`, matches `1.0.0`) | Repeated AST/structural code blocks across modules. |
| `maintainability` | `0.06` | Unscaled (`1.0`, matches `1.0.0`) | Module complexity, monolith boundaries, coupling metrics. |

Total weight: `1.00`.

When a dimension is not assessed, its weight is excluded and the remaining assessed dimensions are renormalized: `overall = round_half_up(sum(w_i * s_i) / sum(w_i))` using `int(x + 0.5)`.

## 2. Severity Deductions & Confidence Multipliers

| Severity | Base Deduction |
|---|---:|
| `critical` | `35` |
| `high` | `18` |
| `medium` | `8` |
| `low` | `3` |
| `info` | `0` |

Confidence multipliers (applied to `agent_integrity` and `licenses` only): `high` = `1.0x`, `medium` = `0.75x`, `low` = `0.5x`.

## 3. Hard Score Caps

- `security`: capped at `25` when any `critical` security finding is present.
- `licenses`: capped at `30` on any `critical` finding, `70` on any `high` finding.
- `agent_integrity`: capped at `60` when any `high`-confidence `high`/`critical` AGT finding falls within the most recent 90 days of the analyzed history window, and `40` when 3+ distinct commits carry such findings.

## 4. Phase Gate Rules

- **Production-track**: `overall >= 80`, `security >= 75`, `tests >= 70`, `agent_integrity >= 60`, `licenses >= 60` (or `not_applicable`), zero `critical` findings, **and every weighted dimension is either `assessed` or `not_applicable`**. Production-track is strictly unattainable without assessed process integrity (*a badge must not reward missing evidence*).
- **MVP**: `overall >= 55`, `security >= 50`, and zero `critical` findings.
- **Prototype**: all other states.

### Phase Qualifiers & Blockers

Qualifiers emitted when evidence is partial or absent:
- `process_integrity_not_assessed`: Process integrity (agent history) was not assessed; Production-track requires git history assessment.
- `license_coverage_partial`: Fewer than 90% of production dependencies had resolved licenses; Production-track requires >= 90% license coverage.
- `license_coverage_missing`: Dependency license resolution data was unavailable for this audit.
- `history_partial`: Git history inspection hit depth, commit, or shallow-clone boundaries.
- `licenses_not_applicable`: Repository declared no pinned or unpinned package dependencies; license dimension marked not applicable.

Blocker codes: `critical_security`, `copyleft_conflict`, `history_secret_unrotated`, `high_confidence_test_integrity_event`.

## 5. Rule Catalog (Process Integrity, Guard & License Rules)

| Rule ID | Dimension | Severity | Basis | Summary | Rationale |
|---|---|---|---|---|---|
| `AGT-001` | `agent_integrity` | `high` | `HISTORY PROOF` | Tests removed alongside the code they cover | Deleting a failing test while modifying the module under test hides regressions instead of fixing them. |
| `AGT-002` | `agent_integrity` | `medium` | `HISTORY PROOF` | Tests removed without matching production code removal | Shrinking test suites without retiring the underlying functionality reduces verification coverage silently. |
| `AGT-003` | `agent_integrity` | `medium` | `AST PROOF` | Existing tests newly skipped | Adding skip decorators or `.skip` modifiers makes broken tests pass CI without verification. |
| `AGT-004` | `agent_integrity` | `medium` | `HISTORY PROOF` | Assertions removed from surviving tests | Leaving a test function executing with zero or fewer assertions preserves pass counts while stripping verification. |
| `AGT-005` | `agent_integrity` | `high` | `AST PROOF` | Trivially-true assertion introduced | Tautological assertions such as `assert True` or `expect(x).toBe(x)` always succeed regardless of application behavior. |
| `AGT-006` | `agent_integrity` | `low` | `PATTERN` | Assertion loosened | Relaxing exact value equality to `is not None` or `.toBeDefined()` can mask incorrect results. |
| `AGT-007` | `agent_integrity` | `high` | `PATTERN` | CI verification step weakened or removed | Bypassing exit codes with `\|\| true` or `continue-on-error: true` prevents CI from blocking broken merges. |
| `AGT-008` | `agent_integrity` | `medium` | `PATTERN` | Quality gate lowered | Lowering coverage thresholds, lint severities, or TypeScript strictness weakens baseline enforcement. |
| `AGT-009` | `agent_integrity` | `low` | `PATTERN` | Suppression directives added | Bursts of inline suppressions or security-rule suppressions beside dangerous calls bypass static safeguards. |
| `AGT-010` | `security` | `high` | `PATTERN` | Secret present in history, absent at HEAD | Credentials removed in later commits remain extractable from git history until rotated and purged. |
| `AGT-011` | `agent_integrity` | `low` | `HISTORY PROOF` | Large change without test changes | Unusually large changes touching no tests carry elevated risk of unverified behavior changes. |
| `AGT-012` | `agent_integrity` | `medium` | `AST PROOF` | Focus marker present at HEAD | Test focus modifiers (`.only`, `fit`, `fdescribe`) cause test runners to silently skip the rest of the suite. |
| `GRD-001` | `agent_integrity` | `high` | `HISTORY PROOF` | Guard policy or baseline modified | Allowing an unreviewed edit or automated session to relax `.codit.yml` or `.codit/baseline.json` undermines local safeguards. |
| `GRD-002` | `agent_integrity` | `high` | `PATTERN` | Destructive command targets tests or CI | Destructive shell commands (`rm`, `mv`, `truncate`, `sed -i`, redirects) targeting tests or CI can remove safeguards outside file edit tools. |
| `LIC-001` | `licenses` | `high` | `PATTERN` | Strong-copyleft dependency | Strong copyleft dependencies may impose reciprocal source disclosure obligations under proprietary or incompatible permissive projects. |
| `LIC-002` | `licenses` | `high` | `PATTERN` | Network-copyleft dependency | Network copyleft terms extend obligations across hosted network interaction. |
| `LIC-003` | `licenses` | `low` | `PATTERN` | Weak-copyleft dependency | Weak copyleft licenses typically impose obligations on modified library files or static linking. |
| `LIC-004` | `licenses` | `medium` | `PATTERN` | Unknown dependency license | Packages without verifiable license metadata cannot be treated as permissive. |
| `LIC-005` | `licenses` | `high` | `PATTERN` | Source-available license dependency | Source-available licenses restrict commercial or production hosting rights. |
| `LIC-006` | `licenses` | `medium` | `PATTERN` | Missing project license declaration | Compatibility assessment requires knowing the target project's own licensing posture. |
| `LIC-007` | `licenses` | `medium` | `PATTERN` | Foreign license header in source file | Mixed license headers can indicate copied third-party snippets with conflicting terms. |
| `LIC-008` | `licenses` | `medium` | `PATTERN` | Vendored directory license mismatch | Undeclared third-party vendored code misses dependency inventory and license review. |

## 6. Effort Estimation Model (`effort_model_version` `1.0.0`)

Person-days are reported as an explicit assumption-labeled range (`min..max` with `likely`, assuming 8 engineering hours per person-day). ONNX ML model outputs are never combined with or added to this effort model.

| Rule Key | Min (h) | Likely (h) | Max (h) | Unit |
|---|---:|---:|---:|---|
| `SEC-SECRET` | `2.0` | `4.0` | `8.0` | per unique secret (rotate, purge) |
| `VULN-DEP` | `1.0` | `2.0` | `6.0` | per dependency |
| `AGT-001` | `2.0` | `4.0` | `12.0` | per event |
| `AGT-002` | `1.0` | `3.0` | `8.0` | per event |
| `AGT-003` | `0.5` | `1.5` | `4.0` | per test file |
| `AGT-004` | `1.0` | `2.0` | `6.0` | per event |
| `AGT-005` | `0.5` | `1.0` | `3.0` | per assertion |
| `AGT-007` | `1.0` | `2.0` | `6.0` | per workflow |
| `AGT-008` | `0.5` | `1.0` | `3.0` | per gate |
| `AGT-009` | `1.0` | `3.0` | `8.0` | per burst |
| `AGT-010` | `2.0` | `4.0` | `12.0` | per unique secret |
| `AGT-011` | `2.0` | `6.0` | `16.0` | per commit |
| `AGT-012` | `0.25` | `0.5` | `1.0` | per marker |
| `LIC-001` | `4.0` | `16.0` | `80.0` | per dependency |
| `LIC-002` | `8.0` | `24.0` | `120.0` | per dependency |
| `LIC-003` | `0.5` | `1.0` | `4.0` | per dependency |
| `LIC-004` | `1.0` | `2.0` | `8.0` | per dependency |
| `LIC-005` | `4.0` | `16.0` | `80.0` | per dependency |
| `LIC-006` | `0.25` | `0.5` | `1.0` | per repository |
| `LIC-007` | `1.0` | `3.0` | `12.0` | per file group |
| `LIC-008` | `1.0` | `3.0` | `12.0` | per directory |

Fallback hours per unlisted finding by severity: `low` = `1.0/2.0/4.0`, `medium` = `2.0/6.0/16.0`, `high` = `4.0/12.0/40.0`, `critical` = `8.0/24.0/80.0`.
