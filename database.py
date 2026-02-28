"""
Supabase import via PostgREST REST API (HTTP), no Supabase JS client.
Smart sync: use resolution=ignore-duplicates (insert new, leave existing unchanged), then delete stale.
"""
import json
import logging
import requests
from typing import List, Dict, Any, Set

from config import SUPABASE_URL, SUPABASE_KEY

logger = logging.getLogger(__name__)

# Chunk size for batch upsert (avoid timeouts / large payloads)
UPSERT_CHUNK_SIZE = 100


class SupabaseManager:
    """PostgREST client for products table: HTTP session, upsert, normalized keys."""

    def __init__(self):
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise RuntimeError("Set SUPABASE_URL and SUPABASE_KEY (or SUPABASE_ANON_KEY) in .env")
        self.base_url = f"{SUPABASE_URL}/rest/v1"
        self.session = requests.Session()
        self.session.headers.update({
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        })
        logger.info("Connected to Supabase (PostgREST)")

        # Test connection
        try:
            r = self.session.get(
                f"{self.base_url}/products",
                params={"select": "id", "limit": 1},
                timeout=15,
            )
            r.raise_for_status()
            logger.info("Database connection test successful")
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            raise

    def get_existing_product_urls(self, source: str) -> Set[str]:
        """Fetch all product_url values for the given source."""
        try:
            collected: List[str] = []
            offset = 0
            limit = 1000
            while True:
                r = self.session.get(
                    f"{self.base_url}/products",
                    params={
                        "select": "product_url",
                        "source": f"eq.{source}",
                        "limit": limit,
                        "offset": offset,
                    },
                    timeout=30,
                )
                r.raise_for_status()
                data = r.json()
                if not data:
                    break
                for row in data:
                    if row.get("product_url"):
                        collected.append(row["product_url"])
                if len(data) < limit:
                    break
                offset += limit
            return set(collected)
        except Exception as e:
            logger.error(f"Error getting existing product URLs: {e}")
            return set()

    # Columns we compare to decide if a row is "same" as scraped (no update needed)
    SYNC_COMPARE_COLUMNS = (
        "id", "source", "product_url", "image_url", "additional_images", "brand", "title",
        "description", "category", "gender", "price", "size", "metadata", "tags",
        "country", "second_hand", "sale", "other",
    )

    def get_existing_products_for_sync(self, source: str) -> List[Dict[str, Any]]:
        """Fetch existing rows for source for sync: id, product_url, and comparable columns."""
        try:
            collected: List[Dict[str, Any]] = []
            offset = 0
            limit = 500
            select = "id,product_url,title,description,category,gender,price,size,image_url,additional_images,metadata,tags,country,second_hand,sale,other"
            while True:
                r = self.session.get(
                    f"{self.base_url}/products",
                    params={
                        "select": select,
                        "source": f"eq.{source}",
                        "limit": limit,
                        "offset": offset,
                    },
                    timeout=30,
                )
                r.raise_for_status()
                data = r.json()
                if not data:
                    break
                collected.extend(data)
                if len(data) < limit:
                    break
                offset += limit
            return collected
        except Exception as e:
            logger.error(f"Error getting existing products for sync: {e}")
            return []

    def delete_products_by_ids(self, ids: List[str]) -> int:
        """Delete rows by id. PostgREST: DELETE with id=in.(id1,id2,...). Batched."""
        if not ids:
            return 0
        deleted = 0
        chunk = 100
        for i in range(0, len(ids), chunk):
            batch = ids[i : i + chunk]
            try:
                # PostgREST: id=in.(id1,id2,...) — UUIDs in parens, comma-separated
                in_val = "in.(" + ",".join(batch) + ")"
                r = self.session.delete(
                    f"{self.base_url}/products",
                    params={"id": in_val},
                    timeout=30,
                )
                r.raise_for_status()
                deleted += len(batch)
            except Exception as e:
                logger.error(f"Error deleting batch: {e}")
        return deleted

    def _normalize_batch(self, products_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Ensure every object has the same set of keys (PostgREST requirement). Use None for missing."""
        all_keys: set = set()
        for p in products_data:
            all_keys.update(p.keys())
        return [{k: p.get(k) for k in all_keys} for p in products_data]

    def _prepare_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare one row for JSON (e.g. leave lists as-is for vector columns)."""
        out = {}
        for k, v in row.items():
            if v is None:
                out[k] = None
            elif isinstance(v, list):
                out[k] = v
            else:
                out[k] = v
        return out

    def insert_products_batch(
        self,
        products_data: List[Dict[str, Any]],
        *,
        ignore_duplicates: bool = True,
    ) -> int:
        """
        Insert products in chunks. By default uses resolution=ignore-duplicates:
        new rows are inserted, existing rows (by unique constraint) are left unchanged.
        Set ignore_duplicates=False to use merge-duplicates (update on conflict).
        """
        if not products_data:
            return 0

        normalized = self._normalize_batch(products_data)
        endpoint = f"{self.base_url}/products"
        prefer = (
            "resolution=ignore-duplicates,return=minimal"
            if ignore_duplicates
            else "resolution=merge-duplicates,return=minimal"
        )
        success_count = 0

        for i in range(0, len(normalized), UPSERT_CHUNK_SIZE):
            chunk = normalized[i : i + UPSERT_CHUNK_SIZE]
            chunk_prepared = [self._prepare_row(row) for row in chunk]

            try:
                r = self.session.post(
                    endpoint,
                    headers={"Prefer": prefer},
                    data=json.dumps(chunk_prepared),
                    timeout=60,
                )
                if r.status_code in (200, 201, 204):
                    success_count += len(chunk)
                    logger.debug(f"Upserted chunk {i // UPSERT_CHUNK_SIZE + 1}: {len(chunk)} rows")
                else:
                    # Retry chunk one row at a time
                    logger.warning(f"Chunk failed {r.status_code} {r.text[:200]}; retrying row-by-row")
                    for row in chunk_prepared:
                        rr = self.session.post(
                            endpoint,
                            headers={"Prefer": prefer},
                            data=json.dumps([row]),
                            timeout=30,
                        )
                        if rr.status_code in (200, 201, 204):
                            success_count += 1
                        else:
                            logger.error(f"Row failed: {rr.status_code} {r.text[:200]} title={row.get('title')}")
            except Exception as e:
                logger.error(f"Chunk request error: {e}; retrying row-by-row")
                for row in chunk_prepared:
                    try:
                        rr = self.session.post(
                            endpoint,
                            headers={"Prefer": prefer},
                            data=json.dumps([row]),
                            timeout=30,
                        )
                        if rr.status_code in (200, 201, 204):
                            success_count += 1
                        else:
                            logger.error(f"Row failed: {rr.status_code} title={row.get('title')}")
                    except Exception as e2:
                        logger.error(f"Row error: {e2} title={row.get('title')}")

        logger.info(f"Batch upsert completed: {success_count}/{len(products_data)} products")
        return success_count

    def check_product_exists(self, source: str, product_url: str) -> bool:
        """Check if a product with this source and product_url exists."""
        try:
            r = self.session.get(
                f"{self.base_url}/products",
                params={
                    "select": "id",
                    "source": f"eq.{source}",
                    "product_url": f"eq.{product_url}",
                    "limit": 1,
                },
                timeout=15,
            )
            r.raise_for_status()
            return len(r.json() or []) > 0
        except Exception as e:
            logger.error(f"Error checking product existence: {e}")
            return False

    def update_product_embedding(self, product_id: str, embedding: List[float]) -> bool:
        """Update image_embedding for one product by id."""
        try:
            r = self.session.patch(
                f"{self.base_url}/products",
                params={"id": f"eq.{product_id}"},
                data=json.dumps({"image_embedding": embedding}),
                timeout=30,
            )
            r.raise_for_status()
            # return=minimal not set, so we get response; with PATCH we can check count
            return True
        except Exception as e:
            logger.error(f"Error updating embedding for product {product_id}: {e}")
            return False


_db_manager = None


def get_db_manager() -> SupabaseManager:
    """Get or create global database manager instance."""
    global _db_manager
    if _db_manager is None:
        _db_manager = SupabaseManager()
    return _db_manager
