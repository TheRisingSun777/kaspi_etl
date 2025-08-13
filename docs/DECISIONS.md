### 2025-08-12: Pivot to core repricing loop

What changed? We realised chasing seller counts and scraping the public product page was blocking delivery of the core feature: automated repricing using merchant data. We added four new "CORE-LOOP" tasks and moved UI-002 back to backlog. Opponents/seller data is now optional; proposals and price adjustments will run on min/max/step logic using merchant offers only. Scraping remains a separate enhancement behind a flag.

Why? The merchant API remains reliable for our own SKUs, whereas the yml/offer-view/offers endpoint is frequently blocked. Our goal is to complete the dry-run -> proposal -> apply loop, not to perfect competitor data at the cost of weeks. Once the core loop is robust, we will revisit scraping with cache and fallback to Playwright if needed.

Impact: Developers must not block on opponents in endpoints; always return offers with withOpponents=false by default. New tasks guide implementation. The branch feat/offers-dashboard now focuses exclusively on the repricing loop.
