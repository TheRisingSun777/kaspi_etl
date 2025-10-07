# FILE_RELATIONSHIPS.md — Keys & Joins (short)

Core keys:
- Primary: `sku_key`
- Size-level: (`sku_key`, `MY_SIZE`) — normalize (upper; XXL→2XL; adults letters only, kids numbers only)

Sales fact (SALES_KSP_CRM_*):
- Canonical: [Date, sku_key, qty, sell_price, (optional MY_SIZE)]
- Last-30 median price → baseline; fallback to Sku_Map current_avg_price
- Denoise: drop spike dates; σ = 1.4826×MAD(last-90); good_day in [median−σ, median+3σ]

SKU Map (Sku_Map_CRM_3.xlsx):
- Join on sku_key (& size when needed)
- Provides: weight_kg, base_cost_cny, current_stock_by_size
- COGS_unit = BaseCost_CNY×78.2 + Weight_kg×2.2×550

Demand & size mix (New_D_2X_size_wide_4.10.25.xlsx):
- Authoritative: D_multiplied & size shares; D_i = D × share_i
- Scenarios: D_base_est; D_store_1.7x, … (do not overwrite D_current)

Delivery bands (KSP_Delivery_rates_V5.xlsx):
- Fee by price & weight band; blended 35% city / 65% country

Econ:
- UnitProfit(VAT) = ((Price*(1−0.12) − Delivery) * (1−VAT)) − COGS_unit
