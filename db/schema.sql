CREATE TABLE purchases (
  po_id            TEXT,
  sku_key          TEXT,
  order_date       DATE,
  arrival_date     DATE,
  qty              INTEGER,
  unit_cogs_kzt    REAL,
  freight_kzt      REAL,
  total_cogs_kzt   REAL,
  PRIMARY KEY (po_id, sku_key)
);
CREATE TABLE IF NOT EXISTS "orders" (
"order_id" INTEGER,
  "order_date" DATE,
  "status_date" DATE,
  "status" TEXT,
  "sku_name_raw" TEXT,
  "qty" INTEGER,
  "gross_price_kzt" INTEGER,
  "kaspi_fee_pct" REAL,
  "sku_key" TEXT,
  "weight_g" REAL,
  "delivery_cost_kzt" INTEGER
);
CREATE TABLE IF NOT EXISTS "products" (
"sku_id" TEXT,
  "kaspi_name_core" TEXT,
  "my_size" TEXT,
  "size_kaspi" TEXT,
  "kaspi_art_1" TEXT,
  "sku_id_ksp" TEXT,
  "kaspi_name_source" TEXT,
  "initial_ksp_price" TEXT,
  "stock_entered" INTEGER,
  "sku_key" TEXT,
  "secondary" TEXT,
  "product_type" TEXT,
  "sub_category" TEXT,
  "brand" TEXT,
  "model" TEXT,
  "color" TEXT,
  "our_size" TEXT,
  "gender" TEXT,
  "season" TEXT,
  "base_cost_cny" REAL,
  "weight_kg" REAL,
  "store_name" TEXT,
  "kaspi_art_2" TEXT
);
CREATE TABLE IF NOT EXISTS "catalog_enhanced" (
"SKU_ID" TEXT,
  "Kaspi_name_core" TEXT,
  "MY_SIZE" TEXT,
  "Size_kaspi" TEXT,
  "Kaspi_art_1" TEXT,
  "SKU_ID_KSP" TEXT,
  "Kaspi_name_source" TEXT,
  "Initial_KSP_Price" TEXT,
  "Stock_entered" TEXT,
  "SKU_key" TEXT,
  "Secondary" TEXT,
  "Product_Type" TEXT,
  "Sub_Category" TEXT,
  "Brend" TEXT,
  "Model" TEXT,
  "Color" TEXT,
  "Our_Size" TEXT,
  "Gender" TEXT,
  "Season" TEXT,
  "BaseCost_CNY" TEXT,
  "Weight_kg" TEXT,
  "Gender2" TEXT,
  "Store_name" TEXT,
  "Kaspi_art_2" TEXT,
  "Unnamed: 24" TEXT,
  "Unnamed: 25" TEXT,
  "Weight_kg_cleaned" REAL,
  "Initial_KSP_Price_cleaned" REAL,
  "Stock_entered_cleaned" INTEGER
);
CREATE TABLE customers (
          id TEXT PRIMARY KEY,
          phone TEXT,
          name TEXT,
          created_at TEXT
        );
CREATE TABLE wa_outbox (
          id TEXT PRIMARY KEY,
          order_id TEXT,
          to_phone TEXT,
          template TEXT,
          payload_json TEXT,
          status TEXT,
          created_at TEXT
        );
CREATE TABLE wa_inbox (
          id TEXT PRIMARY KEY,
          order_id TEXT,
          from_phone TEXT,
          text TEXT,
          parsed_json TEXT,
          created_at TEXT
        );
CREATE TABLE size_recommendations (
          order_id TEXT,
          recommended_size TEXT,
          confidence REAL,
          height INT,
          weight INT,
          final_size TEXT,
          created_at TEXT
        );
CREATE TABLE workflows (
          order_id TEXT PRIMARY KEY,
          state TEXT,
          updated_at TEXT,
          store_name TEXT
        );
CREATE TABLE events_log (
          id TEXT PRIMARY KEY,
          order_id TEXT,
          kind TEXT,
          data_json TEXT,
          created_at TEXT
        );
CREATE INDEX idx_wa_outbox_to_phone ON wa_outbox(to_phone);
CREATE INDEX idx_wa_inbox_from_phone ON wa_inbox(from_phone);
CREATE INDEX idx_workflows_state ON workflows(state);
CREATE INDEX idx_events_log_order ON events_log(order_id);
CREATE TABLE stock_deltas (
          order_id TEXT PRIMARY KEY,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
CREATE TABLE sales (
  orderid TEXT,
  date TEXT,
  sku_id TEXT,
  store_name TEXT,
  qty INTEGER,
  sell_price REAL,
  customer_height REAL,
  customer_weight REAL,
  ksp_sku_id TEXT,
  sku_key TEXT,
  my_size TEXT
);
CREATE INDEX idx_sales_orderid ON sales(orderid);
CREATE INDEX idx_sales_sku_id ON sales(sku_id);
CREATE INDEX idx_sales_store ON sales(store_name);
CREATE VIEW v_sales_by_sku AS
  SELECT sku_id, SUM(qty) AS total_qty,
         SUM(COALESCE(sell_price, 0) * qty) AS revenue
  FROM sales
  GROUP BY sku_id
/* v_sales_by_sku(sku_id,total_qty,revenue) */;
CREATE VIEW v_sales_by_model_size AS
  SELECT sku_key, my_size, SUM(qty) AS total_qty
  FROM sales
  GROUP BY sku_key, my_size
/* v_sales_by_model_size(sku_key,my_size,total_qty) */;
CREATE VIEW v_sales_by_store_day AS
  SELECT store_name, date, SUM(qty) AS total_qty,
         SUM(COALESCE(sell_price, 0) * qty) AS revenue
  FROM sales
  GROUP BY store_name, date
/* v_sales_by_store_day(store_name,date,total_qty,revenue) */;
