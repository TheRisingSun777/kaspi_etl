#!/usr/bin/env python3
# --- SIMPLE ETL FOR KASPI CATALOG (v2025‑08‑05) --------------------------------
import pandas as pd
import sqlite3
import pathlib
import logging

# Setup paths
RAW_DIR = pathlib.Path(__file__).resolve().parents[1] / "data_raw"
DB_PATH = pathlib.Path(__file__).resolve().parents[1] / "db" / "erp.db"
CATALOG_PATH = RAW_DIR / "M02_SKU_CATALOG Sample for gpt.csv"

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_products_table():
    """Create the products table in SQLite database"""
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    
    cur.execute("""
    CREATE TABLE IF NOT EXISTS products (
        sku_id              TEXT PRIMARY KEY,
        kaspi_name_core     TEXT,
        my_size             TEXT,
        size_kaspi          TEXT,
        kaspi_art_1         TEXT,
        sku_id_ksp          TEXT,
        kaspi_name_source   TEXT,
        initial_ksp_price   TEXT,
        stock_entered       INTEGER,
        sku_key             TEXT,
        secondary           TEXT,
        product_type        TEXT,
        sub_category        TEXT,
        brand               TEXT,
        model               TEXT,
        color               TEXT,
        our_size            TEXT,
        gender              TEXT,
        season              TEXT,
        base_cost_cny       REAL,
        weight_kg           REAL,
        store_name          TEXT,
        kaspi_art_2         TEXT,
        last_updated        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    con.commit()
    con.close()
    logger.info("✅ Products table created/verified")

def load_catalog_csv() -> pd.DataFrame:
    """Load and parse the M02_SKU_CATALOG CSV file"""
    if not CATALOG_PATH.exists():
        logger.error(f"❌ Catalog file not found: {CATALOG_PATH}")
        return pd.DataFrame()
    
    try:
        df = pd.read_csv(CATALOG_PATH, sep=';', engine='python', dtype=str, on_bad_lines='skip')
        
        # Clean and standardize column names
        df.columns = [col.strip() for col in df.columns]
        
        # Select and rename relevant columns for new catalog format
        catalog_df = df[[
            'SKU_ID', 'Kaspi_name_core', 'MY_SIZE', 'Size_kaspi', 'Kaspi_art_1',
            'SKU_ID_KSP', 'Kaspi_name_source', 'Initial_KSP_Price', 'Stock_entered',
            'SKU_key', 'Secondary', 'Product_Type', 'Sub_Category', 'Brend',
            'Model', 'Color', 'Our_Size', 'Gender', 'Season', 'BaseCost_CNY', 'Weight_kg',
            'Store_name', 'Kaspi_art_2'
        ]].copy()
        
        # Clean data
        catalog_df = catalog_df.fillna('')
        catalog_df['Weight_kg'] = pd.to_numeric(catalog_df['Weight_kg'].str.replace(',', '.'), errors='coerce')
        
        logger.info(f"✅ Loaded {len(catalog_df)} products from catalog CSV")
        return catalog_df
    
    except Exception as e:
        logger.error(f"❌ Error loading catalog CSV: {e}")
        return pd.DataFrame()

def save_to_database(catalog_df: pd.DataFrame):
    """Save catalog data to database"""
    con = sqlite3.connect(DB_PATH)
    
    # Rename columns to match database schema
    catalog_df = catalog_df.rename(columns={
        'SKU_ID': 'sku_id',
        'Kaspi_name_core': 'kaspi_name_core',
        'MY_SIZE': 'my_size',
        'Size_kaspi': 'size_kaspi',
        'Kaspi_art_1': 'kaspi_art_1',
        'SKU_ID_KSP': 'sku_id_ksp',
        'Kaspi_name_source': 'kaspi_name_source',
        'Initial_KSP_Price': 'initial_ksp_price',
        'Stock_entered': 'stock_entered',
        'SKU_key': 'sku_key',
        'Secondary': 'secondary',
        'Product_Type': 'product_type',
        'Sub_Category': 'sub_category',
        'Brend': 'brand',
        'Model': 'model',
        'Color': 'color',
        'Our_Size': 'our_size',
        'Gender': 'gender',
        'Season': 'season',
        'BaseCost_CNY': 'base_cost_cny',
        'Weight_kg': 'weight_kg',
        'Store_name': 'store_name',
        'Kaspi_art_2': 'kaspi_art_2'
    })
    
    # Convert stock_entered to numeric
    catalog_df['stock_entered'] = pd.to_numeric(catalog_df['stock_entered'], errors='coerce').fillna(0).astype(int)
    catalog_df['base_cost_cny'] = pd.to_numeric(catalog_df['base_cost_cny'], errors='coerce')
    
    # Save to database
    catalog_df.to_sql("products", con, if_exists='replace', index=False)
    con.close()
    
    logger.info(f"✅ Saved {len(catalog_df)} products to database")

def show_summary(catalog_df: pd.DataFrame):
    """Show a summary of the catalog data"""
    print("\n📊 CATALOG SUMMARY:")
    print(f"   Total products: {len(catalog_df)}")
    
    # Count products with Kaspi codes
    with_codes = catalog_df['Kaspi_art_1'].notna() & (catalog_df['Kaspi_art_1'] != '')
    print(f"   Products with Kaspi codes: {with_codes.sum()}")
    
    # Count by brand
    brand_counts = catalog_df['Brend'].value_counts()
    print(f"\n   Products by brand:")
    for brand, count in brand_counts.head(5).items():
        print(f"     {brand}: {count}")
    
    # Count by product type
    type_counts = catalog_df['Product_Type'].value_counts()
    print(f"\n   Products by type:")
    for ptype, count in type_counts.head(5).items():
        print(f"     {ptype}: {count}")
    
    # Show some sample products
    print(f"\n   Sample products:")
    sample = catalog_df[['SKU_ID', 'Kaspi_name_core', 'Brend', 'Model']].head(3)
    for _, row in sample.iterrows():
        name = row['Kaspi_name_core'] if row['Kaspi_name_core'] else row['SKU_ID']
        print(f"     {name} ({row['Brend']} {row['Model']})")

def main():
    """Main ETL process"""
    logger.info("🚀 Starting Simple Kaspi Catalog ETL process")
    
    # 1. Create database table
    create_products_table()
    
    # 2. Load catalog CSV
    catalog_df = load_catalog_csv()
    if catalog_df.empty:
        logger.error("❌ No catalog data loaded")
        return
    
    # 3. Save to database
    save_to_database(catalog_df)
    
    # 4. Show summary
    show_summary(catalog_df)
    
    logger.info("🎉 Simple ETL completed successfully!")

if __name__ == "__main__":
    main()
