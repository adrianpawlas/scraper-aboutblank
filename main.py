import asyncio
import sys
import argparse
from scraper import ProductScraper
from database import DatabaseService
from config import SOURCE, CATEGORY_URLS


async def main(test_mode=False, test_count=3):
    print("=" * 60)
    print("About Blank Scraper Starting")
    print(f"Source: {SOURCE}")
    print("=" * 60)

    scraper = ProductScraper()
    db = DatabaseService()

    print("\n[1/3] Scraping products from About Blank...")
    products = await scraper.run()

    print(f"\nScraped {len(products)} products")

    if test_mode and len(products) > test_count:
        print(f"\n[TEST] Limiting to {test_count} products for testing...")
        products = products[:test_count]

    print("\n[2/3] Inserting products into Supabase...")
    
    # Insert one by one to ensure proper logging
    inserted = 0
    failed = 0
    errors = []
    
    for product in products:
        try:
            result = db.insert_products([product])
            if result['inserted'] > 0:
                inserted += 1
                print(f"  ✓ {product.get('title', 'unknown')}")
            else:
                failed += 1
                errors.extend(result['errors'])
                print(f"  ✗ {product.get('title', 'unknown')}: {result['errors']}")
        except Exception as e:
            failed += 1
            errors.append(str(e))
            print(f"  ✗ {product.get('title', 'unknown')}: {e}")

    results = {"inserted": inserted, "failed": failed, "errors": errors}

    print("\n[3/3] Results:")
    print(f"  - Inserted: {results['inserted']}")
    print(f"  - Failed: {results['failed']}")

    if results['errors']:
        print(f"\nErrors ({len(results['errors'])}):")
        for err in results['errors'][:3]:
            print(f"  - {err}")

    print("\n" + "=" * 60)
    print("Scraping Complete!")
    print("=" * 60)
    
    return results['inserted'] > 0 and results['failed'] == 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='About Blank Scraper')
    parser.add_argument('--test', action='store_true', help='Run in test mode (limited products)')
    parser.add_argument('--count', type=int, default=3, help='Number of products in test mode')
    args = parser.parse_args()
    
    success = asyncio.run(main(test_mode=args.test, test_count=args.count))
    sys.exit(0 if success else 1)