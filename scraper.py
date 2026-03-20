import asyncio
import aiohttp
import json
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone
from config import BASE_URL, SHOP_ALL_URL, HEADERS, REQUESTS_PER_SECOND, MAX_CONCURRENT_REQUESTS, SOURCE
from utils import (
    generate_product_id, clean_text, extract_sizes,
    extract_categories_from_page, extract_prices_with_currencies,
    determine_category, determine_gender, is_in_stock, get_all_product_image_urls,
    setup_session, sync_fetch_url
)
from embedding import generate_image_embedding, generate_text_embedding
from database import get_db_manager
import logging
from tqdm import tqdm
import time

logger = logging.getLogger(__name__)

EMBEDDING_DELAY = 0.5
CONSECUTIVE_MISSES_THRESHOLD = 2


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

    async def discover_product_urls(self) -> List[str]:
        """Discover ALL product URLs from the shop-all collection (no filter by existing)."""
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

            for link in soup.find_all('a', href=re.compile(r'/products/')):
                href = link.get('href')
                if href and '/products/' in href:
                    full_url = urljoin(BASE_URL, href) if href.startswith('/') else href
                    full_url = full_url.split('?')[0].split('#')[0]
                    if full_url not in product_urls:
                        product_urls.add(full_url)
                        products_found_on_page += 1

            logger.info(f"Found {products_found_on_page} products on page {page}")

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

        if not product_urls:
            logger.info("No product links in HTML; trying Shopify collection products.json...")
            try:
                match = re.search(r'/collections/([^/?#]+)', SHOP_ALL_URL)
                handle = match.group(1) if match else "shop-all"
                discovered = _discover_via_shopify_json(BASE_URL, handle, set())
                product_urls = set(discovered)
                logger.info(f"Shopify JSON fallback found {len(product_urls)} product URLs")
            except Exception as e:
                logger.warning(f"Shopify JSON fallback error: {e}")

        logger.info(f"Discovered {len(product_urls)} product URLs in total")
        return list(product_urls)

    async def scrape_product(
        self,
        session: aiohttp.ClientSession,
        url: str,
        *,
        generate_embeddings: bool = True,
    ) -> Optional[Dict[str, Any]]:
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
                price = extract_prices_with_currencies(soup)  # "20USD, 5EUR" or None
                all_image_urls = get_all_product_image_urls(soup)
                image_url = all_image_urls[0] if all_image_urls else None
                additional_images = None
                if len(all_image_urls) > 1:
                    additional_images = " , ".join(all_image_urls[1:])
                sizes = extract_sizes(soup)
                collection = self._extract_collection(url)

                # Category from page (collection links, breadcrumb); fallback to determine_category
                category = extract_categories_from_page(soup, url)
                if not category:
                    category = determine_category(collection, title)
                gender = determine_gender(category)

                # Check stock status (but don't skip - we want all products)
                from utils import is_in_stock
                in_stock = is_in_stock(soup)

                # Generate image embedding if main image exists
                image_embedding = None
                if generate_embeddings and image_url:
                    logger.info(f"Generating embedding for {title}")
                    image_embedding = await generate_image_embedding(image_url)
                    await asyncio.sleep(EMBEDDING_DELAY)

                # Build product info text for text embedding (name, category, size(s), description, etc.)
                info_parts = [title]
                info_embedding = None
                if generate_embeddings:
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
                    if price:
                        info_parts.append(price)
                    info_text = " ".join(p for p in info_parts if p)
                    if info_text:
                        info_embedding = await generate_text_embedding(info_text)
                        await asyncio.sleep(EMBEDDING_DELAY)

                # Create product data
                import json
                metadata = {
                    'name': title,
                    'description': description,
                    'price': price,
                    'sizes': sizes,
                    'category': category,
                    'gender': gender,
                    'brand': 'About Blank',
                    'image_url': image_url,
                    'additional_images': additional_images,
                    'in_stock': in_stock,
                    'collection': collection,
                    'country': None,
                    'second_hand': False,
                    'tags': self._extract_tags(collection, category),
                    'product_url': url,
                }

                product_data = {
                    'id': generate_product_id(SOURCE, url),
                    'source': SOURCE,
                    'product_url': url,
                    'image_url': image_url,
                    'additional_images': additional_images,
                    'brand': 'About Blank',
                    'title': title,
                    'description': description,
                    'category': category,
                    'gender': gender,
                    'price': price,  # "20USD, 5EUR" or None
                    'size': ','.join(sizes) if sizes else None,
                    'second_hand': False,
                    'image_embedding': image_embedding,
                    'info_embedding': info_embedding,
                    'country': None,
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
                # Scrape core fields first; embeddings are generated later only when needed.
                tasks.append(self.scrape_product(session, url, generate_embeddings=False))
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
        """Legacy: insert all (no sync). Prefer sync_products_to_db for full sync."""
        logger.info(f"Saving {len(products)} products to database...")
        success_count = self.db_manager.insert_products_batch(products)
        logger.info(f"Saved {success_count}/{len(products)} products to database")
        return success_count

    def _build_info_text_for_embedding(self, product: Dict[str, Any]) -> Optional[str]:
        """
        Rebuild the text used for the SigLIP "text embedding" generation.
        Mirrors the earlier scrape-time text embedding composition.
        """
        title = product.get("title")
        category = product.get("category")
        gender = product.get("gender")
        size = product.get("size")
        description = product.get("description")
        price = product.get("price")

        collection = None
        metadata = product.get("metadata")
        if isinstance(metadata, str):
            try:
                metadata_obj = json.loads(metadata)
                collection = metadata_obj.get("collection")
            except Exception:
                collection = None

        info_parts: List[str] = []
        if title:
            info_parts.append(title)
        if category:
            info_parts.append(category)
        if gender:
            info_parts.append(gender)
        if size:
            # Core scrape stores sizes as comma-separated string.
            info_parts.append(str(size).replace(",", " "))
        if description:
            info_parts.append(description)
        if collection:
            info_parts.append(collection)
        if price:
            info_parts.append(price)

        info_text = " ".join(p for p in info_parts if p)
        return info_text or None

    async def _generate_embeddings_for_products(self, products: List[Dict[str, Any]]) -> None:
        """Generate image/text embeddings sequentially with staggered delay."""
        for p in products:
            image_url = p.get("image_url")
            if image_url:
                p["image_embedding"] = await generate_image_embedding(image_url)
                await asyncio.sleep(EMBEDDING_DELAY)
            else:
                p["image_embedding"] = None

            info_text = self._build_info_text_for_embedding(p)
            if info_text:
                p["info_embedding"] = await generate_text_embedding(info_text)
                await asyncio.sleep(EMBEDDING_DELAY)
            else:
                p["info_embedding"] = None

    def _stale_state_path(self) -> str:
        safe_source = SOURCE.replace("/", "_").replace("\\", "_").replace(":", "_")
        return f"stale_state_{safe_source}.json"

    def _load_stale_state(self) -> Dict[str, int]:
        path = self._stale_state_path()
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if not isinstance(raw, dict):
                return {}
            out: Dict[str, int] = {}
            for k, v in raw.items():
                try:
                    out[str(k)] = int(v)
                except Exception:
                    out[str(k)] = 0
            return out
        except FileNotFoundError:
            return {}
        except Exception as e:
            logger.warning(f"Could not load stale state file: {e}")
            return {}

    def _save_stale_state(self, state: Dict[str, int]) -> None:
        path = self._stale_state_path()
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=True, indent=2)
        except Exception as e:
            logger.warning(f"Could not save stale state file: {e}")

    async def sync_products_to_db(self, products: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Smart full sync:
        - Batch upsert (50 rows/request) for new + changed products.
        - Skip unchanged products entirely (no embedding regen, no product upsert).
        - Delete stale products after 2 consecutive misses using consecutive_misses.
        """
        logger.info(f"Syncing {len(products)} scraped products to database (source={SOURCE})...")

        if not products:
            return {"inserted": 0, "updated": 0, "skipped": 0, "deleted": 0}

        now = datetime.now(timezone.utc).isoformat()

        seen_ids = [p.get("id") for p in products if p.get("id")]
        seen_ids_set = set(seen_ids)

        # 1) Load existing rows for diffing.
        compare_select = ",".join([
            "id",
            "product_url",
            "image_url",
            "title",
            "description",
            "category",
            "gender",
            "price",
            "size",
            "additional_images",
            "metadata",
            "tags",
            "country",
            "second_hand",
            "sale",
            "other",
        ])
        existing_map = self.db_manager.get_products_by_ids(seen_ids, select=compare_select)

        new_products: List[Dict[str, Any]] = []
        updated_products: List[Dict[str, Any]] = []
        unchanged_count = 0

        regen_embedding_products: List[Dict[str, Any]] = []
        no_regen_embedding_ids: List[str] = []

        for p in products:
            product_id = p.get("id")
            if not product_id:
                continue

            existing = existing_map.get(product_id)
            if existing is None:
                new_products.append(p)
                regen_embedding_products.append(p)
                continue

            if _scraped_equals_existing(existing, p):
                unchanged_count += 1
                continue

            updated_products.append(p)

            # Only regenerate embeddings when the product image URL changed.
            existing_image_url = _normalize_product_url(existing.get("image_url"))
            scraped_image_url = _normalize_product_url(p.get("image_url"))
            if existing_image_url != scraped_image_url:
                regen_embedding_products.append(p)
            else:
                no_regen_embedding_ids.append(product_id)

        # 2) Generate embeddings only for new/where image URL changed.
        if regen_embedding_products:
            logger.info(f"Generating embeddings for {len(regen_embedding_products)} products...")
            await self._generate_embeddings_for_products(regen_embedding_products)

        # 3) For updated products where we did not regenerate embeddings, reuse existing embeddings.
        regen_ids = {p.get("id") for p in regen_embedding_products}
        no_regen_embedding_ids = [pid for pid in no_regen_embedding_ids if pid and pid not in regen_ids]
        if no_regen_embedding_ids:
            embed_select = "id,image_embedding,info_embedding"
            existing_emb_map = self.db_manager.get_products_by_ids(
                no_regen_embedding_ids,
                select=embed_select,
            )
            for p in updated_products:
                pid = p.get("id")
                if pid in existing_emb_map and pid not in regen_ids:
                    p["image_embedding"] = existing_emb_map[pid].get("image_embedding")
                    p["info_embedding"] = existing_emb_map[pid].get("info_embedding")

        # 4) Upsert new + changed products in batches of 50 (handled by db layer).
        upsert_products = new_products + updated_products

        failed_ids: set = set()
        failed_count = 0
        if upsert_products:
            # Some environments may not have this column yet; avoid hard-failing upserts.
            if self.db_manager.products_has_column("updated_at"):
                for p in upsert_products:
                    p["updated_at"] = now
            else:
                logger.warning("`products.updated_at` column not found; skipping updated_at writes.")

            _, failed_count, failed_products = self.db_manager.upsert_products_batch(upsert_products)
            failed_ids = {fp.get("id") for fp in failed_products if fp.get("id")}

        inserted_success = len([p for p in new_products if p.get("id") not in failed_ids])
        updated_success = len([p for p in updated_products if p.get("id") not in failed_ids])

        # 5) Stale cleanup (2 consecutive runs) using local state, keyed by product id.
        existing_rows = self.db_manager.get_existing_products_for_sync(SOURCE)
        existing_ids = {r.get("id") for r in existing_rows if r.get("id")}
        unseen_ids = list(existing_ids - seen_ids_set)

        stale_state = self._load_stale_state()

        # Seen now => reset counter.
        for pid in seen_ids_set:
            stale_state[pid] = 0

        # Not seen now => increment counter.
        for pid in unseen_ids:
            stale_state[pid] = int(stale_state.get(pid, 0) or 0) + 1

        ids_to_delete = [
            pid for pid in unseen_ids
            if int(stale_state.get(pid, 0) or 0) >= CONSECUTIVE_MISSES_THRESHOLD
        ]
        deleted = self.db_manager.delete_products_by_ids(ids_to_delete) if ids_to_delete else 0

        # Remove deleted and rows no longer present in db from local tracker.
        for pid in ids_to_delete:
            stale_state.pop(pid, None)
        for pid in list(stale_state.keys()):
            if pid not in existing_ids and pid not in seen_ids_set:
                stale_state.pop(pid, None)

        self._save_stale_state(stale_state)

        summary = (
            f"Run summary: {inserted_success} new products added; "
            f"{updated_success} products updated; "
            f"{unchanged_count} products unchanged (skipped); "
            f"{deleted} stale products deleted."
        )
        logger.info(summary)
        print(summary)

        return {"inserted": inserted_success, "updated": updated_success, "skipped": unchanged_count, "deleted": deleted}


def _norm(v: Any) -> Any:
    """Normalize for equality: None, empty string, list/tuple."""
    if v is None:
        return None
    if isinstance(v, str):
        return v.strip() or None
    if isinstance(v, (list, tuple)):
        return tuple(_norm(x) for x in v) if v else None
    return v


def _normalize_product_url(url: str) -> str:
    """Normalize product URL for comparison (avoid http/https, trailing slash mismatches)."""
    if not url:
        return url or ""
    url = url.strip().rstrip("/")
    if url.startswith("http://"):
        url = "https://" + url[7:]
    return url


def _scraped_equals_existing(existing: Dict[str, Any], scraped: Dict[str, Any]) -> bool:
    """True if comparable fields are the same (no update needed). Ignores embeddings and created_at."""
    compare_keys = [
        "title", "description", "category", "gender", "price", "size",
        "image_url", "additional_images", "metadata", "country", "second_hand", "sale", "other",
    ]
    for k in compare_keys:
        ev = _norm(existing.get(k))
        sv = _norm(scraped.get(k))
        if ev != sv:
            return False
    if existing.get("tags") is not None or scraped.get("tags") is not None:
        et = existing.get("tags")
        st = scraped.get("tags")
        if isinstance(et, list):
            et = tuple(et) if et else None
        if isinstance(st, list):
            st = tuple(st) if st else None
        if et != st:
            return False
    return True