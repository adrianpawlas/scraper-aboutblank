#!/usr/bin/env python3
"""
Debug the product discovery
"""

import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin

BASE_URL = "https://about---blank.com"
SHOP_ALL_URL = f"{BASE_URL}/collections/shop-all"

def debug_discovery():
    from utils import sync_fetch_url

    url = SHOP_ALL_URL
    print(f"Fetching {url} using sync_fetch_url...")

    html = sync_fetch_url(url)
    if html:
        print("Successfully fetched HTML")
        print(f"HTML length: {len(html)}")
    else:
        print("Failed to fetch HTML")

    # Also try direct requests
    print(f"\nFetching {url} using direct requests...")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    response = requests.get(url, headers=headers, timeout=30)
    print(f"Direct requests status: {response.status_code}")

    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'lxml')

        # Find product links
        product_links = soup.find_all('a', href=re.compile(r'/products/'))
        print(f"Found {len(product_links)} total links with '/products/'")

        # Extract unique URLs
        product_urls = set()
        for link in product_links:
            href = link.get('href')
            if href and '/products/' in href:
                # Clean up the URL
                if href.startswith('/'):
                    full_url = urljoin(BASE_URL, href)
                else:
                    full_url = href

                # Remove any query parameters or fragments
                full_url = full_url.split('?')[0].split('#')[0]
                product_urls.add(full_url)

        print(f"Extracted {len(product_urls)} unique product URLs")

        # Show first 10 URLs
        print("\nFirst 10 URLs:")
        for i, url in enumerate(sorted(list(product_urls))[:10]):
            print(f"  {i+1}: {url}")

        # Check for duplicates in original links
        print(f"\nOriginal links count: {len(product_links)}")
        hrefs = [link.get('href') for link in product_links if link.get('href')]
        unique_hrefs = set(hrefs)
        print(f"Unique hrefs: {len(unique_hrefs)}")

        print("\nSample hrefs:")
        for href in list(unique_hrefs)[:10]:
            print(f"  {href}")

    else:
        print(f"Failed to fetch page: {response.status_code}")

if __name__ == "__main__":
    debug_discovery()