# Process Forensics Corpus Metrics (`s01`–`s27`)

- **Executed:** `test_scenario_corpus_s01_to_s27_and_metrics` passed all 27 deterministic scenarios in `9.56 s`.
- **High-priority rules (`AGT-001`, `AGT-003`, `AGT-005`, `AGT-007`):**
  - **Precision:** `1.00` (threshold `>= 0.95`)
  - **Recall:** `1.00` (threshold `>= 0.85`)
- **Remaining process/attribution scenarios (`AGT-002`, `AGT-004`, `AGT-006`, `AGT-008`..`AGT-012`, `M-1`, trailers, bot accounts, caps, LFS/non-UTF-8):**
  - **Precision:** `1.00` (threshold `>= 0.90`)
- **False-positive control scenarios (`s13` file move, `s14` test rename, `s15` co-deleted source+test, `s24` CRLF, `s25` Unicode):** `0` findings emitted (`s01` clean growing tests: `0` findings).
