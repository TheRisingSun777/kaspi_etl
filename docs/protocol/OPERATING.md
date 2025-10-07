# OPERATING.md — Runbook & Assistant Protocol

## Daily Operator (you)
1. Morning
   - Open dashboard (later) or check `/report/inventory` and `/report/kpis`.
   - (If manual) Upload latest label ZIP → trigger `/labels/build`.
2. Before 15:00
   - Skim orders with no reply; system will auto-decide at 15:00.
3. After 15:00
   - Print grouped PDFs; stage parcels; handover to courier.
4. Weekly
   - Review `/report/po` suggestions; approve PO batch.

## Assistant Update Protocol (Codex)
- Before any code change:
  - Read `GOALS.md`, `RULES.md`, `ARCHITECTURE.md`.
  - Update `TASKS.yaml` status (e.g., P1.2 → in_progress) with timestamp + `actor: codex`.
- After change:
  - Append to `PROGRESS.md` with: date/time, task id(s), short summary, artifact paths, commit title.
  - If a bug found, append to `ISSUES.md` and link commit that fixes it.
  - If a rule/math changes, add ADR to `DECISIONS.md` and request Owner stamp.

## Manual Overrides (you)
- You may edit any file.
- To approve a math/policy change, add:  
  `APPROVED BY OWNER — YYYY‑MM‑DD HH:MM <signature>`  
  in the relevant section of RULES.md or the ADR entry.

## Backups
- DB snapshot weekly to `backups/db/erp_YYYYMMDD.sqlite` (later Postgres dump).
- Artifacts: PDFs/CSVs in `outbox/` dated folders.

## Secrets
- Never commit tokens. Use `.env` or `config.local.yaml` (git‑ignored).
