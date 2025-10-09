## 2025-10-09 14:10 — actor: codex
- Delivery bands ingestion now treats zero fees as valid values and defaults PlatformFeePct to 0.12 when blank; skip logs enumerate missing fields.
- Stabilized inspect_xlsx alias maps (delivery/offers) and added a size-mix loader CLI that normalizes shares when source sheets are available.
- Pre-commit guard now resolves repo roots via git before delegating to protected_paths_guard.py.
- Previously only 1 delivery row was accepted (5 skipped); loader now accepts rows even when fee columns are 0 (skips only truly missing rows).
- Added scripts/dev_sanity.sh with step-by-step checks (fill DELIVERY_XLSX and OFFERS_XLSX paths, then run). OK to run after user fills paths.

## 2025-10-09 19:45 — actor: codex
- Hardened `backend/db/migrate.py` to auto-install requirements (preferring project `requirements.txt`) when `sqlalchemy` is missing, so `python3 backend/db/migrate.py --reset` no longer fails with ModuleNotFoundError.

## 2025-10-09 20:05 — actor: codex
- Added PyYAML bootstrap alongside SQLAlchemy in `backend/db/migrate.py` so fresh environments missing `yaml` are auto-healed before migrations run.

## 2025-10-09 20:25 — actor: codex
- 2025-10-09 — delivery aliases unified in xlsx_loaders.py; loader accepts rows with 0% fees; PlatformFeePct defaults to 0.12 if blank; inspect_xlsx now uses the same map.
