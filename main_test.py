#!/usr/bin/env python3
"""
Test version of main scraper - limited to 5 products
"""

import asyncio
import logging
import sys
from config import PRODUCT_LIMIT
from scraper import AboutBlankScraper

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraper_test.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

async def main():
    """Main scraper execution - test version with limited products"""
    limit = PRODUCT_LIMIT if PRODUCT_LIMIT > 0 else 5
    logger.info(f"Starting About Blank scraper (TEST MODE - limited to {limit} products)...")

    try:
        # Initialize scraper
        scraper = AboutBlankScraper()

        # Discover product URLs
        logger.info("Discovering product URLs...")
        product_urls = await scraper.discover_product_urls()

        if not product_urls:
            logger.info("No new products found to scrape")
            return

        # Limit products (PRODUCT_LIMIT from env; 0 = use 5 for this test script)
        limit = PRODUCT_LIMIT if PRODUCT_LIMIT > 0 else 5
        test_urls = product_urls[:limit]
        logger.info(f"Limited to {len(test_urls)} products for testing")

        # Scrape all products
        logger.info(f"Starting to scrape {len(test_urls)} test products...")
        products = await scraper.scrape_all_products(test_urls)

        if not products:
            logger.warning("No products were successfully scraped")
            return

        # Sync to database
        sync_result = scraper.sync_products_to_db(products)

        logger.info("Test scraping completed successfully!")
        logger.info(
            f"Summary: {len(test_urls)} attempted, {len(products)} scraped | "
            f"inserted={sync_result['inserted']}, updated={sync_result['updated']}, "
            f"skipped={sync_result['skipped']}, deleted={sync_result['deleted']}"
        )

        # Show sample product
        if products:
            sample = products[0]
            logger.info("Sample product data:")
            logger.info(f"  Title: {sample.get('title')}")
            logger.info(f"  Price: {sample.get('price')}")
            logger.info(f"  Category: {sample.get('category')}")
            logger.info(f"  Has image_embedding: {sample.get('image_embedding') is not None}")
            logger.info(f"  Has info_embedding: {sample.get('info_embedding') is not None}")

    except Exception as e:
        logger.error(f"Fatal error during scraping: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())