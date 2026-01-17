#!/usr/bin/env python3
"""
About Blank Fashion Store Scraper
Scrapes all products, generates image embeddings, and stores in Supabase
"""

import asyncio
import logging
import sys
from scraper import AboutBlankScraper
from config import SHOP_ALL_URL

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraper.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

async def main():
    """Main scraper execution"""
    logger.info("Starting About Blank scraper...")

    try:
        # Initialize scraper
        scraper = AboutBlankScraper()

        # Discover product URLs
        logger.info("Discovering product URLs...")
        product_urls = await scraper.discover_product_urls()

        if not product_urls:
            logger.info("No new products found to scrape")
            return

        # Scrape all products
        logger.info(f"Found {len(product_urls)} products to scrape")
        products = await scraper.scrape_all_products(product_urls)

        if not products:
            logger.warning("No products were successfully scraped")
            return

        # Save to database
        saved_count = scraper.save_products_to_db(products)

        logger.info("Scraping completed successfully!")
        logger.info(f"Summary: {len(product_urls)} discovered, {len(products)} scraped, {saved_count} saved to DB")

    except Exception as e:
        logger.error(f"Fatal error during scraping: {e}")
        raise

if __name__ == "__main__":
    # Run the scraper
    asyncio.run(main())