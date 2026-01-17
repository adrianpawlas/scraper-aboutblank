#!/usr/bin/env python3
"""
Check About Blank site structure
"""

import requests
from bs4 import BeautifulSoup
import re

def check_site():
    url = "https://about---blank.com/collections/shop-all"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    print(f"Fetching {url}...")
    response = requests.get(url, headers=headers, timeout=30)
    print(f"Status: {response.status_code}")

    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'lxml')

        # Look for product links
        product_links = soup.find_all('a', href=re.compile(r'/products/'))
        print(f"Found {len(product_links)} product links")

        for i, link in enumerate(product_links[:5]):  # Show first 5
            print(f"  {i+1}: {link.get('href')}")

        # Look for pagination
        pagination = soup.find('div', class_=re.compile(r'pagination|paginate'))
        if pagination:
            print("Found pagination element")
        else:
            print("No pagination element found")

        # Check for "next" button
        next_btn = soup.find('a', string=re.compile(r'next|Next|NEXT', re.I))
        if next_btn:
            print(f"Found next button: {next_btn.get('href')}")
        else:
            print("No next button found")

        # Look for product grid/container
        product_grid = soup.find('div', class_=re.compile(r'product-grid|products|collection'))
        if product_grid:
            print("Found product grid/container")
        else:
            print("No product grid/container found")

    else:
        print(f"Failed to fetch page: {response.status_code}")

if __name__ == "__main__":
    check_site()