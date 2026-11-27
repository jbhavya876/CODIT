# 20-Concurrent-Audit Load & Worker Isolation Evidence (`--workers 2`)

- **Server:** `uvicorn backend.app:create_app --factory --workers 2`
- **Concurrency:** `20` concurrent ZIP audits (`14` files each, distinct `TARGET_UNIQ_00..19` tokens)
- **Completed:** `20 / 20` succeeded (`202` -> polling -> `completed` -> `GET /report`)
- **Total Wall-Clock Duration:** `14.65 s`
- **Combined Worker Tree Working Set:** `111.5 MB` (configured per-worker ceiling: `1024 MB`)
- **Cross-Audit Isolation:** `0` cross-audit leaks (`TARGET_UNIQ_i` verified absent from all `j != i` reports).
- **Reaper Verification:** verified in `backend/tests/test_p0_foundation.py::test_reapers_mark_stale_running_and_delete_expired`.
