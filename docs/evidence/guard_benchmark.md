# `codit-guard` Performance & Verification Benchmark

- **Environment:** Windows, Python 3.13.1, 19 staged Python files (~1,900 lines), `--offline`
- **Median cold `import codit_guard.cli`:** `98.6 ms` (budget `<= 300 ms`)
- **Staged diff check latency (5 runs):** median `0.591 s`, max/p95 `0.617 s` (budget `<= 1.500 s`)
- **Offline & SARIF checks:** verified in `backend/tests/test_p4_guard.py` (`--offline` socket-blocked, SARIF 2.1.0 schema check, `a14` policy-edit check).
