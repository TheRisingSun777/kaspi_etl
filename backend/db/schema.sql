
CREATE TABLE delivery_bands (
	id INTEGER NOT NULL, 
	price_min NUMERIC(10, 2) NOT NULL, 
	price_max NUMERIC(10, 2) NOT NULL, 
	weight_min_kg FLOAT NOT NULL, 
	weight_max_kg FLOAT NOT NULL, 
	fee_city_kzt NUMERIC(10, 2) NOT NULL, 
	fee_country_kzt NUMERIC(10, 2) NOT NULL, 
	PRIMARY KEY (id)
)




CREATE TABLE inventory_policy (
	id INTEGER DEFAULT '1' NOT NULL, 
	"L_days" INTEGER NOT NULL, 
	"R_days" INTEGER NOT NULL, 
	"B_days" INTEGER NOT NULL, 
	z_service FLOAT NOT NULL, 
	tv_floor FLOAT NOT NULL, 
	vat_pct FLOAT NOT NULL, 
	platform_pct FLOAT NOT NULL, 
	delivery_blend_city FLOAT NOT NULL, 
	delivery_blend_country FLOAT NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_inventory_policy_singleton CHECK (id = 1)
)




CREATE TABLE products (
	sku_key VARCHAR(64) NOT NULL, 
	title VARCHAR(255) NOT NULL, 
	category VARCHAR(80), 
	gender VARCHAR(20), 
	weight_kg FLOAT, 
	base_cost_cny FLOAT, 
	active BOOLEAN DEFAULT '1' NOT NULL, 
	PRIMARY KEY (sku_key)
)




CREATE TABLE demand_forecasts (
	sku_key VARCHAR(64) NOT NULL, 
	scenario VARCHAR(32) DEFAULT 'current' NOT NULL, 
	"D_current" FLOAT, 
	sigma_90 FLOAT, 
	updated_at DATETIME, 
	PRIMARY KEY (sku_key, scenario), 
	FOREIGN KEY(sku_key) REFERENCES products (sku_key) ON DELETE CASCADE
)




CREATE TABLE desired_allocations (
	sku_key VARCHAR(64) NOT NULL, 
	account_id VARCHAR(64) NOT NULL, 
	alloc_qty INTEGER DEFAULT '0' NOT NULL, 
	updated_at DATETIME, 
	PRIMARY KEY (sku_key, account_id), 
	FOREIGN KEY(sku_key) REFERENCES products (sku_key) ON DELETE CASCADE
)




CREATE TABLE diagnostics (
	sku_key VARCHAR(64) NOT NULL, 
	good_days_total INTEGER, 
	good_days_90 INTEGER, 
	data_rating_9mo FLOAT, 
	data_rating_12mo FLOAT, 
	updated_at DATETIME, 
	PRIMARY KEY (sku_key), 
	FOREIGN KEY(sku_key) REFERENCES products (sku_key) ON DELETE CASCADE
)




CREATE TABLE offers (
	offer_id VARCHAR(64) NOT NULL, 
	account_id VARCHAR(64) NOT NULL, 
	sku_key VARCHAR(64) NOT NULL, 
	color VARCHAR(64), 
	size_label VARCHAR(32), 
	kaspi_product_code VARCHAR(64), 
	PRIMARY KEY (offer_id), 
	CONSTRAINT uq_offers_account_offer UNIQUE (account_id, offer_id), 
	FOREIGN KEY(sku_key) REFERENCES products (sku_key) ON DELETE CASCADE
)




CREATE TABLE po_plan (
	po_id VARCHAR(64) NOT NULL, 
	sku_key VARCHAR(64) NOT NULL, 
	status VARCHAR(32), 
	t_post_days INTEGER, 
	alloc_json_by_size JSON, 
	pre_json JSON, 
	post_json JSON, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (po_id), 
	FOREIGN KEY(sku_key) REFERENCES products (sku_key) ON DELETE CASCADE
)




CREATE TABLE sales_daily (
	sku_key VARCHAR(64) NOT NULL, 
	date DATE NOT NULL, 
	qty INTEGER DEFAULT '0' NOT NULL, 
	revenue_kzt NUMERIC(14, 2) DEFAULT '0' NOT NULL, 
	PRIMARY KEY (sku_key, date), 
	FOREIGN KEY(sku_key) REFERENCES products (sku_key) ON DELETE CASCADE
)




CREATE TABLE size_mix (
	sku_key VARCHAR(64) NOT NULL, 
	size_label VARCHAR(32) NOT NULL, 
	share FLOAT NOT NULL, 
	PRIMARY KEY (sku_key, size_label), 
	FOREIGN KEY(sku_key) REFERENCES products (sku_key) ON DELETE CASCADE
)




CREATE TABLE orders (
	order_id VARCHAR(64) NOT NULL, 
	order_ts DATETIME NOT NULL, 
	account_id VARCHAR(64), 
	offer_id VARCHAR(64), 
	sku_key VARCHAR(64), 
	ordered_size VARCHAR(32), 
	final_size VARCHAR(32), 
	phone VARCHAR(32), 
	status VARCHAR(32), 
	price_kzt NUMERIC(14, 2), 
	delivery_cost_kzt NUMERIC(14, 2) DEFAULT '0', 
	kaspi_fee_pct FLOAT DEFAULT '0.12', 
	PRIMARY KEY (order_id), 
	CONSTRAINT uq_orders_order_id UNIQUE (order_id), 
	FOREIGN KEY(offer_id) REFERENCES offers (offer_id) ON DELETE SET NULL, 
	FOREIGN KEY(sku_key) REFERENCES products (sku_key) ON DELETE SET NULL
)




CREATE TABLE stock_snapshots (
	id INTEGER NOT NULL, 
	offer_id VARCHAR(64) NOT NULL, 
	account_id VARCHAR(64) NOT NULL, 
	qty INTEGER DEFAULT '0' NOT NULL, 
	ts_utc DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(offer_id) REFERENCES offers (offer_id) ON DELETE CASCADE
)


