#!/usr/bin/env python3
"""
Debug stock detection for About Blank products
"""

import requests
from bs4 import BeautifulSoup
import re

def check_product_stock(url):
    """Check stock status of a specific product"""
    print(f"\n=== Checking: {url} ===")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'lxml')
        text_content = soup.get_text().lower()

        print(f"Page title: {soup.find('title').get_text() if soup.find('title') else 'No title'}")

        # Check for out of stock indicators
        out_of_stock_indicators = [
            'sold out',
            'out of stock',
            'unavailable',
            'notify when available'
        ]

        found_indicators = []
        for indicator in out_of_stock_indicators:
            if indicator in text_content:
                found_indicators.append(indicator)

        if found_indicators:
            print(f"[OUT OF STOCK] Found out-of-stock indicators: {found_indicators}")
            return False

        # Check for add to cart button
        add_to_cart = soup.find('button', string=re.compile('add to cart|add to bag', re.I))
        if add_to_cart:
            disabled = add_to_cart.get('disabled')
            if disabled is None:
                print("[IN STOCK] Found active add-to-cart button")
                return True
            else:
                print(f"[OUT OF STOCK] Found disabled add-to-cart button (disabled='{disabled}')")
                return False
        else:
            print("[UNKNOWN] No add-to-cart button found")

        # Check for variant availability in scripts
        variant_scripts = soup.find_all('script', string=re.compile('available'))
        if variant_scripts:
            for script in variant_scripts:
                if '"available":true' in script.string:
                    print("[IN STOCK] Found variant availability: true")
                    return True
                elif '"available":false' in script.string:
                    print("[OUT OF STOCK] Found variant availability: false")
                    return False

        # Look for other availability indicators
        availability_indicators = soup.find_all(string=re.compile(r'available|in stock|out of stock', re.I))
        if availability_indicators:
            print("Found availability text:")
            for indicator in availability_indicators[:3]:  # Show first 3
                print(f"  '{indicator.strip()}'")

        # Check for form with variant selection (common Shopify pattern)
        variant_form = soup.find('form', {'action': re.compile('/cart/add')})
        if variant_form:
            print("[IN STOCK] Found add-to-cart form")
            return True

        # Check for quantity input
        quantity_input = soup.find('input', {'type': 'number', 'name': 'quantity'})
        if quantity_input:
            print("[IN STOCK] Found quantity input")
            return True

        print("[UNKNOWN] No clear stock indicators found - defaulting to out of stock")
        return False

    except Exception as e:
        print(f"Error checking product: {e}")
        return False

def main():
    """Check a few products to understand the pattern"""
    test_urls = [
        "https://about---blank.com/products/box-zip-hoodie-cotton-smoke-blue-ecru",
        "https://about---blank.com/products/leather-jacket-leather-black",
        "https://about---blank.com/products/emblem-t-shirt-cotton-oat-gold"
    ]

    for url in test_urls:
        result = check_product_stock(url)
        print(f"Result: {'IN STOCK' if result else 'OUT OF STOCK'}")

if __name__ == "__main__":
    main()