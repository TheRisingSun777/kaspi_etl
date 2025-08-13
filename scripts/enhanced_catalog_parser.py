#!/usr/bin/env python3
"""
Enhanced Catalog Parser with Data Validation and Kaspi API Mapping
Handles M02_SKU_CATALOG with Russian columns and comma-separated weights
"""
import logging
import pathlib
import re
import sqlite3

import pandas as pd

# Setup paths
RAW_DIR = pathlib.Path(__file__).resolve().parents[1] / "data_raw"
DB_PATH = pathlib.Path(__file__).resolve().parents[1] / "db" / "erp.db"
CATALOG_PATH = RAW_DIR / "M02_SKU_CATALOG Sample for gpt.csv"

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class CatalogDataValidator:
    """Validates and cleans catalog data for Kaspi API integration"""
    
    @staticmethod
    def clean_weight(weight_str: str) -> float | None:
        """Convert weight from '0,95' format to 0.95 float"""
        if not weight_str or pd.isna(weight_str):
            return None
        
        try:
            # Handle comma decimal separator
            cleaned = str(weight_str).replace(',', '.')
            # Remove any non-numeric chars except decimal point
            cleaned = re.sub(r'[^\d.]', '', cleaned)
            return float(cleaned) if cleaned else None
        except (ValueError, TypeError):
            logger.warning(f"Invalid weight format: {weight_str}")
            return None
    
    @staticmethod
    def clean_price(price_str: str) -> int | None:
        """Clean price string and convert to integer KZT"""
        if not price_str or pd.isna(price_str):
            return None
        
        try:
            # Remove spaces and non-numeric chars except decimal
            cleaned = re.sub(r'[^\d.]', '', str(price_str))
            return int(float(cleaned)) if cleaned else None
        except (ValueError, TypeError):
            logger.warning(f"Invalid price format: {price_str}")
            return None
    
    @staticmethod
    def clean_stock(stock_str: str) -> int:
        """Clean stock quantity and convert to integer"""
        if not stock_str or pd.isna(stock_str):
            return 0
        
        try:
            cleaned = re.sub(r'[^\d]', '', str(stock_str))
            return int(cleaned) if cleaned else 0
        except (ValueError, TypeError):
            logger.warning(f"Invalid stock format: {stock_str}")
            return 0
    
    @staticmethod
    def validate_sku_id(sku_id: str) -> bool:
        """Validate SKU ID format"""
        if not sku_id or pd.isna(sku_id):
            return False
        return len(str(sku_id).strip()) > 0
    
    @staticmethod
    def clean_text_field(text: str) -> str:
        """Clean and standardize text fields"""
        if not text or pd.isna(text):
            return ""
        return str(text).strip()


class KaspiApiMapper:
    """Maps catalog data to Kaspi API format"""
    
    # CSV to API field mapping
    FIELD_MAPPING = {
        'SKU_ID': 'merchantProductId',
        'Kaspi_name_core': 'title',
        'Kaspi_art_1': 'masterCode',
        'SKU_ID_KSP': 'code',
        'Initial_KSP_Price': 'price',
        'Stock_entered': 'availableAmount',
        'Weight_kg': 'weight',
        'Brend': 'brand',
        'Model': 'model',
        'Color': 'color',
        'Our_Size': 'size',
        'Gender': 'gender',
        'Season': 'season',
        'Product_Type': 'category',
        'Sub_Category': 'subcategory',
    }
    
    @classmethod
    def map_to_api_format(cls, row: pd.Series) -> dict:
        """Convert catalog row to Kaspi API format"""
        validator = CatalogDataValidator()
        
        api_data = {
            'merchantProductId': validator.clean_text_field(row.get('SKU_ID')),
            'title': validator.clean_text_field(row.get('Kaspi_name_core')) or row.get('SKU_ID', ''),
            'masterCode': validator.clean_text_field(row.get('Kaspi_art_1')),
            'code': validator.clean_text_field(row.get('SKU_ID_KSP')),
            'price': validator.clean_price(row.get('Initial_KSP_Price')),
            'availableAmount': validator.clean_stock(row.get('Stock_entered')),
            'weight': validator.clean_weight(row.get('Weight_kg')),
            'brand': validator.clean_text_field(row.get('Brend')),
            'model': validator.clean_text_field(row.get('Model')),
            'color': validator.clean_text_field(row.get('Color')),
            'size': validator.clean_text_field(row.get('Our_Size')),
            'gender': validator.clean_text_field(row.get('Gender')),
            'season': validator.clean_text_field(row.get('Season')),
            'category': validator.clean_text_field(row.get('Product_Type')),
            'subcategory': validator.clean_text_field(row.get('Sub_Category')),
        }
        
        # Remove None values for API compatibility
        return {k: v for k, v in api_data.items() if v is not None and v != ''}


class EnhancedCatalogParser:
    """Enhanced catalog parser with validation and API mapping"""
    
    def __init__(self):
        self.validator = CatalogDataValidator()
        self.mapper = KaspiApiMapper()
        self.errors = []
        self.warnings = []
    
    def load_catalog(self) -> pd.DataFrame:
        """Load and validate catalog CSV"""
        if not CATALOG_PATH.exists():
            raise FileNotFoundError(f"Catalog file not found: {CATALOG_PATH}")
        
        logger.info(f"Loading catalog from {CATALOG_PATH}")
        
        try:
            # Load with proper handling of semicolon separator
            df = pd.read_csv(
                CATALOG_PATH, 
                sep=';', 
                engine='python', 
                dtype=str, 
                on_bad_lines='skip'
            )
            
            # Clean column names
            df.columns = [col.strip() for col in df.columns]
            
            logger.info(f"Loaded {len(df)} rows from catalog")
            return df
            
        except Exception as e:
            logger.error(f"Error loading catalog: {e}")
            raise
    
    def validate_catalog(self, df: pd.DataFrame) -> tuple[pd.DataFrame, list[str], list[str]]:
        """Validate catalog data and return cleaned DataFrame with errors/warnings"""
        cleaned_df = df.copy()
        errors = []
        warnings = []
        
        # Required columns check
        required_cols = ['SKU_ID', 'Store_name']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            errors.append(f"Missing required columns: {missing_cols}")
            return cleaned_df, errors, warnings
        
        # Validate each row
        valid_rows = []
        for idx, row in df.iterrows():
            row_errors = []
            row_warnings = []
            
            # SKU ID validation
            if not self.validator.validate_sku_id(row.get('SKU_ID')):
                row_errors.append(f"Row {idx}: Invalid SKU_ID")
                continue
            
            # Weight validation
            weight = self.validator.clean_weight(row.get('Weight_kg'))
            if weight is None and row.get('Weight_kg'):
                row_warnings.append(f"Row {idx}: Invalid weight format: {row.get('Weight_kg')}")
            
            # Price validation
            price = self.validator.clean_price(row.get('Initial_KSP_Price'))
            if price is None and row.get('Initial_KSP_Price'):
                row_warnings.append(f"Row {idx}: Invalid price format: {row.get('Initial_KSP_Price')}")
            
            # Store validation
            store = self.validator.clean_text_field(row.get('Store_name'))
            if not store:
                row_warnings.append(f"Row {idx}: Missing store name")
            
            if row_errors:
                errors.extend(row_errors)
            else:
                valid_rows.append(idx)
                if row_warnings:
                    warnings.extend(row_warnings)
        
        # Filter to valid rows only
        cleaned_df = df.loc[valid_rows].copy()
        
        logger.info(f"Validation complete: {len(valid_rows)} valid rows, {len(errors)} errors, {len(warnings)} warnings")
        
        return cleaned_df, errors, warnings
    
    def prepare_for_api(self, df: pd.DataFrame) -> list[dict]:
        """Prepare catalog data for Kaspi API calls"""
        api_products = []
        
        for _, row in df.iterrows():
            try:
                api_data = self.mapper.map_to_api_format(row)
                if api_data.get('merchantProductId'):  # Must have product ID
                    api_products.append(api_data)
            except Exception as e:
                logger.warning(f"Error mapping row to API format: {e}")
        
        logger.info(f"Prepared {len(api_products)} products for API")
        return api_products
    
    def save_to_database(self, df: pd.DataFrame) -> None:
        """Save validated catalog to database"""
        # Clean data for database
        db_df = df.copy()
        
        # Apply data cleaning
        for col in ['Weight_kg']:
            if col in db_df.columns:
                db_df[f'{col}_cleaned'] = db_df[col].apply(self.validator.clean_weight)
        
        for col in ['Initial_KSP_Price']:
            if col in db_df.columns:
                db_df[f'{col}_cleaned'] = db_df[col].apply(self.validator.clean_price)
        
        for col in ['Stock_entered']:
            if col in db_df.columns:
                db_df[f'{col}_cleaned'] = db_df[col].apply(self.validator.clean_stock)
        
        # Save to database
        con = sqlite3.connect(DB_PATH)
        try:
            db_df.to_sql("catalog_enhanced", con, if_exists='replace', index=False)
            logger.info(f"Saved {len(db_df)} rows to database table 'catalog_enhanced'")
        finally:
            con.close()
    
    def generate_report(self, df: pd.DataFrame, api_products: list[dict]) -> dict:
        """Generate processing report"""
        report = {
            'total_products': len(df),
            'api_ready_products': len(api_products),
            'products_by_store': df['Store_name'].value_counts().to_dict(),
            'products_with_kaspi_codes': df['Kaspi_art_1'].notna().sum(),
            'products_with_prices': df['Initial_KSP_Price'].notna().sum(),
            'products_with_stock': df['Stock_entered'].notna().sum(),
            'errors': self.errors,
            'warnings': self.warnings,
        }
        return report


def main():
    """Main processing function"""
    logger.info("🚀 Starting enhanced catalog processing")
    
    parser = EnhancedCatalogParser()
    
    try:
        # Load catalog
        df = parser.load_catalog()
        
        # Validate data
        cleaned_df, errors, warnings = parser.validate_catalog(df)
        parser.errors = errors
        parser.warnings = warnings
        
        if errors:
            logger.error(f"❌ Validation errors found: {len(errors)}")
            for error in errors[:5]:  # Show first 5 errors
                logger.error(f"  {error}")
            return
        
        if warnings:
            logger.warning(f"⚠️ Validation warnings: {len(warnings)}")
            for warning in warnings[:5]:  # Show first 5 warnings
                logger.warning(f"  {warning}")
        
        # Prepare API data
        api_products = parser.prepare_for_api(cleaned_df)
        
        # Save to database
        parser.save_to_database(cleaned_df)
        
        # Generate report
        report = parser.generate_report(cleaned_df, api_products)
        
        # Display summary
        print("\n📊 PROCESSING SUMMARY")
        print("=" * 50)
        print(f"✅ Total products processed: {report['total_products']}")
        print(f"🚀 API-ready products: {report['api_ready_products']}")
        print(f"🔗 Products with Kaspi codes: {report['products_with_kaspi_codes']}")
        print(f"💰 Products with prices: {report['products_with_prices']}")
        print(f"📦 Products with stock: {report['products_with_stock']}")
        
        print("\n🏪 Products by store:")
        for store, count in report['products_by_store'].items():
            print(f"   {store}: {count}")
        
        if warnings:
            print(f"\n⚠️ Warnings: {len(warnings)}")
        
        logger.info("🎉 Enhanced catalog processing completed successfully")
        
    except Exception as e:
        logger.error(f"❌ Processing failed: {e}")
        raise


if __name__ == "__main__":
    main()
