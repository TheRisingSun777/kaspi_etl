### Data Dictionary (Phase 1)

- orderid: Order identifier (string)
- date: Order date (ISO-like string)
- store_name: Merchant/store name
- sku_key: Product model key (uppercase with underscores)
- my_size: Normalized size label (S/M/L/XL/2XL/3XL/4XL or numeric 44–64)
- sku_id: sku_key + '_' + my_size; blank when sku_key missing
- qty: Quantity (int)
- sell_price: Unit price (float)
- amount: qty * sell_price (float; derived)
- ksp_sku_id: Kaspi SKU ID (string; optional)
- customer_height: Height in centimeters (int; optional)
- customer_weight: Weight in kilograms (float; optional)
- normalized_phone: E.164 phone (+7...) when available

Reports

- missing_skus_YYYYMMDD.csv: sku_id gaps with reason and has_ksp_id
- duplicates_YYYYMMDD.csv: duplicate sales rows removed
- oversell_YYYYMMDD.csv: stock oversell before clipping
- KPI: sales_by_sku/store/size/daily_YYYYMMDD.csv

Mart

- dim_product: Product dimension including sku_id, sku_key, my_size
- dim_store: Store dimension with store_name
- dim_date: Calendar dimension for date range present
- fact_sales_YYYYMMDD: Denormalized sales facts with qty and amount


