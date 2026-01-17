import os
from dotenv import load_dotenv

load_dotenv()

# Supabase Configuration
SUPABASE_URL = "https://yqawmzggcgpeyaaynrjk.supabase.co"
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InlxYXdtemdnY2dwZXlhYXlucmprIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1NTAxMDkyNiwiZXhwIjoyMDcwNTg2OTI2fQ.XtLpxausFriraFJeX27ZzsdQsFv3uQKXBBggoz6P4D4"

# Set service role key for full access
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = SUPABASE_ANON_KEY

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