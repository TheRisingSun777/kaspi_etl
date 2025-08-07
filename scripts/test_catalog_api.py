#!/usr/bin/env python3
# --- TEST SCRIPT FOR KASPI CATALOG API (v2025‑08‑05) ------------------------
import pandas as pd
import pathlib
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup paths
RAW_DIR = pathlib.Path(__file__).resolve().parents[1] / "data_raw"
CATALOG_PATH = RAW_DIR / "M02_SKU_CATALOG Sample for gpt.csv"

def test_catalog_loading():
    """Test loading the catalog CSV file"""
    print("🧪 Testing catalog CSV loading...")
    
    if not CATALOG_PATH.exists():
        print(f"❌ Catalog file not found: {CATALOG_PATH}")
        return False
    
    try:
        df = pd.read_csv(CATALOG_PATH, sep=';', engine='python', dtype=str, on_bad_lines='skip')
        print(f"✅ Successfully loaded {len(df)} rows from catalog CSV")
        
        # Check required columns
        required_cols = ['SKU_ID', 'sku_name_raw', 'Kaspi_art_1', 'Brend', 'Model', 'Color']
        missing_cols = [col for col in required_cols if col not in df.columns]
        
        if missing_cols:
            print(f"⚠️  Missing columns: {missing_cols}")
            print(f"Available columns: {list(df.columns)}")
        else:
            print("✅ All required columns found")
        
        # Show sample data
        print("\n📋 Sample catalog data:")
        sample = df[['SKU_ID', 'sku_name_raw', 'Kaspi_art_1', 'Brend', 'Model']].head(3)
        print(sample.to_string(index=False))
        
        return True
        
    except Exception as e:
        print(f"❌ Error loading catalog CSV: {e}")
        return False

def test_environment():
    """Test environment configuration"""
    print("\n🧪 Testing environment configuration...")
    
    token = os.getenv("KASPI_TOKEN")
    if token and token != "xxxxxxxxxxxxxxxx":
        print("✅ KASPI_TOKEN found in environment")
        return True
    else:
        print("⚠️  KASPI_TOKEN not found or using placeholder value")
        print("   Please set KASPI_TOKEN in your .env file")
        return False

def test_database_connection():
    """Test database connection"""
    print("\n🧪 Testing database connection...")
    
    try:
        import sqlite3
        db_path = pathlib.Path(__file__).resolve().parents[1] / "db" / "erp.db"
        
        if db_path.exists():
            con = sqlite3.connect(db_path)
            cur = con.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cur.fetchall()
            con.close()
            
            print(f"✅ Database connected successfully")
            print(f"   Tables found: {[t[0] for t in tables]}")
            return True
        else:
            print("⚠️  Database file not found, will be created on first run")
            return True
            
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 Starting Kaspi Catalog API tests...\n")
    
    tests = [
        test_catalog_loading,
        test_environment,
        test_database_connection
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The script should work correctly.")
    else:
        print("⚠️  Some tests failed. Please check the issues above.")

if __name__ == "__main__":
    main()
