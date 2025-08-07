#!/usr/bin/env python3
# --- EXPLAIN DATA FILES (v2025‑08‑05) --------------------------------
import pandas as pd
import pathlib
import sqlite3

# Setup paths
RAW_DIR = pathlib.Path(__file__).resolve().parents[1] / "data_raw"
DB_PATH = pathlib.Path(__file__).resolve().parents[1] / "db" / "erp.db"

def explain_catalog_file():
    """Explain the main catalog file"""
    print("📊 M02_SKU_CATALOG Sample for gpt.csv")
    print("=" * 50)
    
    try:
        df = pd.read_csv(RAW_DIR / "M02_SKU_CATALOG Sample for gpt.csv", sep=';', engine='python', dtype=str, on_bad_lines='skip')
        df.columns = [col.strip() for col in df.columns]
        
        print(f"✅ Total products: {len(df)}")
        
        # Count by store
        store_counts = df['Store_name'].value_counts()
        print(f"\n🏪 Products by store:")
        for store, count in store_counts.items():
            print(f"   {store}: {count} products")
        
        # Count products with Kaspi codes
        with_codes = df['Kaspi_art_1'].notna() & (df['Kaspi_art_1'] != '')
        print(f"\n🔗 Products with Kaspi codes: {with_codes.sum()}")
        print(f"   Products without Kaspi codes: {(~with_codes).sum()}")
        
        # Show sample
        print(f"\n📋 Sample products:")
        sample = df[['SKU_ID', 'Kaspi_name_core', 'Store_name', 'Kaspi_art_1']].head(3)
        for _, row in sample.iterrows():
            name = row['Kaspi_name_core'] if row['Kaspi_name_core'] else row['SKU_ID']
            kaspi_code = row['Kaspi_art_1'] if row['Kaspi_art_1'] else "No code"
            print(f"   {name} → Store: {row['Store_name']} → Kaspi: {kaspi_code}")
            
    except Exception as e:
        print(f"❌ Error reading catalog: {e}")

def explain_stock_file():
    """Explain the stock file"""
    print(f"\n📦 stock_on_hand.csv")
    print("=" * 50)
    
    try:
        df = pd.read_csv(RAW_DIR / "stock_on_hand.csv")
        print(f"✅ Total stock items: {len(df)}")
        
        total_stock = df['qty_on_hand'].sum()
        print(f"   Total quantity in stock: {total_stock}")
        
        print(f"\n📋 Sample stock items:")
        for _, row in df.head(3).iterrows():
            print(f"   {row['sku_key']}: {row['qty_on_hand']} units")
            
    except Exception as e:
        print(f"❌ Error reading stock: {e}")

def explain_orders():
    """Explain the orders files"""
    print(f"\n🛒 Orders Files")
    print("=" * 50)
    
    # Check active orders
    active_file = RAW_DIR / "ActiveOrders 31.7.25.xlsx"
    if active_file.exists():
        try:
            df = pd.read_excel(active_file)
            print(f"✅ ActiveOrders 31.7.25.xlsx: {len(df)} orders")
            print(f"   Columns: {list(df.columns)}")
        except Exception as e:
            print(f"❌ Error reading active orders: {e}")
    
    # Check archive orders
    archive_file = RAW_DIR / "ArchiveOrders since 1.7.25.xlsx"
    if archive_file.exists():
        try:
            df = pd.read_excel(archive_file)
            print(f"✅ ArchiveOrders since 1.7.25.xlsx: {len(df)} orders")
            print(f"   Columns: {list(df.columns)}")
        except Exception as e:
            print(f"❌ Error reading archive orders: {e}")

def explain_purchases():
    """Explain the purchase file"""
    print(f"\n📋 Purchase inquiry made by me.xlsx")
    print("=" * 50)
    
    purchase_file = RAW_DIR / "Purchase inquiry made by me.xlsx"
    if purchase_file.exists():
        try:
            df = pd.read_excel(purchase_file)
            print(f"✅ Purchase orders: {len(df)} items")
            print(f"   Columns: {list(df.columns)}")
        except Exception as e:
            print(f"❌ Error reading purchases: {e}")

def show_database_status():
    """Show what's in the database"""
    print(f"\n💾 Database Status (db/erp.db)")
    print("=" * 50)
    
    try:
        con = sqlite3.connect(DB_PATH)
        cur = con.cursor()
        
        # Show tables
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cur.fetchall()
        
        print(f"✅ Tables in database:")
        for table in tables:
            table_name = table[0]
            cur.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cur.fetchone()[0]
            print(f"   {table_name}: {count} records")
        
        con.close()
        
    except Exception as e:
        print(f"❌ Error reading database: {e}")

def main():
    """Main explanation function"""
    print("🚀 KASPI ETL DATA FILES EXPLANATION")
    print("=" * 60)
    
    explain_catalog_file()
    explain_stock_file()
    explain_orders()
    explain_purchases()
    show_database_status()
    
    print(f"\n" + "=" * 60)
    print("💡 SUMMARY:")
    print("   • Catalog file = Your product master list")
    print("   • Stock file = Current inventory levels")
    print("   • Orders = Customer requests")
    print("   • Purchases = Supplier orders")
    print("   • Database = Everything stored together")
    print("\n🎯 Right now: Everything works manually (safe)")
    print("🔄 Later: API will automate everything")

if __name__ == "__main__":
    main()
