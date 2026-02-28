#!/usr/bin/env python3
"""
Check what's in the database
"""

from config import SOURCE
from database import get_db_manager

def check_database():
    db = get_db_manager()

    # Get all existing URLs for this scraper's source
    urls = db.get_existing_product_urls(SOURCE)

    print(f"Found {len(urls)} existing product URLs in database")

    # Show first 10 URLs
    print("\nFirst 10 URLs:")
    for i, url in enumerate(sorted(list(urls))[:10]):
        print(f"  {i+1}: {url}")

    # Check if any are from about-blank
    about_blank_urls = [url for url in urls if 'about---blank.com' in url]
    print(f"\nAbout Blank URLs in database: {len(about_blank_urls)}")

    if about_blank_urls:
        print("Sample About Blank URLs:")
        for url in about_blank_urls[:5]:
            print(f"  {url}")

if __name__ == "__main__":
    check_database()