#!/usr/bin/env python3
"""
Local test that mocks DB so we can verify scraper + embedding logic without Supabase.
Run: python run_local_test.py
"""
import asyncio
import sys

# Inject mock database module so scraper never loads real supabase/websockets
class MockDbManager:
    def __init__(self):
        self.existing = set()
    def get_existing_product_urls(self, source):
        return self.existing
    def insert_products_batch(self, products):
        print(f"[MOCK] Would insert {len(products)} products")
        return len(products)

class FakeDatabaseModule:
    _instance = None
    @staticmethod
    def get_db_manager():
        if FakeDatabaseModule._instance is None:
            FakeDatabaseModule._instance = MockDbManager()
        return FakeDatabaseModule._instance

sys.modules["database"] = FakeDatabaseModule()

# Now import scraper (it will use our fake database)
from scraper import AboutBlankScraper

async def main():
    print("=== Local test (mocked DB) ===\n")
    scraper = AboutBlankScraper()
    print("Discovering product URLs...")
    urls = await scraper.discover_product_urls()
    if not urls:
        print("No new URLs (or discovery failed).")
        return 1
    print(f"Found {len(urls)} product URLs. Scraping first 2...\n")
    products = await scraper.scrape_all_products(urls[:2])
    if not products:
        print("No products scraped.")
        return 1
    for i, p in enumerate(products):
        print(f"Product {i+1}: {p.get('title')}")
        print(f"  image_url: {bool(p.get('image_url'))}")
        print(f"  additional_images: {p.get('additional_images', '')[:80]}..." if (p.get('additional_images') or '') and len(p.get('additional_images') or '') > 80 else f"  additional_images: {p.get('additional_images')}")
        print(f"  image_embedding: {len(p.get('image_embedding') or [])} dims")
        print(f"  info_embedding: {len(p.get('info_embedding') or [])} dims")
    print("\n[MOCK] Skipping DB insert.")
    print("=== Local test passed ===\n")
    return 0

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
