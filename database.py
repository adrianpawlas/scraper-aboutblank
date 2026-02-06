from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_ANON_KEY
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class SupabaseManager:
    def __init__(self):
        # Try with service role key format
        self.client: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
        logger.info("Connected to Supabase")

        # Test the connection
        try:
            result = self.client.table('products').select('id').limit(1).execute()
            logger.info("Database connection test successful")
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            raise

    def insert_product(self, product_data: Dict[str, Any]) -> bool:
        """Insert a single product into the database"""
        try:
            # Remove None values and convert to proper format
            clean_data = {k: v for k, v in product_data.items() if v is not None}

            # Embeddings are stored as lists; DB expects vector type (Supabase/PostgREST accept list)
            for key in ('image_embedding', 'info_embedding'):
                if key in clean_data and isinstance(clean_data[key], list):
                    clean_data[key] = clean_data[key]

            logger.info(f"Attempting to insert product: {clean_data.get('title', 'Unknown')}")
            logger.debug(f"Product data keys: {list(clean_data.keys())}")

            result = self.client.table('products').insert(clean_data).execute()

            if result.data:
                logger.info(f"Inserted product: {product_data.get('title', 'Unknown')}")
                return True
            else:
                logger.error(f"Failed to insert product: {product_data.get('title', 'Unknown')} - No data in result")
                logger.error(f"Result: {result}")
                return False

        except Exception as e:
            logger.error(f"Error inserting product {product_data.get('title', 'Unknown')}: {e}")
            logger.error(f"Product data: {product_data}")
            return False

    def insert_products_batch(self, products_data: List[Dict[str, Any]]) -> int:
        """Insert multiple products in batch"""
        success_count = 0

        for product_data in products_data:
            if self.insert_product(product_data):
                success_count += 1

        logger.info(f"Batch insert completed: {success_count}/{len(products_data)} products inserted")
        return success_count

    def check_product_exists(self, source: str, product_url: str) -> bool:
        """Check if product already exists"""
        try:
            result = self.client.table('products').select('id').eq('source', source).eq('product_url', product_url).execute()
            return len(result.data) > 0
        except Exception as e:
            logger.error(f"Error checking product existence: {e}")
            return False

    def get_existing_product_urls(self, source: str) -> set:
        """Get all existing product URLs for a source"""
        try:
            result = self.client.table('products').select('product_url').eq('source', source).execute()
            return {row['product_url'] for row in result.data if row['product_url']}
        except Exception as e:
            logger.error(f"Error getting existing product URLs: {e}")
            return set()

    def update_product_embedding(self, product_id: str, embedding: List[float]) -> bool:
        """Update product image_embedding"""
        try:
            result = self.client.table('products').update({'image_embedding': embedding}).eq('id', product_id).execute()
            return len(result.data) > 0
        except Exception as e:
            logger.error(f"Error updating embedding for product {product_id}: {e}")
            return False

# Global instance
_db_manager = None

def get_db_manager():
    """Get or create global database manager instance"""
    global _db_manager
    if _db_manager is None:
        _db_manager = SupabaseManager()
    return _db_manager