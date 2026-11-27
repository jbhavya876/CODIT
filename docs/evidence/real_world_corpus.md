# Real-World Public Repository Validation Dataset

Automated history-audit capture across **19** real public permissive repositories (`depth <= 40` commits per repo), yielding **48** total flagged events and a stratified sample of **48** events for independent human labeling.

## 1. Audited Repositories

| Repository | License | Commits Analyzed | Declared Agent Commits | Findings Emitted | Wall Time (s) |
|---|---|---:|---:|---:|---:|
| `BardLaudian/ghostrules` | `permissive` | 40 | 16 | 18 | 17.15 |
| `bigtaoo/potion-siege` | `permissive` | 40 | 38 | 17 | 26.4 |
| `kevinwellborn/cyberteaches` | `permissive` | 40 | 39 | 5 | 16.99 |
| `h0useRus/JoystickGobloon` | `permissive` | 40 | 12 | 2 | 43.17 |
| `Treybm3/tm-design-portfolio` | `permissive` | 25 | 18 | 2 | 2.42 |
| `ArtemIonov123/evolution-world-privacy` | `permissive` | 40 | 40 | 1 | 4.2 |
| `qkfn23-droid/mogumoon-` | `permissive` | 40 | 39 | 1 | 6.95 |
| `victoralvarezalegria/alegria-music` | `permissive` | 40 | 40 | 1 | 7.02 |
| `QuanhongDing/data-travel` | `permissive` | 40 | 40 | 0 | 10.93 |
| `Starsjoy/landing` | `permissive` | 40 | 37 | 0 | 7.69 |
| `Ventusltd/star-maker` | `permissive` | 40 | 15 | 0 | 15.86 |
| `AVEducate/truck-packology` | `permissive` | 40 | 40 | 0 | 3.22 |
| `ZhouYinLong-lab/Dog-Awesome` | `permissive` | 18 | 5 | 0 | 1.65 |
| `mentifaber/Cartograph` | `permissive` | 20 | 18 | 0 | 2.34 |
| `lehagutman1984-coder/aineron` | `permissive` | 40 | 40 | 0 | 7.62 |
| `anthropics/claude-code` | `MIT/Source` | 40 | 0 | 1 | 23.67 |
| `Mjeerten/Vakantie-Searchbot` | `permissive` | 40 | 27 | 0 | 2.36 |
| `calvinquentin1/rbaclp` | `permissive` | 40 | 27 | 0 | 14.77 |
| `Pengeszikra/3Draft` | `permissive` | 40 | 39 | 0 | 5.63 |

## 2. Stratified Sample for Independent Review (48 events)

| # | Repository | Commit | Rule | Severity | Confidence | Evidence | Event Summary | Reviewer Label (`true_positive`/`false_positive`/`unclear`) | Reviewer Notes |
|---:|---|---|---|---|---|---|---|---|---|
| 1 | `BardLaudian/ghostrules` | `dcf37e30bf` | `AGT-001` | `high` | `high` | `tests/test_ci_files.py:319` | Commit dcf37e3 removed 2 test(s) from tests/test_ci_files.py and also changed code those tests cover. | _PENDING_ | _PENDING_ |
| 2 | `BardLaudian/ghostrules` | `d52fd4de9c` | `AGT-004` | `medium` | `medium` | `tests/test_reporters.py:106` | Commit d52fd4d reduced assertions in 1 surviving test(s) in tests/test_reporters.py. | _PENDING_ | _PENDING_ |
| 3 | `BardLaudian/ghostrules` | `e05d677786` | `AGT-005` | `high` | `high` | `tests/test_context_command.py:194` | Commit e05d677 added an assertion that cannot fail (assert_x_eq_x) in tests/test_context_command.py. | _PENDING_ | _PENDING_ |
| 4 | `bigtaoo/potion-siege` | `2ff4d5f26e` | `AGT-006` | `low` | `low` | `src/view/SideInfo.test.ts:311` | Commit 2ff4d5f replaced strict assertions with weaker truthiness/non-null checks in src/view/SideInfo.test.ts. | _PENDING_ | _PENDING_ |
| 5 | `BardLaudian/ghostrules` | `10575c0d9a` | `AGT-009` | `low` | `high` | `tests/test_mcp_config.py:11` | Commit 10575c0 added 6 linter/security suppression directive(s) in tests/test_mcp_config.py. | _PENDING_ | _PENDING_ |
| 6 | `kevinwellborn/cyberteaches` | `7007cd3d59` | `AGT-011` | `low` | `high` | `academy/cloud.js:1` | Commit 7007cd3 changed 4 files (999 production lines) with zero test file updates. | _PENDING_ | _PENDING_ |
| 7 | `BardLaudian/ghostrules` | `0bbd41652a` | `AGT-001` | `high` | `medium` | `tests/test_agents_claude.py:512` | Commit 0bbd416 removed 4 test(s) from tests/test_agents_claude.py and also changed code those tests cover. | _PENDING_ | _PENDING_ |
| 8 | `bigtaoo/potion-siege` | `2d05dc8348` | `AGT-004` | `medium` | `medium` | `src/sim/rebrew.test.ts:46` | Commit 2d05dc8 reduced assertions in 1 surviving test(s) in src/sim/rebrew.test.ts. | _PENDING_ | _PENDING_ |
| 9 | `bigtaoo/potion-siege` | `dc25eb3fe5` | `AGT-005` | `high` | `high` | `src/sim/week.test.ts:45` | Commit dc25eb3 added an assertion that cannot fail (expect(X).toEqual(X)) in src/sim/week.test.ts. | _PENDING_ | _PENDING_ |
| 10 | `BardLaudian/ghostrules` | `fe32f9e679` | `AGT-009` | `low` | `high` | `src/ghostrules/cli.py:109` | Commit fe32f9e added 10 linter/security suppression directive(s) in src/ghostrules/cli.py. | _PENDING_ | _PENDING_ |
| 11 | `kevinwellborn/cyberteaches` | `199566a43c` | `AGT-011` | `low` | `high` | `repository:1` | Commit 199566a changed 307 files (0 production lines) with zero test file updates. | _PENDING_ | _PENDING_ |
| 12 | `BardLaudian/ghostrules` | `0bbd41652a` | `AGT-001` | `high` | `medium` | `tests/test_agents_repo.py:32` | Commit 0bbd416 removed 1 test(s) from tests/test_agents_repo.py and also changed code those tests cover. | _PENDING_ | _PENDING_ |
| 13 | `BardLaudian/ghostrules` | `e05d677786` | `AGT-009` | `low` | `high` | `src/ghostrules/agents/base.py:203` | Commit e05d677 added 15 linter/security suppression directive(s) in src/ghostrules/agents/base.py. | _PENDING_ | _PENDING_ |
| 14 | `kevinwellborn/cyberteaches` | `862197dc1c` | `AGT-011` | `low` | `high` | `apcsa/book-questions.js:1` | Commit 862197d changed 12 files (4242 production lines) with zero test file updates. | _PENDING_ | _PENDING_ |
| 15 | `BardLaudian/ghostrules` | `0bbd41652a` | `AGT-001` | `high` | `medium` | `tests/test_lock.py:330` | Commit 0bbd416 removed 1 test(s) from tests/test_lock.py and also changed code those tests cover. | _PENDING_ | _PENDING_ |
| 16 | `BardLaudian/ghostrules` | `767bf1f3a1` | `AGT-009` | `low` | `high` | `src/ghostrules/reporters/context.py:22` | Commit 767bf1f added 24 linter/security suppression directive(s) in src/ghostrules/reporters/context.py. | _PENDING_ | _PENDING_ |
| 17 | `kevinwellborn/cyberteaches` | `65cd021d1e` | `AGT-011` | `low` | `high` | `apcybersecurity/exam/data.js:1` | Commit 65cd021 changed 4 files (1118 production lines) with zero test file updates. | _PENDING_ | _PENDING_ |
| 18 | `BardLaudian/ghostrules` | `0bbd41652a` | `AGT-001` | `high` | `medium` | `tests/test_scan_imports.py:295` | Commit 0bbd416 removed 2 test(s) from tests/test_scan_imports.py and also changed code those tests cover. | _PENDING_ | _PENDING_ |
| 19 | `BardLaudian/ghostrules` | `37159bad05` | `AGT-009` | `low` | `high` | `bench/run.py:32` | Commit 37159ba added 13 linter/security suppression directive(s) in bench/run.py. | _PENDING_ | _PENDING_ |
| 20 | `kevinwellborn/cyberteaches` | `85598d89de` | `AGT-011` | `low` | `high` | `apcybersecurity/exam/data1.js:1` | Commit 85598d8 changed 5 files (960 production lines) with zero test file updates. | _PENDING_ | _PENDING_ |
| 21 | `BardLaudian/ghostrules` | `f6a881584d` | `AGT-001` | `high` | `medium` | `tests/test_docs.py:58` | Commit f6a8815 removed 1 test(s) from tests/test_docs.py and also changed code those tests cover. | _PENDING_ | _PENDING_ |
| 22 | `BardLaudian/ghostrules` | `e817d48d6c` | `AGT-009` | `low` | `high` | `src/ghostrules/cli.py:218` | Commit e817d48 added 6 linter/security suppression directive(s) in src/ghostrules/cli.py. | _PENDING_ | _PENDING_ |
| 23 | `h0useRus/JoystickGobloon` | `50f0998a88` | `AGT-011` | `low` | `high` | `repository:1` | Commit 50f0998 changed 271 files (0 production lines) with zero test file updates. | _PENDING_ | _PENDING_ |
| 24 | `BardLaudian/ghostrules` | `37159bad05` | `AGT-001` | `high` | `medium` | `tests/test_ci_files.py:102` | Commit 37159ba removed 1 test(s) from tests/test_ci_files.py and also changed code those tests cover. | _PENDING_ | _PENDING_ |
| 25 | `BardLaudian/ghostrules` | `e38c5cc6ab` | `AGT-009` | `low` | `high` | `.claude/hooks/log_tool_call.py:22` | Commit e38c5cc added 11 linter/security suppression directive(s) in .claude/hooks/log_tool_call.py. | _PENDING_ | _PENDING_ |
| 26 | `h0useRus/JoystickGobloon` | `cb1a9059d5` | `AGT-011` | `low` | `high` | `repository:1` | Commit cb1a905 changed 298 files (0 production lines) with zero test file updates. | _PENDING_ | _PENDING_ |
| 27 | `BardLaudian/ghostrules` | `8d65b35e55` | `AGT-001` | `high` | `medium` | `tests/test_bench.py:167` | Commit 8d65b35 removed 1 test(s) from tests/test_bench.py and also changed code those tests cover. | _PENDING_ | _PENDING_ |
| 28 | `Treybm3/tm-design-portfolio` | `46620e8df0` | `AGT-011` | `low` | `high` | `app/components/ChatWidget.tsx:1` | Commit 46620e8 changed 2 files (818 production lines) with zero test file updates. | _PENDING_ | _PENDING_ |
| 29 | `BardLaudian/ghostrules` | `d7fdb703ee` | `AGT-001` | `high` | `high` | `tests/test_robustness_limits.py:29` | Commit d7fdb70 removed 1 test(s) from tests/test_robustness_limits.py and also changed code those tests cover. | _PENDING_ | _PENDING_ |
| 30 | `Treybm3/tm-design-portfolio` | `d96815e105` | `AGT-011` | `low` | `high` | `app/page.tsx:1` | Commit d96815e changed 1 files (855 production lines) with zero test file updates. | _PENDING_ | _PENDING_ |
| 31 | `bigtaoo/potion-siege` | `456ccf3e8f` | `AGT-001` | `high` | `high` | `src/view/shrink.test.ts:6` | Commit 456ccf3 removed 2 test(s) from src/view/shrink.test.ts and also changed code those tests cover. | _PENDING_ | _PENDING_ |
| 32 | `ArtemIonov123/evolution-world-privacy` | `ae8fb54e9f` | `AGT-011` | `low` | `high` | `neon-block-hands/scripts/check_game.js:1` | Commit ae8fb54 changed 2 files (1850 production lines) with zero test file updates. | _PENDING_ | _PENDING_ |
| 33 | `bigtaoo/potion-siege` | `f6f1a6e44f` | `AGT-001` | `high` | `medium` | `src/view/overlay/cardNudge.test.ts:12` | Commit f6f1a6e removed 3 test(s) from src/view/overlay/cardNudge.test.ts and also changed code those tests cover. | _PENDING_ | _PENDING_ |
| 34 | `qkfn23-droid/mogumoon-` | `1ae8976c2e` | `AGT-011` | `low` | `high` | `repository:1` | Commit 1ae8976 changed 315 files (0 production lines) with zero test file updates. | _PENDING_ | _PENDING_ |
| 35 | `bigtaoo/potion-siege` | `fe82fa2e53` | `AGT-001` | `high` | `medium` | `src/sim/commander.test.ts:80` | Commit fe82fa2 removed 2 test(s) from src/sim/commander.test.ts and also changed code those tests cover. | _PENDING_ | _PENDING_ |
| 36 | `victoralvarezalegria/alegria-music` | `12fc874ff8` | `AGT-011` | `low` | `high` | `src/app/(funnel)/apply/page.tsx:1` | Commit 12fc874 changed 5 files (1313 production lines) with zero test file updates. | _PENDING_ | _PENDING_ |
| 37 | `bigtaoo/potion-siege` | `fe82fa2e53` | `AGT-001` | `high` | `medium` | `src/view/battleView/commander.test.ts:54` | Commit fe82fa2 removed 1 test(s) from src/view/battleView/commander.test.ts and also changed code those tests cover. | _PENDING_ | _PENDING_ |
| 38 | `bigtaoo/potion-siege` | `813b94ab7e` | `AGT-001` | `high` | `high` | `src/view/nextMove.test.ts:50` | Commit 813b94a removed 1 test(s) from src/view/nextMove.test.ts and also changed code those tests cover. | _PENDING_ | _PENDING_ |
| 39 | `bigtaoo/potion-siege` | `5df476b302` | `AGT-001` | `high` | `high` | `src/view/HudPointer.test.ts:131` | Commit 5df476b removed 2 test(s) from src/view/HudPointer.test.ts and also changed code those tests cover. | _PENDING_ | _PENDING_ |
| 40 | `bigtaoo/potion-siege` | `887410ae36` | `AGT-001` | `high` | `high` | `src/appFlow.test.ts:42` | Commit 887410a removed 1 test(s) from src/appFlow.test.ts and also changed code those tests cover. | _PENDING_ | _PENDING_ |
| 41 | `bigtaoo/potion-siege` | `887410ae36` | `AGT-001` | `high` | `high` | `src/sim/tutorial.test.ts:171` | Commit 887410a removed 1 test(s) from src/sim/tutorial.test.ts and also changed code those tests cover. | _PENDING_ | _PENDING_ |
| 42 | `bigtaoo/potion-siege` | `4878e8c282` | `AGT-001` | `high` | `high` | `src/game/tutorialFlow.test.ts:168` | Commit 4878e8c removed 1 test(s) from src/game/tutorialFlow.test.ts and also changed code those tests cover. | _PENDING_ | _PENDING_ |
| 43 | `bigtaoo/potion-siege` | `2ff4d5f26e` | `AGT-001` | `high` | `high` | `src/view/Hud.test.ts:310` | Commit 2ff4d5f removed 1 test(s) from src/view/Hud.test.ts and also changed code those tests cover. | _PENDING_ | _PENDING_ |
| 44 | `bigtaoo/potion-siege` | `fc4fe730b3` | `AGT-001` | `high` | `medium` | `scripts/onboard.test.ts:136` | Commit fc4fe73 removed 1 test(s) from scripts/onboard.test.ts and also changed code those tests cover. | _PENDING_ | _PENDING_ |
| 45 | `bigtaoo/potion-siege` | `fc4fe730b3` | `AGT-001` | `high` | `high` | `src/view/home/hintPlace.test.ts:34` | Commit fc4fe73 removed 1 test(s) from src/view/home/hintPlace.test.ts and also changed code those tests cover. | _PENDING_ | _PENDING_ |
| 46 | `bigtaoo/potion-siege` | `bd37e3c37a` | `AGT-001` | `high` | `high` | `src/view/home/starChestBar.test.ts:40` | Commit bd37e3c removed 1 test(s) from src/view/home/starChestBar.test.ts and also changed code those tests cover. | _PENDING_ | _PENDING_ |
| 47 | `bigtaoo/potion-siege` | `b2c38b7886` | `AGT-001` | `high` | `high` | `src/view/home/consentPanel.test.ts:23` | Commit b2c38b7 removed 2 test(s) from src/view/home/consentPanel.test.ts and also changed code those tests cover. | _PENDING_ | _PENDING_ |
| 48 | `anthropics/claude-code` | `7ae5de41a7` | `AGT-001` | `high` | `medium` | `mods/sec-default/tests/process-env.test.ts:29` | Commit 7ae5de4 removed 3 test(s) from mods/sec-default/tests/process-env.test.ts and also changed code those tests cover. | _PENDING_ | _PENDING_ |
