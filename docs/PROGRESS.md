## 2025-08-12 15:50 UTC

Pivot to core repricing loop: After days of effort fighting the seller/opponent scraping, we decided to prioritise the main pricing loop and make sellers optional. We added new tasks CORE-LOOP-001 to CORE-LOOP-004, which cover settings persistence, returning offers without opponents, computing dry-run proposals, and adding a scheduler. We moved UI-002 back to the backlog. STATE.json updated to point to CORE-LOOP-001. The default for offers API calls is withOpponents=false so that endpoints always return valid data. Seller scraping will be revisited later with caching and optional Playwright fallback.
\- 2025-08-13: A.1 Create size normalization and ignore rules for CRM processing (crm-system)
\- 2025-08-13: A.2 Add sales repair script to normalize sizes, derive sku_key, drop ignored prefixes (crm-system)
- 2025-08-13: A.3 Update processing to prefer fixed sales, regenerate outputs, add coverage report (crm-system)
\- 2025-08-13 12:20 UTC: PH1-REPAIR finalized — added size normalization (44–64, S–4XL), ignore prefixes (ELS_, PRINTER_, CARTRIDGE_, PAPER_), ran repair to produce fixed sales and delta report; counts and top dropped prefixes captured. (crm-system)
\- 2025-08-13 12:35 UTC: WA size-check outbox generated (dry-run) with template; deduped, wrote texts and whatsapp_messages.csv. (crm-system)
\- 2025-08-13 12:50 UTC: Mapping coverage + missing-by-store reports; worst stores: M-GROUP, (blank); worst models: ЧЕРНИЛА_664_ЧЕРНЫЙ, ЧЕРНИЛА_КОМПЛЕКТ, 0, (blank), XLOOKUP-artifact. (crm-system)
- 2025-08-13 10:35 UTC: C.1 Add STATE.json and OPERATING.md (crm-system)
- 2025-08-13 10:36 UTC: C.2 Refresh TASKS.yaml with PH1 tasks (done/todo) (crm-system)
- 2025-08-13 10:37 UTC: C.3 Commit updates for state, ops, tasks, progress (crm-system)
- 2025-08-13 10:41 UTC: D.1–D.3 Add DB loader, views, and CLI; committed and pushed (crm-system)
- 2025-08-13 10:45 UTC: E.1–E.2 Add daily orchestrator and run script; logs directory initialized (crm-system)
- 2025-08-13 10:58 UTC: B.1 Added WhatsApp API client (Twilio/360dialog) and .env.sample (crm-system)
- 2025-08-13 11:05 UTC: C.1–C.2 WA inbound webhook (FastAPI) + runner; docs updated (crm-system)
 - 2025-08-13 06:27 UTC: Checkpoint & rotate; Phase2 dry-run pipeline, planning/apply shells, alerts and reports in place (crm-system)
