# PROGRESS.md — Chronological Log (append-only)

## 2025-10-06 10:00 — actor: owner
- Created protocol files and branch `inventory_foundation_v1`.
- Initial plan staged; awaiting Codex to begin P0.2.

## Template for future entries (Codex must use this):
- YYYY-MM-DD HH:MM — actor: codex — Task(s): P?.?
- Summary: what changed
- Artifacts: paths/filenames
- Commit: <conventional title>

- 2025-10-07 13:11 — actor: codex — Task(s): P0.2
- Summary: Documented legacy inventory conflicts and logged deprecation actions in protocol files.
- Artifacts: docs/protocol/AUDIT_legacy_inventory.md; docs/protocol/ISSUES.md; docs/protocol/TASKS.yaml
- Commit: protocol: audit legacy inventory artifacts and open issues (codex)
- 2025-10-07 13:38 — actor: codex — Task(s): P1.1
- Summary: Bootstrapped backend schema package with SQLAlchemy models, migration helper, and ERD snapshot.
- Artifacts: backend/app.py; backend/db/models.py; backend/db/migrate.py; backend/db/schema.sql; docs/protocol/ERD_inventory_v1.mmd
- Commit: backend: bootstrap db schema and migrate scaffold (codex)
- 2025-10-07 14:56 — actor: codex — Task(s): P1.2
- Summary: Reduced Python deps, added env placeholders, updated setup docs, and hardened hook installation notes.
- Artifacts: requirements.txt; .env.example; docs/protocol/OPERATING.md; .gitignore; scripts/etl_catalog_api.py
- Commit: build: minimal deps + env scaffolding + ops setup (codex)
- 2025-10-07 17:23 — actor: codex — Task(s): P1.2a
- Summary: Removed tenacity remnants, consolidated API retry helper, normalized gitignore entries, and added a script smoke entry point.
- Artifacts: scripts/etl_catalog_api.py; requirements.txt; .gitignore; docs/protocol/TASKS.yaml
- Commit: build: stabilize config; remove tenacity use; normalize .gitignore (codex)
- 2025-10-07 19:32 — actor: codex — Task(s): P1.3
- Summary: Added XLSX ingestion loaders and baseline CLI to populate products, size mix, and delivery bands from configured workbooks.
- Artifacts: backend/ingest/xlsx_loaders.py; backend/ingest/load_baseline.py; backend/ingest/__init__.py; docs/protocol/TASKS.yaml
- Commit: ingest: load baseline products/size-mix/delivery-bands from XLSX (codex)
- 2025-10-08 17:22 — actor: codex — Task(s): P1.4
- Summary: Implemented offers loader/CLI mapping Business_model workbook into offers with account-aware IDs and product auto-creation.
- Artifacts: backend/ingest/xlsx_offers_loader.py; backend/ingest/load_offers.py; backend/utils/config.py; docs/protocol/CONFIG.yaml; docs/protocol/TASKS.yaml
- Commit: ingest: load offers map (Business_model→offers) with account-aware IDs (codex)
- 2025-10-08 17:46 — actor: codex — Task(s): P1.3b
- Summary: Expanded delivery header synonyms with sheet autodetect, tightened size token detection, and added an XLSX inspection CLI.
- Artifacts: backend/ingest/xlsx_loaders.py; backend/ingest/inspect_xlsx.py; docs/protocol/TASKS.yaml
- Commit: ingest: harden delivery-bands header matching; strict size token detection; add inspect CLI (codex)
- 2025-10-08 19:17 — actor: codex — Task(s): P1.3c
- Summary: Added percent-based delivery band support, offers sheet autodetect, and finalized size token detection with inspector modes.
- Artifacts: backend/db/models.py; backend/ingest/xlsx_loaders.py; backend/ingest/xlsx_offers_loader.py; backend/ingest/inspect_xlsx.py; docs/protocol/TASKS.yaml
- Commit: ingest: support percent-based delivery bands; autodetect offers sheet; lock size tokenization (codex)
- 2025-10-08 19:39 — actor: codex — Task(s): P1.3d
- Summary: Finalized percent-delivery ingest and mapped store names to account IDs so real workbooks load without manual edits.
- Artifacts: backend/ingest/xlsx_offers_loader.py; backend/ingest/xlsx_loaders.py; backend/ingest/inspect_xlsx.py; docs/protocol/TASKS.yaml
- Commit: ingest: offers loader accepts Store_name + config name→id map; delivery bands pct path verified (codex)
- 2025-10-08 20:40 — actor: codex — Task(s): P1.3e
- Summary: Added SQLite reset guard, normalized delivery percent headers, mapped store names via config, and added ingest header tests.
- Artifacts: backend/db/migrate.py; backend/ingest/xlsx_loaders.py; backend/ingest/xlsx_offers_loader.py; backend/ingest/inspect_xlsx.py; backend/tests/test_ingest_headers.py; docs/protocol/OPERATING.md; docs/protocol/TASKS.yaml
- Commit: ingest: auto-upgrade delivery bands + store-name offers mapping (codex)
- 2025-10-08 21:34 — actor: codex — Task(s): P1.3f
- Summary: Finalized baseline ingest reset/inspect flow so percent delivery bands and Store_name offers import cleanly on fresh SQLite.
- Artifacts: backend/db/migrate.py; backend/ingest/xlsx_loaders.py; backend/ingest/xlsx_offers_loader.py; backend/ingest/inspect_xlsx.py; backend/tests/test_ingest_headers.py; docs/protocol/TASKS.yaml
- Commit: ingest: finalize percent delivery + store-name mapping (codex)
- 2025-10-07 14:40 — actor: codex — Task(s): P0.3
- Summary: Added protected-path guard with pre-commit hook template and installer documentation.
- Artifacts: tools/protected_paths_guard.py; hooks/pre-commit; scripts/install_hooks.sh; docs/protocol/OPERATING.md
- Commit: protocol: add protected-paths guard (pre-commit) + installer (codex)
