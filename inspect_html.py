#!/usr/bin/env python3
"""
Inspect HTML for image tags
"""

import requests
from bs4 import BeautifulSoup

def inspect_html():
    url = "https://about---blank.com/products/box-zip-hoodie-cotton-smoke-blue-ecru"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    response = requests.get(url, headers=headers, timeout=30)
    soup = BeautifulSoup(response.text, 'lxml')

    print("All img tags:")
    imgs = soup.find_all('img')
    for i, img in enumerate(imgs):
        src = img.get('src') or img.get('data-src') or img.get('data-lazy-src') or img.get('data-image')
        alt = img.get('alt', '')
        print(f"  {i+1}: src={src}, alt={alt}")

    print("\nLooking for product images specifically...")
    # Look for images in product-related containers
    product_containers = soup.find_all(['div', 'section'], class_=re.compile(r'product|image|gallery|photo'))
    for container in product_containers[:3]:  # First 3 containers
        print(f"Container: {container.get('class')}")
        imgs = container.find_all('img')
        for img in imgs:
            src = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
            alt = img.get('alt', '')
            print(f"    Image: src={src}, alt={alt}")

if __name__ == "__main__":
    import re
    inspect_html()