import os
from dotenv import load_dotenv

load_dotenv(override=False)

# Supabase Configuration (PostgREST API)
# Set SUPABASE_URL and SUPABASE_KEY in .env (or SUPABASE_ANON_KEY as fallback)
SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_ANON_KEY") or ""
if not SUPABASE_URL or not SUPABASE_KEY:
    pass  # Allow missing at import; database module will raise on first use

# Scraper Configuration
BASE_URL = "https://about---blank.com"
SHOP_ALL_URL = f"{BASE_URL}/collections/shop-all"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
}

# Data Mapping Configuration
BRAND = "About Blank"
SOURCE = "scraper"
COUNTRY = "US"
CURRENCY = "USD"

# Category mapping (from collection names to our categories)
CATEGORY_MAPPING = {
    'clothes': ['t-shirts', 'hoodies & sweats', 'knitwear', 'outerwear', 'shirts', 'vests'],
    'accessories': ['accessories', 'headwear'],
    'footwear': []  # No footwear category visible
}

# Rate limiting
REQUESTS_PER_SECOND = 2  # Conservative rate limiting
MAX_CONCURRENT_REQUESTS = 5

# Image processing
EMBEDDING_MODEL = "google/siglip-base-patch16-384"
EMBEDDING_DIM = 768