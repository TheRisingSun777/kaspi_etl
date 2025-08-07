#!/usr/bin/env python3
# --- ETL FOR KASPI CATALOG API (v2025‑08‑05) --------------------------------
import pandas as pd
import sqlite3
import pathlib
import httpx
import os
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential
import json
from typing import Dict, List, Optional
import logging

# Load environment variables
load_dotenv()

# Setup paths
RAW_DIR = pathlib.Path(__file__).resolve().parents[1] / "data_raw"
DB_PATH = pathlib.Path(__file__).resolve().parents[1] / "db" / "erp.db"
CATALOG_PATH = RAW_DIR / "M02_SKU_CATALOG Sample for gpt.csv"

# API Configuration
BASE_URL = "https://kaspi.kz/shop/api/v2"
KASPI_TOKEN = os.getenv("KASPI_TOKEN")

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class KaspiAPI:
    def __init__(self, token: str, base_url: str = BASE_URL):
        self.token = token
        self.base_url = base_url
        self.headers = {
            "X-Auth-Token": token,
            "Content-Type": "application/json"
        }
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def get_products(self) -> List[Dict]:
        """GET /shop/api/v2/products to verify token and get existing products"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/products",
                headers=self.headers,
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()
            logger.info(f"✅ Retrieved {len(data.get('data', []))} products from Kaspi API")
            return data.get('data', [])
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def create_product(self, product_data: Dict) -> Dict:
        """POST /shop/api/v2/products/create for new/changed SKUs"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/products/create",
                headers=self.headers,
                json=product_data,
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()
            logger.info(f"✅ Created product: {product_data.get('name', 'Unknown')}")
            return data

def load_catalog_csv() -> pd.DataFrame:
    """Load and parse the M02_SKU_CATALOG CSV file"""
    if not CATALOG_PATH.exists():
        logger.error(f"❌ Catalog file not found: {CATALOG_PATH}")
        return pd.DataFrame()
    
    try:
        df = pd.read_csv(CATALOG_PATH, sep=';', engine='python', dtype=str, on_bad_lines='skip')
        
        # Clean and standardize column names
        df.columns = [col.strip() for col in df.columns]
        
        # Select and rename relevant columns
        catalog_df = df[[
            'SKU_ID', 'sku_name_raw', 'Kaspi_name_edit', 'my_size', 'Size_kaspi',
            'Stock_entered', 'Kaspi_art_1', 'SKU_ID_KSP', 'Kaspi_name_source',
            'SKU_key', 'Kaspi_art_2', 'Kaspi_art_3', 'Product_Type', 'Brend',
            'Model', 'Color', 'Our_Size', 'Gender', 'Season', 'BaseCost_CNY', 'Weight_kg'
        ]].copy()
        
        # Clean data
        catalog_df = catalog_df.fillna('')
        catalog_df['Weight_kg'] = pd.to_numeric(catalog_df['Weight_kg'].str.replace(',', '.'), errors='coerce')
        
        logger.info(f"✅ Loaded {len(catalog_df)} products from catalog CSV")
        return catalog_df
    
    except Exception as e:
        logger.error(f"❌ Error loading catalog CSV: {e}")
        return pd.DataFrame()

def create_products_table():
    """Create the products table in SQLite database"""
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    
    cur.execute("""
    CREATE TABLE IF NOT EXISTS products (
        sku_id              TEXT PRIMARY KEY,
        sku_name_raw        TEXT,
        kaspi_name_edit     TEXT,
        my_size             TEXT,
        size_kaspi          TEXT,
        stock_entered       INTEGER,
        kaspi_art_1         TEXT,
        sku_id_ksp          TEXT,
        kaspi_name_source   TEXT,
        sku_key             TEXT,
        kaspi_art_2         TEXT,
        kaspi_art_3         TEXT,
        product_type        TEXT,
        brand               TEXT,
        model               TEXT,
        color               TEXT,
        our_size            TEXT,
        gender              TEXT,
        season              TEXT,
        base_cost_cny       REAL,
        weight_kg           REAL,
        kaspi_product_id    TEXT,
        last_updated        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    con.commit()
    con.close()
    logger.info("✅ Products table created/verified")

def save_to_database(catalog_df: pd.DataFrame, kaspi_products: List[Dict]):
    """Save catalog data and Kaspi API data to database"""
    con = sqlite3.connect(DB_PATH)
    
    # Create a mapping of Kaspi product codes to product IDs
    kaspi_mapping = {}
    for product in kaspi_products:
        code = product.get('code')
        if code:
            kaspi_mapping[code] = product.get('id')
    
    # Add Kaspi product ID to catalog data
    catalog_df['kaspi_product_id'] = catalog_df['Kaspi_art_1'].map(kaspi_mapping)
    
    # Rename columns to match database schema
    catalog_df = catalog_df.rename(columns={
        'SKU_ID': 'sku_id',
        'sku_name_raw': 'sku_name_raw',
        'Kaspi_name_edit': 'kaspi_name_edit',
        'my_size': 'my_size',
        'Size_kaspi': 'size_kaspi',
        'Stock_entered': 'stock_entered',
        'Kaspi_art_1': 'kaspi_art_1',
        'SKU_ID_KSP': 'sku_id_ksp',
        'Kaspi_name_source': 'kaspi_name_source',
        'SKU_key': 'sku_key',
        'Kaspi_art_2': 'kaspi_art_2',
        'Kaspi_art_3': 'kaspi_art_3',
        'Product_Type': 'product_type',
        'Brend': 'brand',
        'Model': 'model',
        'Color': 'color',
        'Our_Size': 'our_size',
        'Gender': 'gender',
        'Season': 'season',
        'BaseCost_CNY': 'base_cost_cny',
        'Weight_kg': 'weight_kg'
    })
    
    # Convert stock_entered to numeric
    catalog_df['stock_entered'] = pd.to_numeric(catalog_df['stock_entered'], errors='coerce').fillna(0).astype(int)
    catalog_df['base_cost_cny'] = pd.to_numeric(catalog_df['base_cost_cny'], errors='coerce')
    
    # Save to database
    catalog_df.to_sql("products", con, if_exists='replace', index=False)
    con.close()
    
    logger.info(f"✅ Saved {len(catalog_df)} products to database")

def prepare_product_for_api(row: pd.Series) -> Dict:
    """Prepare a catalog row for Kaspi API product creation"""
    # Basic product structure for Kaspi API
    product_data = {
        "name": row['kaspi_name_edit'] if row['kaspi_name_edit'] else row['sku_name_raw'],
        "code": row['kaspi_art_1'],
        "description": f"{row['brand']} {row['model']} {row['color']} {row['our_size']}",
        "category": row['product_type'],
        "brand": row['brand'],
        "model": row['model'],
        "color": row['color'],
        "size": row['our_size'],
        "gender": row['gender'],
        "season": row['season'],
        "weight": float(row['weight_kg']) if pd.notna(row['weight_kg']) else 0.0
    }
    
    # Remove None/empty values
    return {k: v for k, v in product_data.items() if v and v != ''}

async def main():
    """Main ETL process"""
    if not KASPI_TOKEN:
        logger.error("❌ KASPI_TOKEN not found in environment variables")
        return
    
    logger.info("🚀 Starting Kaspi Catalog ETL process")
    
    # 1. Create database table
    create_products_table()
    
    # 2. Load catalog CSV
    catalog_df = load_catalog_csv()
    if catalog_df.empty:
        logger.error("❌ No catalog data loaded")
        return
    
    # 3. Initialize Kaspi API client
    api = KaspiAPI(KASPI_TOKEN)
    
    try:
        # 4. GET existing products from Kaspi API
        logger.info("📡 Fetching existing products from Kaspi API...")
        kaspi_products = await api.get_products()
        
        # 5. Compare and identify new/changed products
        existing_codes = {p.get('code') for p in kaspi_products if p.get('code')}
        new_products = []
        
        for _, row in catalog_df.iterrows():
            kaspi_code = row['kaspi_art_1']
            if kaspi_code and kaspi_code not in existing_codes:
                product_data = prepare_product_for_api(row)
                if product_data:
                    new_products.append((row, product_data))
        
        logger.info(f"📊 Found {len(new_products)} new products to create")
        
        # 6. POST new products to Kaspi API
        created_count = 0
        for row, product_data in new_products:
            try:
                await api.create_product(product_data)
                created_count += 1
                logger.info(f"✅ Created product: {product_data['name']} ({product_data['code']})")
            except Exception as e:
                logger.error(f"❌ Failed to create product {product_data['code']}: {e}")
        
        # 7. Save all data to database
        logger.info("💾 Saving data to database...")
        save_to_database(catalog_df, kaspi_products)
        
        logger.info(f"🎉 ETL completed successfully!")
        logger.info(f"   - Catalog products: {len(catalog_df)}")
        logger.info(f"   - Existing Kaspi products: {len(kaspi_products)}")
        logger.info(f"   - New products created: {created_count}")
        
    except Exception as e:
        logger.error(f"❌ ETL process failed: {e}")
        raise

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
