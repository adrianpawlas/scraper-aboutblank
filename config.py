import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SOURCE = os.getenv("SOURCE", "scraper-aboutblank")
BRAND = os.getenv("BRAND", "About Blank")
BASE_URL = os.getenv("BASE_URL", "https://about---blank.com")

CATEGORY_URLS = [
    "https://about---blank.com/collections/shop-all",
]

PRODUCT_URLS = [
    "https://about---blank.com/collections/shop-all/products/oxford-script-shirt-beige-white",
    "https://about---blank.com/collections/shop-all/products/pleated-sweatpant-cotton-black-ecru",
    "https://about---blank.com/collections/shop-all/products/monogram-cap-wool-mix-brown-ecru?variant=55864033280377",
]

EMBEDDING_MODEL = "google/siglip-base-patch16-384"
EMBEDDING_DIMENSION = 768