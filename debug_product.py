#!/usr/bin/env python3
"""
Debug product data
"""

import asyncio
from scraper import AboutBlankScraper

async def debug_product():
    scraper = AboutBlankScraper()
    urls = await scraper.discover_product_urls()

    print(f"Found {len(urls)} URLs")
    if urls:
        print(f"First URL: {urls[0]}")

        import aiohttp
        from utils import setup_session, sync_fetch_url
        from bs4 import BeautifulSoup

        # Try synchronous fetch first
        print("Fetching with sync_fetch_url...")
        html = sync_fetch_url(urls[0])
        if html:
            print(f"HTML length: {len(html)}")
            soup = BeautifulSoup(html, 'lxml')

            # Check if in stock
            from utils import is_in_stock
            in_stock = is_in_stock(soup)
            print(f"In stock: {in_stock}")

            if not in_stock:
                print("Product is out of stock, trying another URL...")
                # Try another URL
                for url in urls[1:6]:  # Try next 5
                    html = sync_fetch_url(url)
                    if html:
                        soup = BeautifulSoup(html, 'lxml')
                        if is_in_stock(soup):
                            print(f"Found in-stock product: {url}")
                            break

            # Extract title
            title = scraper._extract_title(soup)
            print(f"Title: {title}")

            # Extract price
            price = scraper._extract_price(soup)
            print(f"Price: {price}")

            # Extract image
            from utils import get_image_url
            image_url = get_image_url(soup)
            print(f"Image URL: {image_url}")

        else:
            print("Failed to fetch HTML")

        # Now try the full scrape
        print("\nTrying full scrape...")
        async with setup_session() as session:
            product = await scraper.scrape_product(session, urls[0])

        if product:
            print("Product data:")
            for key, value in product.items():
                if key == 'embedding' and value is not None:
                    print(f"  {key}: [list of {len(value)} floats]")
                else:
                    print(f"  {key}: {value} (type: {type(value)})")

            # Check required fields
            required_fields = ['id', 'title', 'image_url']
            missing = [field for field in required_fields if not product.get(field)]
            if missing:
                print(f"Missing required fields: {missing}")
            else:
                print("All required fields present")
        else:
            print("No product data returned")

if __name__ == "__main__":
    asyncio.run(debug_product())