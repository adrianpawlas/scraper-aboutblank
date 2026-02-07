import asyncio
import hashlib
import aiohttp
import requests
from fake_useragent import UserAgent
from bs4 import BeautifulSoup
import re
import uuid
from urllib.parse import urljoin
from config import HEADERS, BASE_URL, MAX_CONCURRENT_REQUESTS


def generate_product_id(source: str, product_url: str) -> str:
    """Stable id for upsert: same product always gets the same row."""
    id_string = f"{source}:{product_url}"
    return hashlib.sha256(id_string.encode("utf-8")).hexdigest()


def generate_uuid():
    """Generate a unique UUID for product ID (legacy). Prefer generate_product_id for products."""
    return str(uuid.uuid4())

def clean_text(text):
    """Clean and normalize text"""
    if not text:
        return None
    return ' '.join(text.strip().split())

def extract_price(text):
    """Extract price from text, handling currency symbols (returns single float)."""
    if not text:
        return None
    cleaned = re.sub(r'[£$€¥₹₽₩₦₨₪₫₡₵₺₴₸₼₲₱₭₯₰₳₶₷₹₻₽₾₿]', '', text)
    match = re.search(r'(\d+(?:\.\d{2})?)', cleaned)
    return float(match.group(1)) if match else None


# Currency symbols/codes we recognize for multi-currency price extraction
CURRENCY_SYMBOLS = {'$': 'USD', '€': 'EUR', '£': 'GBP', '¥': 'JPY', 'Kč': 'CZK', 'kr': 'SEK', 'zł': 'PLN', 'Ft': 'HUF'}
CURRENCY_CODES = {'USD', 'EUR', 'GBP', 'JPY', 'CZK', 'PLN', 'SEK', 'NOK', 'DKK', 'CHF', 'HUF', 'RON', 'BGN'}


def _normalize_price_value(val: float, currency: str) -> float:
    """Convert cents to units for USD/EUR/GBP when value looks like cents (e.g. 2000 -> 20)."""
    if currency in ('USD', 'EUR', 'GBP') and val >= 100 and val == int(val):
        # Likely stored in cents
        return round(val / 100.0, 2)
    return val


def extract_prices_with_currencies(soup):
    """
    Extract one price per currency from product page. Returns "20USD, 5EUR" or None.
    Normalizes cents to dollars for USD/EUR/GBP. Ensures at least USD or EUR.
    """
    import json
    # Priority order: JSON-LD (display) first, then visible, then script. One value per currency.
    by_currency = {}

    def add(val, c):
        c = (c or 'USD').upper()[:3]
        val = _normalize_price_value(val, c)
        if c not in by_currency:
            by_currency[c] = val
        # Prefer value that looks like display (not huge); keep first from higher-priority source
        elif val < 10000 and by_currency[c] > 10000:
            by_currency[c] = val

    # 1) JSON-LD (most reliable display price)
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            data = json.loads(script.string or '{}')
            if isinstance(data, dict) and data.get('@type') == 'Product':
                offers = data.get('offers')
                if isinstance(offers, dict):
                    offers = [offers]
                for o in (offers or []):
                    if not isinstance(o, dict):
                        continue
                    p, c = o.get('price'), (o.get('priceCurrency') or 'USD').upper()[:3]
                    if p is not None:
                        try:
                            add(float(p), c)
                        except (TypeError, ValueError):
                            pass
            if isinstance(data, list):
                for g in data:
                    if isinstance(g, dict) and g.get('@type') == 'Product':
                        for o in (g.get('offers') or []) if isinstance(g.get('offers'), list) else ([g.get('offers')] if isinstance(g.get('offers'), dict) else []):
                            if not isinstance(o, dict):
                                continue
                            p, c = o.get('price'), (o.get('priceCurrency') or 'USD').upper()[:3]
                            if p is not None:
                                try:
                                    add(float(p), c)
                                except (TypeError, ValueError):
                                    pass
        except (json.JSONDecodeError, TypeError):
            pass

    # 2) Visible price elements (display prices)
    for elem in soup.select('.price, .product-price, [data-price], .current-price, .money'):
        text = (elem.get_text() or '').strip()
        if not text or len(text) > 50:
            continue
        for m in re.finditer(r'(\d+(?:[.,]\d{1,2})?)\s*([A-Z]{3})?', text):
            try:
                val = float(m.group(1).replace(',', '.'))
            except ValueError:
                continue
            c = (m.group(2) or '').upper() or None
            if not c:
                c = 'USD' if '$' in text else 'EUR' if '€' in text else 'GBP' if '£' in text else 'USD'
            if c:
                add(val, c)
            break  # one price per element

    # 3) Scripts: Shopify variant price (often in cents) - only fill if we don't have that currency yet
    for script in soup.find_all('script', string=re.compile(r'price|variant|money_format')):
        s = script.string or ''
        for m in re.finditer(r'"price"\s*:\s*["\']?(\d+(?:\.\d*)?)', s):
            try:
                raw = float(m.group(1))
                c = 'USD'
                if 'EUR' in s or '€' in s:
                    c = 'EUR'
                elif 'GBP' in s or '£' in s:
                    c = 'GBP'
                elif 'CZK' in s or 'Kč' in s:
                    c = 'CZK'
                elif 'PLN' in s or 'zł' in s:
                    c = 'PLN'
                if c not in by_currency:
                    add(raw, c)
            except (ValueError, IndexError):
                pass
        break  # one script pass

    if not by_currency:
        return None
    has_usd_eur = any(c in ('USD', 'EUR') for c in by_currency)
    if not has_usd_eur:
        first_val = next(iter(by_currency.values()))
        by_currency['USD'] = _normalize_price_value(first_val, 'USD')
    parts = [f"{int(v) if v == int(v) else v}{c}" for c, v in sorted(by_currency.items())]
    return ", ".join(parts)

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

def normalize_category_display(name):
    """Turn 'Sweaters & Hoodies' into 'Sweaters, Hoodies' (comma-separated, no ' & ')."""
    if not name or not name.strip():
        return None
    s = name.strip().replace(" & ", ", ").replace(" and ", ", ")
    s = re.sub(r',\s*,', ',', s).strip(' ,')
    return s if s else None


def map_raw_categories_to_canonical(raw_names):
    """
    Map raw category/collection names to canonical: clothes, footwear, accessories.
    Returns comma-separated string e.g. "clothes" or "clothes, accessories".
    """
    from config import CATEGORY_MAPPING
    canonical = set()
    for raw in raw_names:
        if not raw or not raw.strip():
            continue
        lower = raw.lower().strip()
        for canonical_name, keywords in CATEGORY_MAPPING.items():
            if any(kw in lower for kw in keywords):
                canonical.add(canonical_name)
                break
    if not canonical:
        return None
    return ", ".join(sorted(canonical))


def extract_categories_from_page(soup, base_url):
    """
    Extract category from product page and map to canonical: clothes, footwear, accessories.
    Returns comma-separated canonical string e.g. "clothes" or "clothes, accessories".
    """
    from urllib.parse import unquote
    import json
    raw_names = []
    seen = set()

    # 1) Links to /collections/xxx
    for a in soup.find_all('a', href=re.compile(r'/collections/[\w\-]+')):
        href = a.get('href') or ''
        m = re.search(r'/collections/([^/?#]+)', href)
        if m:
            raw = unquote(m.group(1)).replace('-', ' ').strip()
            if raw and raw.lower() not in seen:
                seen.add(raw.lower())
                raw_names.append(raw)
            norm = normalize_category_display(raw)
            if norm:
                for part in [p.strip() for p in norm.split(',') if p.strip()]:
                    if part.lower() not in seen:
                        seen.add(part.lower())
                        raw_names.append(part)

    # 2) JSON-LD breadcrumb / product category
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            data = json.loads(script.string or '{}')
            if isinstance(data, dict) and data.get('@type') == 'BreadcrumbList':
                for item in data.get('itemListElement', []):
                    name = item.get('name') if isinstance(item, dict) else None
                    if name and name.lower() not in seen and name.lower() not in ('home', 'products', 'shop', 'all'):
                        seen.add(name.lower())
                        raw_names.append(name)
            if isinstance(data, dict) and data.get('@type') == 'Product':
                for cat in (data.get('category') or data.get('categories') or []):
                    if isinstance(cat, str) and cat.lower() not in seen:
                        seen.add(cat.lower())
                        raw_names.append(cat)
        except (json.JSONDecodeError, TypeError):
            pass

    return map_raw_categories_to_canonical(raw_names)


def determine_category(collection_name, product_title):
    """Fallback: determine category from collection/title when page extraction has nothing."""
    from config import CATEGORY_MAPPING
    collection_lower = collection_name.lower() if collection_name else ""
    title_lower = product_title.lower() if product_title else ""
    for category, keywords in CATEGORY_MAPPING.items():
        if any(keyword in collection_lower for keyword in keywords):
            return category
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

def _normalize_image_src(src, base_url=BASE_URL):
    """Normalize image src to full URL."""
    if not src:
        return None
    if src.startswith('//'):
        return 'https:' + src
    if src.startswith('/'):
        return urljoin(base_url, src)
    if not src.startswith('http'):
        return urljoin(base_url, src)
    return src


def get_all_product_image_urls(soup, base_url=BASE_URL):
    """
    Extract all product image URLs. First item is the main image, rest are additional.
    Returns list of full URLs, deduplicated, main first.
    """
    all_imgs = soup.find_all('img')
    seen = set()
    ordered_urls = []  # (order_index, url) for stable ordering
    product_cdn_urls = []  # cdn/shop/files URLs in order

    for idx, img in enumerate(all_imgs):
        src = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
        if not src or any(word in src.lower() for word in ['icon', 'logo', 'social', 'favicon', 'menu']):
            continue
        url = _normalize_image_src(src, base_url)
        if not url or url in seen:
            continue
        seen.add(url)
        if 'cdn/shop/files' in src:
            product_cdn_urls.append((idx, url))
        ordered_urls.append((idx, url))

    # Prefer product CDN images as product gallery
    candidate_list = product_cdn_urls if product_cdn_urls else ordered_urls
    if not candidate_list:
        return []

    # Main image: first one with good alt, or first CDN, or first any
    main_url = None
    for img in all_imgs:
        src = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
        alt = img.get('alt', '').lower()
        if src and alt and len(alt) > 3 and not any(g in alt for g in ['logo', 'icon', 'social', 'menu', 'search']):
            url = _normalize_image_src(src, base_url)
            if url and url in seen:
                main_url = url
                break
    if not main_url and product_cdn_urls:
        main_url = product_cdn_urls[0][1]
    if not main_url and ordered_urls:
        main_url = ordered_urls[0][1]

    # Build result: main first, then rest in order of appearance
    result = [main_url] if main_url else []
    for _, url in sorted(candidate_list, key=lambda x: x[0]):
        if url != main_url:
            result.append(url)
    return result


def get_image_url(soup, base_url=BASE_URL):
    """Extract main product image URL (first from get_all_product_image_urls)."""
    urls = get_all_product_image_urls(soup, base_url)
    return urls[0] if urls else None

def is_in_stock(soup):
    """Check if product is in stock - prioritize UI elements over script data"""
    # Check for out of stock indicators
    out_of_stock_indicators = [
        'sold out',
        'out of stock',
        'unavailable',
        'notify when available',
        'coming soon',
        'pre-order',
        'temporarily unavailable'
    ]

    text_content = soup.get_text().lower()
    for indicator in out_of_stock_indicators:
        if indicator in text_content:
            return False

    # PRIORITY 1: Check for functional add to cart button (most user-facing indicator)
    add_to_cart_buttons = soup.find_all('button', string=re.compile('add to cart|add to bag|buy now|shop now', re.I))
    for button in add_to_cart_buttons:
        if button.get('disabled') is None:
            # Check if button has proper styling/classes that indicate it's active
            button_classes = button.get('class', [])
            if not any(cls for cls in button_classes if 'disabled' in cls.lower() or 'unavailable' in cls.lower()):
                return True

    # PRIORITY 2: Check for add to cart form (Shopify pattern)
    cart_form = soup.find('form', {'action': re.compile('/cart/add')})
    if cart_form:
        # Make sure form isn't hidden or disabled
        if cart_form.get('style') != 'display: none' and not cart_form.get('disabled'):
            return True

    # PRIORITY 3: Check for quantity selector
    quantity_input = soup.find('input', {'type': 'number', 'name': 'quantity'})
    if quantity_input and not quantity_input.get('disabled'):
        return True

    # PRIORITY 4: Check for size/variant selectors (if they exist without "out of stock" text)
    size_select = soup.find('select', {'name': 'Size'})
    variant_select = soup.find('select', {'name': 'variant'})
    if (size_select or variant_select):
        # Only consider available if we don't see out of stock indicators
        select_element = size_select or variant_select
        if not select_element.get('disabled'):
            return True

    # PRIORITY 5: Check variant availability in scripts (less reliable, often wrong)
    variant_scripts = soup.find_all('script', string=re.compile('available'))
    for script in variant_scripts:
        if '"available":true' in script.string:
            return True
        # If we find explicit "available":false, it might override UI elements
        elif '"available":false' in script.string:
            # But only if ALL variants are unavailable
            continue

    # PRIORITY 6: Look for any product-related interactive elements
    product_forms = soup.find_all('form', class_=re.compile('product|add-to-cart'))
    for form in product_forms:
        if not form.get('disabled') and form.get('style') != 'display: none':
            return True

    # If we have add-to-cart buttons but variant scripts say false, be more lenient
    # This handles cases where the site has UI elements but script data is wrong
    if add_to_cart_buttons:
        return True

    return False  # Default to out of stock if unclear