# GOALS.md — North Star & Outcomes

**North Star (Hybrid architecture)**
- Keep all business logic (parser, sizing, inventory math, PDFs, PO engine) in **Python**.
- Use **n8n** strictly as thin glue: 2 small flows (Orders+WhatsApp, Inventory+OOS).
- Deterministic, testable, minimal moving parts, easy to scale or swap vendors.

**Business Outcomes (measurable)**
- Single source of truth for stock per `sku_key` across all Kaspi offers & stores.
- Automated stock sync: disable all duplicate offers when total stock ≤ 0; re‑enable on restock.
- Automated order → size consultation → decision (15:00 fallback) → labels → shipment logging.
- Continuous demand denoising, SS/ROP, and PO planning (per size) with ROIC view.
- One‑click daily operations + PDF & CSV artifacts for auditability.

**Success Criteria**
- >95% in‑stock service level on planned SKUs.
- <5 minutes operator time for 60–100 orders/day (from morning intake to labels).
- Zero oversells from duplicate offers (cross‑store OOS coupling enforced).
- Weekly PO plan generated with per‑size allocations and ROI evidence.

**Scope guardrails**
- Business rules and math live in Python (never encoded in n8n flows).
- Assistants (Codex) may update `TASKS.yaml`, `PROGRESS.md`, `ISSUES.md`, `DECISIONS.md` only—never change GOALS/RULES without Owner approval stamp (see RULES.md).
