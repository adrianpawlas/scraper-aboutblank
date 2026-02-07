import asyncio
import aiohttp
import json
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin
from typing import List, Dict, Any, Optional
from config import BASE_URL, SHOP_ALL_URL, HEADERS, REQUESTS_PER_SECOND, MAX_CONCURRENT_REQUESTS
from utils import (
    generate_product_id, clean_text, extract_price, extract_sizes,
    determine_category, determine_gender, is_in_stock, get_all_product_image_urls,
    setup_session, sync_fetch_url
)
from embedding import generate_image_embedding, generate_text_embedding
from database import get_db_manager
import logging
from tqdm import tqdm
import time

logger = logging.getLogger(__name__)


def _discover_via_shopify_json(base_url: str, collection_handle: str, existing_urls: set) -> List[str]:
    """Fallback: discover product URLs via Shopify's collection products.json API."""
    product_urls = []
    page = 1
    base_json_url = f"{base_url}/collections/{collection_handle}/products.json"

    while True:
        url = f"{base_json_url}?page={page}"
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            logger.warning(f"Shopify JSON fallback failed for {url}: {e}")
            break

        products = data.get("products") if isinstance(data, dict) else []
        if not products:
            break

        for p in products:
            handle = p.get("handle")
            if not handle:
                continue
            full_url = f"{base_url}/products/{handle}"
            if full_url not in existing_urls:
                product_urls.append(full_url)

        # Shopify usually returns 50–250 per page; if less, we're done
        if len(products) < 50:
            break
        page += 1
        time.sleep(0.5)

    return product_urls


class AboutBlankScraper:
    def __init__(self):
        self.db_manager = get_db_manager()
        self.semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
        self.existing_urls = self.db_manager.get_existing_product_urls("scraper")

    async def discover_product_urls(self) -> List[str]:
        """Discover all product URLs from the shop-all collection."""
        logger.info("Starting product URL discovery...")

        product_urls = set()
        page = 1

        while True:
            url = f"{SHOP_ALL_URL}?page={page}" if page > 1 else SHOP_ALL_URL
            logger.info(f"Fetching page {page}: {url}")

            html = sync_fetch_url(url)
            if not html:
                break

            soup = BeautifulSoup(html, 'lxml')
            products_found_on_page = 0

            # Find product links
            product_links = soup.find_all('a', href=re.compile(r'/products/'))
            logger.info(f"Found {len(product_links)} links with '/products/' on page {page}")

            for link in product_links:
                href = link.get('href')
                if href and '/products/' in href:
                    if href.startswith('/'):
                        full_url = urljoin(BASE_URL, href)
                    else:
                        full_url = href
                    full_url = full_url.split('?')[0].split('#')[0]
                    if full_url not in self.existing_urls:
                        product_urls.add(full_url)
                        products_found_on_page += 1

            logger.info(f"Found {products_found_on_page} new products on page {page}")

            next_page = soup.find('a', string=re.compile(r'next|Next|NEXT', re.I))
            if not next_page or products_found_on_page == 0:
                if page > 1 and products_found_on_page == 0:
                    logger.info("No more products found, stopping discovery")
                break

            page += 1
            await asyncio.sleep(1 / REQUESTS_PER_SECOND)
            if page > 50:
                logger.warning("Reached page limit (50), stopping discovery")
                break

        # If HTML returned no links (e.g. JS-only, bot block, or changed structure), use Shopify JSON API
        if not product_urls:
            logger.info("No product links in HTML; trying Shopify collection products.json...")
            try:
                match = re.search(r'/collections/([^/?#]+)', SHOP_ALL_URL)
                handle = match.group(1) if match else "shop-all"
                discovered = _discover_via_shopify_json(BASE_URL, handle, self.existing_urls)
                product_urls = set(discovered)
                logger.info(f"Shopify JSON fallback found {len(product_urls)} product URLs")
            except Exception as e:
                logger.warning(f"Shopify JSON fallback error: {e}")

        logger.info(f"Discovered {len(product_urls)} new product URLs")
        return list(product_urls)

    async def scrape_product(self, session: aiohttp.ClientSession, url: str) -> Optional[Dict[str, Any]]:
        """Scrape individual product page"""
        async with self.semaphore:
            try:
                response = await session.get(url)
                response.raise_for_status()
                html = await response.text()
                soup = BeautifulSoup(html, 'lxml')

                # We now scrape ALL products regardless of stock status
                # Stock status is determined and stored in metadata

                # Extract basic product info
                title = self._extract_title(soup)
                if not title:
                    logger.warning(f"Could not extract title for {url}")
                    return None

                description = self._extract_description(soup)
                price = self._extract_price(soup)
                all_image_urls = get_all_product_image_urls(soup)
                image_url = all_image_urls[0] if all_image_urls else None
                additional_images = None
                if len(all_image_urls) > 1:
                    additional_images = " , ".join(all_image_urls[1:])
                sizes = extract_sizes(soup)
                collection = self._extract_collection(url)

                # Determine category and gender
                category = determine_category(collection, title)
                gender = determine_gender(category)

                # Check stock status (but don't skip - we want all products)
                from utils import is_in_stock
                in_stock = is_in_stock(soup)

                # Generate image embedding if main image exists
                image_embedding = None
                if image_url:
                    logger.info(f"Generating embedding for {title}")
                    image_embedding = await generate_image_embedding(image_url)

                # Build product info text for text embedding (name, category, size(s), description, etc.)
                info_parts = [title]
                if category:
                    info_parts.append(category)
                if gender:
                    info_parts.append(gender)
                if sizes:
                    info_parts.append(" ".join(sizes))
                if description:
                    info_parts.append(description)
                if collection:
                    info_parts.append(collection)
                if price is not None:
                    info_parts.append(str(price))
                info_text = " ".join(p for p in info_parts if p)
                info_embedding = None
                if info_text:
                    info_embedding = await generate_text_embedding(info_text)

                # Create product data
                import json
                metadata = {
                    'in_stock': in_stock,
                    'sizes_available': sizes,
                    'collection': collection
                }

                product_data = {
                    'id': generate_product_id('scraper', url),
                    'source': 'scraper',
                    'product_url': url,
                    'image_url': image_url,
                    'additional_images': additional_images,
                    'brand': 'About Blank',
                    'title': title,
                    'description': description,
                    'category': category,
                    'gender': gender,
                    'price': str(price) if price is not None else None,
                    'size': ','.join(sizes) if sizes else None,
                    'second_hand': False,
                    'image_embedding': image_embedding,
                    'info_embedding': info_embedding,
                    'country': 'US',
                    'metadata': json.dumps(metadata),
                    'tags': self._extract_tags(collection, category)
                }

                return product_data

            except Exception as e:
                logger.error(f"Error scraping product {url}: {e}")
                return None

    def _extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract product title"""
        selectors = [
            'h1.product-title',
            '.product-title h1',
            'h1[data-product-title]',
            '.product-name',
            'h1'
        ]

        for selector in selectors:
            title_elem = soup.select_one(selector)
            if title_elem:
                return clean_text(title_elem.get_text())

        # Fallback: look in meta tags
        meta_title = soup.find('meta', {'property': 'og:title'})
        if meta_title and meta_title.get('content'):
            return clean_text(meta_title['content'])

        return None

    def _extract_description(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract product description"""
        selectors = [
            '.product-description',
            '.product-details',
            '.description',
            '[data-product-description]',
            '.tab-content .description'
        ]

        for selector in selectors:
            desc_elem = soup.select_one(selector)
            if desc_elem:
                return clean_text(desc_elem.get_text())

        # Fallback: look for structured data
        script = soup.find('script', {'type': 'application/ld+json'})
        if script:
            try:
                import json
                data = json.loads(script.string)
                if isinstance(data, dict) and 'description' in data:
                    return clean_text(data['description'])
            except:
                pass

        return None

    def _extract_price(self, soup: BeautifulSoup) -> Optional[float]:
        """Extract product price"""
        selectors = [
            '.product-price',
            '.price',
            '.current-price',
            '[data-price]'
        ]

        for selector in selectors:
            price_elem = soup.select_one(selector)
            if price_elem:
                price_text = price_elem.get_text()
                return extract_price(price_text)

        # Look for price in scripts
        script = soup.find('script', string=re.compile(r'price|Price'))
        if script:
            match = re.search(r'"price"\s*:\s*"([^"]*)"', script.string)
            if match:
                return extract_price(match.group(1))

        return None

    def _extract_collection(self, url: str) -> Optional[str]:
        """Extract collection name from URL"""
        match = re.search(r'/collections/([^/]+)', url)
        if match:
            collection = match.group(1).replace('-', ' ')
            return collection
        return None

    def _extract_tags(self, collection: Optional[str], category: Optional[str]) -> List[str]:
        """Extract tags for the product"""
        tags = []
        if collection:
            tags.append(collection)
        if category:
            tags.append(category)
        return tags

    async def scrape_all_products(self, product_urls: List[str]) -> List[Dict[str, Any]]:
        """Scrape all products concurrently"""
        logger.info(f"Starting to scrape {len(product_urls)} products...")

        async with setup_session() as session:
            tasks = []
            for url in product_urls:
                tasks.append(self.scrape_product(session, url))
                await asyncio.sleep(1 / REQUESTS_PER_SECOND)  # Rate limiting

            # Use tqdm for progress tracking
            products = []
            with tqdm(total=len(tasks), desc="Scraping products") as pbar:
                for coro in asyncio.as_completed(tasks):
                    product = await coro
                    if product:
                        products.append(product)
                    pbar.update(1)

        logger.info(f"Successfully scraped {len(products)} products")
        return products

    def save_products_to_db(self, products: List[Dict[str, Any]]) -> int:
        """Save products to database"""
        logger.info(f"Saving {len(products)} products to database...")

        success_count = self.db_manager.insert_products_batch(products)
        logger.info(f"Saved {success_count}/{len(products)} products to database")

        return success_count