## 2025-08-12 15:50 UTC

Pivot to core repricing loop: After days of effort fighting the seller/opponent scraping, we decided to prioritise the main pricing loop and make sellers optional. We added new tasks CORE-LOOP-001 to CORE-LOOP-004, which cover settings persistence, returning offers without opponents, computing dry-run proposals, and adding a scheduler. We moved UI-002 back to the backlog. STATE.json updated to point to CORE-LOOP-001. The default for offers API calls is withOpponents=false so that endpoints always return valid data. Seller scraping will be revisited later with caching and optional Playwright fallback.
\- 2025-08-13: A.1 Create size normalization and ignore rules for CRM processing (crm-system)
\- 2025-08-13: A.2 Add sales repair script to normalize sizes, derive sku_key, drop ignored prefixes (crm-system)
\- 2025-08-13: A.3 Update processing to prefer fixed sales, regenerate outputs, add coverage report (crm-system)
