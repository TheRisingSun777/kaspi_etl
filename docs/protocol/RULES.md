# RULES.md — Operating Rules & Invariants

## Invariants (must always hold)
- **Single truth by `sku_key`**: Stock and policy compute at `sku_key` (model) level; multiple Kaspi offers map to one `sku_key`.
- **15:00 rule**: If no WhatsApp reply by 15:00 local, ship the ordered size.
- **Boundary rule**: If between sizes, prefer the ordered size unless clear evidence to size up/down.
- **Idempotency**: Any job may safely re-run without double-applying effects.
- **Explainability**: Every automated decision must be logged with `decision_reason`.

## Protected Paths (DO NOT TOUCH)
These automations are business‑critical and must not be modified, moved, or deleted by assistants or refactors. Any change requires explicit Owner approval (PR review) and an ADR with Owner stamp.

**Patterns (repo‑relative):**
- docs/ops/**              # all operational scripts & runbooks (keep working automations)
- docs/perfume_offers_scrape.md
- scripts/scrape_kaspi_offers.ts
- docs/ops/kaspi/scraper/scrape.command
- docs/ops/kaspi/run_today_and_archive_input.command
- docs/ops/kaspi/run_import_orders_all_dates.command
- docs/ops/kaspi/run_import_orders.command
- run_perfume_scrape.command
- docs/ops/kaspi/SALES_KSP_CRM_V3.xlsx

**Assistant rule:** Assistants MUST NOT modify these paths. Any attempt must be blocked by repo guardrails and rejected in code review.

## Inventory Policy (defaults)
- Lead time (L): **16** days
- Review cadence (R): **7** days
- Floor buffer (B): **14** days
- Service level (z): **1.65** (~95%)
- Mix variance floor (TV): **0.23**
- VAT: **3%**
- Platform fee: **12%**
- Delivery fee: price-band × weight-band with **35% city / 65% country** blend

## Safety stock & reorder math (SKU level)
- σ = 1.4826 × MAD(last‑90 daily units) excluding spike days
- SS_demand = z × σ × √L
- SS_floor  = D × B
- SS_mix    = TV × D × L
- SS_total  = SS_demand + SS_floor + SS_mix
- ROP       = D × L + SS_total
- T_post    = R + (SS_total / D)

## Size-level allocation (per arrival)
- Pre_i  = on-hand before arrival (per size)
- Alloc_i = max(0, T_post × D_i − Pre_i)
- Post_i  = Pre_i + Alloc_i
- DoC_i   = Post_i / D_i

## Assistant (Codex) Update Rules — STRICT
- MAY edit: `TASKS.yaml` (status/owner/notes), `PROGRESS.md` (append only), `ISSUES.md` (append/close), `DECISIONS.md` (append ADR).
- MUST NOT edit: `GOALS.md`, `RULES.md`, `ARCHITECTURE.md` without Owner stamp.
- Owner stamp: add a line `APPROVED BY OWNER — YYYY‑MM‑DD HH:MM <signature>` before any change.
- Every assistant edit must:
  - Include ISO timestamp and “actor: codex” tag.
  - Add a concise commit message in `PROGRESS.md` (also used as Git commit title).
- Changes to math/policy require an ADR entry in `DECISIONS.md` and Owner stamp.

## Commit Guidance
- Conventional commits; examples:
  - `protocol: update TASKS.yaml P1.3 → in_progress (codex)`
  - `inventory: add /inventory/update endpoint stub`
  - `forecast: compute sigma MAD90 + diagnostics`
