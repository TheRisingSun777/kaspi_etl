# DECISIONS.md — Architecture Decision Records (ADR)

## ADR-001 Use Hybrid (Python core + 2 n8n flows)
- Context: Need determinism, few moving parts, vendor swap flexibility.
- Decision: Business logic in Python; n8n only connectors/orchestration.
- Consequences: Easier testing, clearer audits, faster future swap of WhatsApp/Kaspi auth.
- Approved: APPPROVED BY OWNER — YYYY-MM-DD HH:MM <signature>

## ADR-002 Inventory policy defaults (L=16, R=7, B=14, z=1.65, TV=0.23)
- Context: Current lead times/variability.
- Decision: Apply defaults globally with per-SKU overrides later.
- Consequences: Immediate SS/ROP viability; easy tuning via policy table.
- Approved: APPPROVED BY OWNER — YYYY-MM-DD HH:MM <signature>

APPROVED BY OWNER — 2025-10-08T21:45 adil
