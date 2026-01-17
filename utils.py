import asyncio
import aiohttp
import requests
from fake_useragent import UserAgent
from bs4 import BeautifulSoup
import re
import uuid
from urllib.parse import urljoin
from config import HEADERS, BASE_URL, MAX_CONCURRENT_REQUESTS

def generate_uuid():
    """Generate a unique UUID for product ID"""
    return str(uuid.uuid4())

def clean_text(text):
    """Clean and normalize text"""
    if not text:
        return None
    return ' '.join(text.strip().split())

def extract_price(text):
    """Extract price from text, handling currency symbols"""
    if not text:
        return None

    # Remove currency symbols and find numeric values
    cleaned = re.sub(r'[£$€¥₹₽₩₦₨₪₫₡₵₺₴₸₼₲₱₭₯₰₳₶₷₹₻₽₾₿]', '', text)
    # Find price pattern (e.g., "120.00" or "120")
    match = re.search(r'(\d+(?:\.\d{2})?)', cleaned)
    return float(match.group(1)) if match else None

def extract_sizes(soup):
    """Extract available sizes from product page"""
    sizes = []

    # Look for size options in various formats
    # Check for select dropdown
    size_select = soup.find('select', {'name': 'Size'})
    if size_select:
        options = size_select.find_all('option')
        for option in options:
            if option.get('value') and option.get('value') != 'Size':
                sizes.append(option.get('value'))

    # Check for size buttons/swatches
    size_buttons = soup.find_all('input', {'name': 'Size'})
    for button in size_buttons:
        if button.get('value'):
            sizes.append(button.get('value'))

    # Look for size labels in variant data
    variant_script = soup.find('script', string=re.compile('variant'))
    if variant_script:
        variants_match = re.search(r'variants\s*:\s*\[(.*?)\]', variant_script.string, re.DOTALL)
        if variants_match:
            variants_text = variants_match.group(1)
            size_matches = re.findall(r'"option(\d+)"\s*:\s*"([^"]*)"', variants_text)
            for _, size in size_matches:
                if size and size.lower() != 'default title':
                    sizes.append(size)

    return list(set(sizes))  # Remove duplicates

def determine_category(collection_name, product_title):
    """Determine category based on collection name and product title"""
    from config import CATEGORY_MAPPING

    collection_lower = collection_name.lower() if collection_name else ""
    title_lower = product_title.lower() if product_title else ""

    # Check collection mapping
    for category, keywords in CATEGORY_MAPPING.items():
        if any(keyword in collection_lower for keyword in keywords):
            return category

    # Fallback to title-based detection
    if any(word in title_lower for word in ['hat', 'cap', 'beanie', 'scarf', 'belt', 'bag', 'wallet']):
        return 'accessories'

    if any(word in title_lower for word in ['t-shirt', 'hoodie', 'sweatshirt', 'jacket', 'coat', 'pants', 'jeans', 'shirt', 'vest', 'knitwear']):
        return 'clothes'

    return None

def determine_gender(category):
    """Determine gender based on category"""
    if category == 'accessories':
        return None
    return 'man'

async def fetch_url(session, url, timeout=30):
    """Async fetch URL with proper error handling"""
    try:
        async with session.get(url, timeout=timeout) as response:
            response.raise_for_status()
            return await response.text()
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

def sync_fetch_url(url, timeout=30):
    """Synchronous fetch URL"""
    try:
        response = requests.get(url, headers=HEADERS, timeout=timeout)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

def setup_session():
    """Setup aiohttp session with proper headers"""
    ua = UserAgent()
    headers = HEADERS.copy()
    headers['User-Agent'] = ua.random
    return aiohttp.ClientSession(headers=headers, connector=aiohttp.TCPConnector(limit=MAX_CONCURRENT_REQUESTS))

def get_image_url(soup, base_url=BASE_URL):
    """Extract main product image URL"""
    all_imgs = soup.find_all('img')

    # First priority: images with product name in alt text
    for img in all_imgs:
        src = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
        alt = img.get('alt', '').lower()
        if src and alt and len(alt) > 3:  # Avoid empty or very short alt text
            # Check if alt text contains product-related words or is not generic
            if not any(generic in alt for generic in ['logo', 'icon', 'social', 'menu', 'search']):
                if src.startswith('//'):
                    src = 'https:' + src
                elif src.startswith('/'):
                    src = urljoin(base_url, src)
                elif not src.startswith('http'):
                    src = urljoin(base_url, src)
                return src

    # Second priority: any image from the product CDN
    for img in all_imgs:
        src = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
        if src and 'cdn/shop/files' in src:
            if src.startswith('//'):
                src = 'https:' + src
            elif src.startswith('/'):
                src = urljoin(base_url, src)
            elif not src.startswith('http'):
                src = urljoin(base_url, src)
            return src

    # Last resort: any image that's not clearly an icon/logo
    for img in all_imgs:
        src = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
        if src and not any(word in src.lower() for word in ['icon', 'logo', 'social', 'favicon', 'menu']):
            if src.startswith('//'):
                src = 'https:' + src
            elif src.startswith('/'):
                src = urljoin(base_url, src)
            elif not src.startswith('http'):
                src = urljoin(base_url, src)
            return src

    return None

def is_in_stock(soup):
    """Check if product is in stock"""
    # Check for out of stock indicators
    out_of_stock_indicators = [
        'sold out',
        'out of stock',
        'unavailable',
        'notify when available'
    ]

    text_content = soup.get_text().lower()
    for indicator in out_of_stock_indicators:
        if indicator in text_content:
            return False

    # Check for add to cart button
    add_to_cart = soup.find('button', string=re.compile('add to cart|add to bag', re.I))
    if add_to_cart and add_to_cart.get('disabled') is None:
        return True

    # Check for variant availability
    variant_script = soup.find('script', string=re.compile('available'))
    if variant_script:
        if '"available":true' in variant_script.string:
            return True

    return False  # Default to out of stock if unclear