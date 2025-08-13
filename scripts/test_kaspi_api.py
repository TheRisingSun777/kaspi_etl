#!/usr/bin/env python3
# --- TEST KASPI API CONNECTION (v2025‑08‑05) --------------------------------
import asyncio
import logging
import os

import httpx
from dotenv import load_dotenv

# Load environment variables (prefer .env.local if present, then .env)
load_dotenv(".env.local", override=False)
load_dotenv(override=False)

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# API Configuration
# Allow multiple variable names for compatibility:
# - Token: KASPI_TOKEN | X_AUTH_TOKEN | KASPI_API_TOKEN
# - Base: KASPI_BASE | KASPI_API_BASE_URL | default
BASE_URL = (
    os.getenv("KASPI_BASE")
    or os.getenv("KASPI_API_BASE_URL")
    or "https://kaspi.kz/shop/api/v2"
)
KASPI_TOKEN = (
    os.getenv("KASPI_TOKEN")
    or os.getenv("X_AUTH_TOKEN")
    or os.getenv("KASPI_API_TOKEN")
)


async def test_api_connection():
    """Test basic API connection"""
    if not KASPI_TOKEN:
        logger.error(
            "❌ Missing API token. Set one of: KASPI_TOKEN, X_AUTH_TOKEN, or KASPI_API_TOKEN"
        )
        return False

    headers = {"X-Auth-Token": KASPI_TOKEN, "Content-Type": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            logger.info("🔗 Testing connection to Kaspi API...")

            # Try to get products (this should work if token is valid)
            response = await client.get(f"{BASE_URL}/products", headers=headers)

            if response.status_code == 200:
                data = response.json()
                products_count = len(data.get("data", []))
                logger.info("✅ API connection successful!")
                logger.info(f"   Found {products_count} existing products in your store")
                return True
            else:
                logger.error(f"❌ API request failed with status {response.status_code}")
                logger.error(f"   Response: {response.text}")
                return False

    except httpx.TimeoutException:
        logger.error("❌ API request timed out (60 seconds)")
        logger.info("   This might be due to slow internet or API being busy")
        return False
    except Exception as e:
        logger.error(f"❌ API connection failed: {e}")
        return False


async def test_simple_product_creation():
    """Test creating a simple test product"""
    if not KASPI_TOKEN:
        return False

    headers = {"X-Auth-Token": KASPI_TOKEN, "Content-Type": "application/json"}

    # Simple test product
    test_product = {
        "name": "Test Product - Please Delete",
        "code": "TEST123456",
        "description": "This is a test product for API verification",
        "category": "TEST",
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            logger.info("🧪 Testing product creation...")

            response = await client.post(
                f"{BASE_URL}/products/create", headers=headers, json=test_product
            )

            if response.status_code == 200:
                data = response.json()
                logger.info("✅ Test product created successfully!")
                logger.info(f"   Product ID: {data.get('id', 'Unknown')}")
                return True
            else:
                logger.error(f"❌ Product creation failed with status {response.status_code}")
                logger.error(f"   Response: {response.text}")
                return False

    except Exception as e:
        logger.error(f"❌ Product creation test failed: {e}")
        return False


async def main():
    """Run API tests"""
    logger.info("🚀 Starting Kaspi API tests...")

    # Test 1: Basic connection
    connection_ok = await test_api_connection()

    if connection_ok:
        # Test 2: Product creation (optional)
        logger.info("\n" + "=" * 50)
        create_ok = await test_simple_product_creation()

        if create_ok:
            logger.info("\n🎉 All API tests passed!")
            logger.info("   Your Kaspi API integration is working correctly.")
        else:
            logger.info("\n⚠️  API connection works, but product creation failed.")
            logger.info("   This might be due to API permissions or rate limits.")
    else:
        logger.error("\n❌ API connection failed.")
        logger.error("   Please check your token and internet connection.")


if __name__ == "__main__":
    asyncio.run(main())
