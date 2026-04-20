import re
import json
import asyncio
import time
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
from config import BASE_URL, CATEGORY_URLS, PRODUCT_URLS
from embedding_service import EmbeddingService


class ProductScraper:
    def __init__(self):
        self.base_url = BASE_URL
        self.embedding_service = EmbeddingService()
        self.scrolled_urls = set()
        self.product_links = []

    async def scroll_page(self, page, max_scrolls: int = 50):
        last_count = 0
        scroll_attempts = 0

        for _ in range(max_scrolls):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(2)

            current_count = await page.evaluate("window.innerHeight")

            if current_count == last_count:
                scroll_attempts += 1
                if scroll_attempts >= 3:
                    break
            else:
                scroll_attempts = 0

            last_count = current_count

        return await page.evaluate("""() => {
            const links = [];
            document.querySelectorAll('a[href*="/products/"]').forEach(a => {
                const href = a.href;
                if (!links.includes(href)) links.push(href);
            });
            return links;
        }""")

    async def scrape_collection_page(self, url: str) -> list[str]:
        product_urls = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            try:
                await page.goto(url, timeout=60000)
                await page.wait_for_timeout(5000)

                links = await self.scroll_page(page)
                product_urls = [link.split('?')[0].split('#')[0] for link in links if '/products/' in link]

                await browser.close()
            except Exception as e:
                print(f"Error scraping {url}: {e}")
                await browser.close()

        return list(set(product_urls))

    async def extract_product_info(self, page, url: str) -> dict:
        info = {
            "product_url": url,
            "title": None,
            "description": None,
            "image_url": None,
            "additional_images": [],
            "categories": [],
            "gender": None,
            "metadata": {},
            "brand": "About Blank",
        }

        try:
            page_title = await page.title()
            if page_title:
                info["title"] = page_title.split("|")[0].split("-")[0].strip()
        except:
            pass

        try:
            title_result = await page.evaluate("""() => {
                const titleEl = document.querySelector('h1.product-title') ||
                              document.querySelector('h1[itemprop="name"]') ||
                              document.querySelector('.product-info h1') ||
                              document.querySelector('.product__title') ||
                              document.querySelector('h1');
                if (titleEl) {
                    let text = titleEl.textContent.trim();
                    text = text.replace(/\\s+/g, ' ').trim();
                    return text;
                }
                return null;
            }""")
            if title_result:
                info["title"] = title_result
        except:
            pass

        try:
            desc_result = await page.evaluate("""() => {
                const descEl = document.querySelector('[itemprop="description"]') ||
                               document.querySelector('.product-description') ||
                               document.querySelector('.rte') ||
                               document.querySelector('.product__description') ||
                               document.querySelector('.description');
                return descEl ? descEl.textContent.trim() : null;
            }""")
            if desc_result:
                info["description"] = desc_result
        except:
            pass

        try:
            img_result = await page.evaluate("""() => {
                const imgs = Array.from(document.querySelectorAll('img'));
                
                // First: find images with alt text that matches product name in title
                const titleEl = document.querySelector('h1');
                const productName = titleEl ? titleEl.textContent.trim().toLowerCase() : '';
                
                // Find images with alt text matching product
                for (let img of imgs) {
                    const alt = (img.alt || '').toLowerCase();
                    const src = img.src || img.getAttribute('src');
                    if (src && alt && (src.includes('products') || src.includes('files')) && 
                       img.naturalWidth > 0 && alt.length > 3 &&
                       (alt.includes(productName.split(' ')[0]) || productName.split(' ').some(w => w.length > 3 && alt.includes(w)))) {
                        return src.split('?')[0];
                    }
                }
                
                // Second: filter out common/shared images (Mobile, Header, Footer, etc)
                const badPatterns = ['Mobile', 'Header', 'Footer', 'Logo', 'Banner', 'Icon', 'avatar', 'Logo', 'hero', 'Hero', 'Etsy', 'shopify', 'Cart'];
                const goodImgs = imgs.filter(img => {
                    const src = img.src || img.getAttribute('src');
                    if (!src || !(src.includes('products') || src.includes('files'))) return false;
                    if (img.naturalWidth <= 0) return false;
                    const srcLower = src.toLowerCase();
                    for (let p of badPatterns) {
                        if (srcLower.includes(p.toLowerCase())) return false;
                    }
                    return true;
                });
                
                // Get unique product images (filter duplicates from responsive srcset)
                const unique = [];
                const seen = new Set();
                for (let img of goodImgs) {
                    let src = (img.src || img.getAttribute('src')).split('?')[0];
                    // Skip tiny thumbnail versions
                    if (src.includes('_thumbs') || src.includes('thumb')) continue;
                    if (!seen.has(src)) {
                        seen.add(src);
                        unique.push(src);
                    }
                }
                
                return unique.length > 0 ? unique[0] : null;
            }""")
            if img_result:
                info["image_url"] = img_result
        except:
            pass

        try:
            additional_imgs = await page.evaluate("""() => {
                const badPatterns = ['Mobile', 'Header', 'Footer', 'Logo', 'Banner', 'Icon', 'avatar', 'hero', 'Hero', 'Etsy', 'shopify', 'Cart'];
                const imgs = Array.from(document.querySelectorAll('img'));
                const goodImgs = imgs.filter(img => {
                    const src = img.src || img.getAttribute('src');
                    if (!src || !(src.includes('products') || src.includes('files'))) return false;
                    if (img.naturalWidth <= 0) return false;
                    const srcLower = src.toLowerCase();
                    for (let p of badPatterns) {
                        if (srcLower.includes(p.toLowerCase())) return false;
                    }
                    return true;
                });
                
                const unique = [];
                const seen = new Set();
                for (let img of goodImgs) {
                    let src = (img.src || img.getAttribute('src')).split('?')[0];
                    if (src.includes('_thumbs') || src.includes('thumb')) continue;
                    if (!seen.has(src)) {
                        seen.add(src);
                        unique.push(src);
                    }
                }
                return unique;
            }""")
            if additional_imgs and len(additional_imgs) > 1:
                info["additional_images"] = additional_imgs[1:]
        except:
            pass

        try:
            page_url = page.url
            collection = ''
            if '/collections/' in page_url:
                collection_part = page_url.split('/collections/')[1].split('/products/')[0]
                collection = collection_part.replace('-', ' ')
            category_result = await page.evaluate("""() => {
                const categories = [];
                const categoryMap = {
                    'headwear': 'Headwear', 'hats': 'Headwear', 'caps': 'Headwear',
                    'vests': 'Vests', 'waistcoats': 'Vests',
                    't-shirts': 'T-Shirts', 'tees': 'T-Shirts', 'tshirts': 'T-Shirts',
                    'shirts': 'Shirts', 'button-up': 'Shirts', 'oxford': 'Shirts',
                    'hoodies': 'Hoodies', 'hoodies & sweats': 'Hoodies', 'hoodie': 'Hoodies',
                    'sweats': 'Sweats', 'sweatpants': 'Sweatpants', 'sweatshirts': 'Sweatshirts',
                    'knitwear': 'Knitwear', 'knits': 'Knitwear', 'jumpers': 'Knitwear',
                    'outerwear': 'Outerwear', 'jackets': 'Outerwear', 'coats': 'Outerwear',
                    'shorts': 'Shorts',
                    'legwear': 'Legwear', 'trousers': 'Legwear', 'pants': 'Legwear',
                    'denim': 'Denim', 'jeans': 'Denim',
                    'accessories': 'Accessories', 'bags': 'Accessories', 'belts': 'Accessories',
                    'core': 'Core', 'shop all': 'Shop All', 'new in': 'New In'
                };
                const text = document.body.innerText.toLowerCase();
                for (let [key, value] of Object.entries(categoryMap)) {
                    if (text.includes(key) && !categories.includes(value)) {
                        categories.push(value);
                    }
                }
                return categories;
            }""")
            if category_result and len(category_result) > 0:
                info["categories"] = category_result
            elif collection:
                info["categories"] = [collection]
        except:
            pass

        try:
            gender_keywords = ['men', 'women', 'unisex', 'male', 'female', 'genderless', 'her', 'him']
            page_text = await page.evaluate("() => document.body.innerText.toLowerCase()")
            for kw in gender_keywords:
                if kw in page_text:
                    if kw in ['unisex', 'genderless']:
                        info["gender"] = "unisex"
                    elif kw in ['women', 'her', 'female']:
                        if not info["gender"] or info["gender"] != "unisex":
                            info["gender"] = "women"
                    elif kw in ['men', 'him', 'male']:
                        if not info["gender"] or info["gender"] != "unisex":
                            info["gender"] = "men"
        except:
            pass

        try:
            price_result = await page.evaluate("""() => {
                const prices = {};
                const text = document.body.innerText;
                const currencyRegex = /([£€$¥]) ?([0-9]+[.,]?[0-9]*)/g;
                let match;
                while ((match = currencyRegex.exec(text)) !== null) {
                    const currency = match[1] === '£' ? 'GBP' : match[1] === '€' ? 'EUR' : match[1] === '$' ? 'USD' : match[1] === '¥' ? 'JPY' : 'OTHER';
                    prices[currency] = match[2];
                    if (!prices.main) prices.main = match[0].trim();
                }
                const priceSelectors = ['[itemprop="price"]', '.product-price', '.price', '.money', '.product__price', '.price-item'];
                for (let sel of priceSelectors) {
                    const el = document.querySelector(sel);
                    if (el && !prices.main) {
                        prices.main = el.textContent.trim();
                    }
                }
                const compareEl = document.querySelector('[data-compare-at-price], .compare-at-price, .was-price, .price--compare');
                if (compareEl) {
                    prices.compare = compareEl.textContent.trim();
                }
                return prices;
            }""")
            if price_result:
                if price_result.get("main") or price_result.get("GBP") or price_result.get("EUR") or price_result.get("USD"):
                    price_dict = {}
                    for curr in ["GBP", "EUR", "USD", "JPY"]:
                        if price_result.get(curr):
                            price_dict[curr] = price_result[curr]
                    if not price_dict and price_result.get("main"):
                        price_dict["USD"] = price_result["main"]
                    info["metadata"]["prices"] = price_dict
                    info["metadata"]["original_price"] = price_result.get("main")
                if price_result.get("compare"):
                    info["metadata"]["on_sale"] = True
                    info["metadata"]["sale_price"] = price_result["compare"]
        except:
            pass

        try:
            size_result = await page.evaluate("""() => {
                const sizes = [];
                const commonSizes = ['XXXS', 'XXS', 'XS', 'S', 'M', 'L', 'XL', 'XXL', 'XXXL', '4XL', '5XL', '6XL', 
                                    '28', '29', '30', '31', '32', '33', '34', '35', '36', '38', '40', '42', '44',
                                    'One Size'];
                const sizeButtons = document.querySelectorAll('button, input[type="radio"], label, .swatch');
                for (let el of sizeButtons) {
                    const value = el.value || el.textContent || el.getAttribute('data-value');
                    if (value && commonSizes.includes(value.trim().toUpperCase())) {
                        if (!sizes.includes(value.trim().toUpperCase())) sizes.push(value.trim().toUpperCase());
                    }
                }
                if (sizes.length === 0) {
                    const text = document.body.innerText.toUpperCase();
                    for (let size of commonSizes) {
                        if (text.includes(size.toUpperCase()) && !sizes.includes(size)) {
                            sizes.push(size);
                        }
                    }
                }
                return sizes;
            }""")
            if size_result and len(size_result) > 0:
                info["metadata"]["sizes"] = size_result
        except:
            pass

        try:
            color_result = await page.evaluate("""() => {
                const colors = [];
                const colorSelectors = '.color-swatch, .swatch, .product-form__input input[type="radio"], select[name="color"] option';
                document.querySelectorAll(colorSelectors).forEach(el => {
                    const value = el.value || el.getAttribute('data-color') || el.textContent;
                    if (value && value.trim() && !colors.includes(value.trim())) colors.push(value.trim());
                });
                return colors;
            }""")
            if color_result:
                info["metadata"]["colors"] = color_result
        except:
            pass

        return info

    async def scrape_product(self, url: str, generate_embeddings: bool = True) -> dict:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            try:
                await page.goto(url, timeout=60000)
                await page.wait_for_timeout(5000)

                product_info = await self.extract_product_info(page, url)

                if product_info.get("image_url") and generate_embeddings:
                    try:
                        time.sleep(0.5)
                        product_info["image_embedding"] = self.embedding_service.get_image_embedding(
                            product_info["image_url"]
                        )
                    except Exception as e:
                        print(f"Error generating embedding for {url}: {e}")
                        product_info["image_embedding"] = None

                    metadata = product_info.get("metadata", {})
                    sizes = ", ".join(metadata.get("sizes", []))
                    colors = ", ".join(metadata.get("colors", []))
                    prices = ", ".join(metadata.get("prices", {}).values())
                    
                    info_text = f"{product_info.get('title', '')} {product_info.get('description', '')} {', '.join(product_info.get('categories', []))} {product_info.get('gender', '')} {sizes} {colors} {prices}"
                    try:
                        time.sleep(0.5)
                        product_info["info_embedding"] = self.embedding_service.get_text_embedding(info_text)
                    except Exception as e:
                        print(f"Error generating info embedding for {url}: {e}")
                        product_info["info_embedding"] = None

                await browser.close()
                return product_info

            except Exception as e:
                print(f"Error scraping product {url}: {e}")
                await browser.close()
                return None

    async def scrape_all_products(self, urls: list[str], generate_embeddings: bool = True) -> list[dict]:
        all_products = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)

            for i, url in enumerate(urls):
                page = await browser.new_page()
                try:
                    await page.goto(url, timeout=60000)
                    await page.wait_for_timeout(5000)

                    product_info = await self.extract_product_info(page, url)

                    if product_info.get("image_url") and generate_embeddings:
                        try:
                            time.sleep(0.5)
                            product_info["image_embedding"] = self.embedding_service.get_image_embedding(
                                product_info["image_url"]
                            )
                        except Exception as e:
                            print(f"Error generating image embedding for {url}: {e}")
                            product_info["image_embedding"] = None

                        metadata = product_info.get("metadata", {})
                        sizes = ", ".join(metadata.get("sizes", []))
                        colors = ", ".join(metadata.get("colors", []))
                        prices = ", ".join(metadata.get("prices", {}).values())
                        
                        info_text = f"{product_info.get('title', '')} {product_info.get('description', '')} {', '.join(product_info.get('categories', []))} {product_info.get('gender', '')} {sizes} {colors} {prices}"
                        try:
                            time.sleep(0.5)
                            product_info["info_embedding"] = self.embedding_service.get_text_embedding(info_text)
                        except Exception as e:
                            print(f"Error generating info embedding for {url}: {e}")
                            product_info["info_embedding"] = None

                    all_products.append(product_info)
                    print(f"Scraped: {product_info.get('title', url)}")

                except Exception as e:
                    print(f"Error scraping product {url}: {e}")

                await page.close()

            await browser.close()

        return all_products

    async def run(self) -> list[dict]:
        all_product_urls = set()

        print("Fetching product URLs from collection pages...")
        for category_url in CATEGORY_URLS:
            print(f"Scraping collection: {category_url}")
            urls = await self.scrape_collection_page(category_url)
            all_product_urls.update(urls)
            print(f"Found {len(urls)} product URLs")

        print(f"Total unique product URLs: {len(all_product_urls)}")

        print("Scraping individual products...")
        products = await self.scrape_all_products(list(all_product_urls))

        return products