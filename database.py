"""
Supabase import via PostgREST REST API (HTTP), no Supabase JS client.
Smart sync: batch inserts, smart upsert, stale product removal, skip unchanged.
"""
import json
import logging
import requests
import os
import time
from typing import List, Dict, Any, Set, Tuple, Optional
from datetime import datetime, timezone

from config import SUPABASE_URL, SUPABASE_KEY

logger = logging.getLogger(__name__)

UPSERT_CHUNK_SIZE = 50
MAX_RETRIES = 3
RETRY_DELAY = 1
EMBEDDING_DELAY = 0.5
CONSECUTIVE_MISSES_THRESHOLD = 2


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
        self._products_columns_cache: Optional[Set[str]] = None
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

    def get_products_columns(self) -> Set[str]:
        """Best-effort runtime discovery of `products` table columns via a sample row."""
        if self._products_columns_cache is not None:
            return self._products_columns_cache
        try:
            r = self.session.get(
                f"{self.base_url}/products",
                params={"select": "*", "limit": 1},
                timeout=20,
            )
            r.raise_for_status()
            data = r.json() or []
            if data and isinstance(data, list) and isinstance(data[0], dict):
                self._products_columns_cache = set(data[0].keys())
            else:
                self._products_columns_cache = set()
        except Exception as e:
            logger.warning(f"Could not discover products columns: {e}")
            self._products_columns_cache = set()
        return self._products_columns_cache

    def products_has_column(self, column_name: str) -> bool:
        """Check whether `products` appears to contain a given column."""
        return column_name in self.get_products_columns()

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

    def get_products_by_ids(self, ids: List[str], select: str) -> Dict[str, Dict[str, Any]]:
        """
        Fetch products by UUID ids in chunks.

        Returns a map keyed by `id` so callers can diff quickly without doing
        per-product roundtrips.
        """
        if not ids:
            return {}

        collected: Dict[str, Dict[str, Any]] = {}
        chunk = 500
        for i in range(0, len(ids), chunk):
            batch = ids[i:i + chunk]
            try:
                in_val = "in.(" + ",".join(batch) + ")"
                r = self.session.get(
                    f"{self.base_url}/products",
                    params={"select": select, "id": in_val},
                    timeout=60,
                )
                r.raise_for_status()
                data = r.json() or []
                for row in data:
                    row_id = row.get("id")
                    if row_id:
                        collected[row_id] = row
            except Exception as e:
                logger.error(f"Error fetching products by ids batch: {e}")
        return collected

    def get_existing_product_ids_and_consecutive_misses(self, source: str) -> Dict[str, int]:
        """Fetch (id -> consecutive_misses) for all rows for this source."""
        try:
            collected: Dict[str, int] = {}
            offset = 0
            limit = 1000
            select = "id,consecutive_misses"
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
                data = r.json() or []
                if not data:
                    break
                for row in data:
                    if not row.get("id"):
                        continue
                    misses = row.get("consecutive_misses")
                    # Be defensive: treat null/missing as 0
                    try:
                        collected[row["id"]] = int(misses) if misses is not None else 0
                    except Exception:
                        collected[row["id"]] = 0
                if len(data) < limit:
                    break
                offset += limit
            return collected
        except Exception as e:
            logger.error(f"Error getting existing product ids/misses: {e}")
            return {}

    def set_consecutive_misses_for_ids(self, ids: List[str], misses: int) -> int:
        """
        Set consecutive_misses to a specific integer for a list of ids.

        We use explicit setting instead of `col = col + 1` because PostgREST
        doesn't reliably support arithmetic updates via PATCH.
        """
        if not ids:
            return 0
        updated = 0
        chunk = 100
        for i in range(0, len(ids), chunk):
            batch = ids[i:i + chunk]
            try:
                in_val = "in.(" + ",".join(batch) + ")"
                r = self.session.patch(
                    f"{self.base_url}/products",
                    params={"id": in_val},
                    data=json.dumps({"consecutive_misses": int(misses)}),
                    timeout=30,
                )
                r.raise_for_status()
                updated += len(batch)
            except Exception as e:
                logger.error(f"Error setting consecutive_misses: {e}")
        return updated

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
            return True
        except Exception as e:
            logger.error(f"Error updating embedding for product {product_id}: {e}")
            return False

    def get_existing_products_with_timestamps(self, source: str) -> Dict[str, Dict[str, Any]]:
        """Fetch existing rows for source with last_seen and consecutive_misses tracking."""
        try:
            collected: Dict[str, Dict[str, Any]] = {}
            offset = 0
            limit = 500
            select = "id,product_url,title,description,category,gender,price,size,image_url,additional_images,metadata,tags,country,second_hand,sale,other,last_seen,consecutive_misses"
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
                for row in data:
                    if row.get("product_url"):
                        collected[row["product_url"]] = row
                if len(data) < limit:
                    break
                offset += limit
            return collected
        except Exception as e:
            logger.error(f"Error getting existing products with timestamps: {e}")
            return {}

    def _log_failed_products(self, failed_products: List[Dict[str, Any]], error_msg: str):
        """Log failed products to a local file."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        log_file = f"failed_products_{timestamp}.log"
        try:
            with open(log_file, "w", encoding="utf-8") as f:
                f.write(f"Failed products at {timestamp}\n")
                f.write(f"Error: {error_msg}\n")
                f.write("-" * 50 + "\n")
                for p in failed_products:
                    f.write(json.dumps(p, ensure_ascii=False) + "\n")
            logger.warning(f"Logged {len(failed_products)} failed products to {log_file}")
        except Exception as e:
            logger.error(f"Failed to write error log: {e}")

    def upsert_products_batch(
        self,
        products_data: List[Dict[str, Any]],
    ) -> Tuple[int, int, List[Dict[str, Any]]]:
        """
        Upsert products with retry logic (3 retries).
        Returns tuple of (success_count, failed_count, failed_products).
        """
        if not products_data:
            return 0, 0, []

        normalized = self._normalize_batch(products_data)
        endpoint = f"{self.base_url}/products"
        prefer = "resolution=merge-duplicates,return=minimal"
        success_count = 0
        failed_products = []

        for i in range(0, len(normalized), UPSERT_CHUNK_SIZE):
            chunk = normalized[i : i + UPSERT_CHUNK_SIZE]
            chunk_prepared = [self._prepare_row(row) for row in chunk]
            
            chunk_success = self._insert_chunk_with_retry(chunk_prepared, endpoint, prefer)
            success_count += chunk_success
            if chunk_success < len(chunk):
                failed_products.extend(chunk[chunk_success:])

        if failed_products:
            self._log_failed_products(failed_products, "Batch insert failed after 3 retries")

        logger.info(f"Batch upsert completed: {success_count}/{len(products_data)} products")
        return success_count, len(failed_products), failed_products

    def _insert_chunk_with_retry(
        self,
        chunk: List[Dict[str, Any]],
        endpoint: str,
        prefer: str,
        max_retries: int = MAX_RETRIES,
    ) -> int:
        """Insert a chunk with retry logic."""
        for attempt in range(max_retries):
            try:
                r = self.session.post(
                    endpoint,
                    headers={"Prefer": prefer},
                    data=json.dumps(chunk),
                    timeout=60,
                )
                if r.status_code in (200, 201, 204):
                    return len(chunk)
                else:
                    logger.warning(f"Attempt {attempt + 1} failed: {r.status_code} {r.text[:200]}")
                    if attempt < max_retries - 1:
                        time.sleep(RETRY_DELAY * (attempt + 1))
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} error: {e}")
                if attempt < max_retries - 1:
                    time.sleep(RETRY_DELAY * (attempt + 1))

        return 0

    def update_products_last_seen(self, product_ids: List[str]) -> int:
        """Update last_seen timestamp and reset consecutive_misses for products seen in current run."""
        if not product_ids:
            return 0
        updated = 0
        now = datetime.now(timezone.utc).isoformat()
        chunk = 100
        for i in range(0, len(product_ids), chunk):
            batch = product_ids[i:i + chunk]
            try:
                in_val = "in.(" + ",".join(batch) + ")"
                r = self.session.patch(
                    f"{self.base_url}/products",
                    params={"id": in_val},
                    data=json.dumps({"last_seen": now, "consecutive_misses": 0}),
                    timeout=30,
                )
                r.raise_for_status()
                updated += len(batch)
            except Exception as e:
                logger.error(f"Error updating last_seen: {e}")
        return updated

    def increment_consecutive_misses(self, product_ids: List[str]) -> int:
        """Increment consecutive_misses for products not seen in current run."""
        if not product_ids:
            return 0
        updated = 0
        chunk = 100
        for i in range(0, len(product_ids), chunk):
            batch = product_ids[i:i + chunk]
            try:
                in_val = "in.(" + ",".join(batch) + ")"
                r = self.session.patch(
                    f"{self.base_url}/products",
                    params={"id": in_val},
                    data=json.dumps({"consecutive_misses": "consecutive_misses+1"}),
                    timeout=30,
                )
                r.raise_for_status()
                updated += len(batch)
            except Exception as e:
                logger.error(f"Error incrementing consecutive_misses: {e}")
        return updated

    def delete_stale_products(self, source: str, threshold: int = 2) -> int:
        """Delete products that have missed >= threshold consecutive runs."""
        try:
            r = self.session.delete(
                f"{self.base_url}/products",
                params={
                    "source": f"eq.{source}",
                    "consecutive_misses": f"gte.{threshold}",
                },
                timeout=30,
            )
            r.raise_for_status()
            deleted = r.json() if r.text else []
            if isinstance(deleted, list):
                return len(deleted)
            return 0
        except Exception as e:
            logger.error(f"Error deleting stale products: {e}")
            return 0

    @staticmethod
    def _norm_value(v: Any) -> Any:
        """Normalize a value for comparison."""
        if v is None:
            return None
        if isinstance(v, str):
            return v.strip() or None
        if isinstance(v, (list, tuple)):
            return tuple(SABASEManager._norm_value(x) for x in v) if v else None
        return v

    @staticmethod
    def _compare_products(existing: Dict[str, Any], scraped: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """
        Compare scraped product against existing DB record.
        Returns (changed: bool, diff_dict: Dict of changed fields).
        """
        changed_fields: Dict[str, Any] = {}
        for field in COMPARE_FIELDS:
            ev = SABASEManager._norm_value(existing.get(field))
            sv = SABASEManager._norm_value(scraped.get(field))
            if ev != sv:
                changed_fields[field] = scraped.get(field)

        if existing.get("tags") is not None or scraped.get("tags") is not None:
            et = existing.get("tags")
            st = scraped.get("tags")
            if isinstance(et, list):
                et = tuple(et) if et else None
            if isinstance(st, list):
                st = tuple(st) if st else None
            if et != st:
                changed_fields["tags"] = scraped.get("tags")

        return len(changed_fields) > 0, changed_fields

    def upsert_products_diffing(
        self,
        products_to_upsert: List[Dict[str, Any]],
        existing_map: Dict[str, Dict[str, Any]],
    ) -> Tuple[int, int, List[Dict[str, Any]]]:
        """
        Upsert products with diffing: only send changed fields + updated_at.
        Always sends all provided fields for new products.
        Returns (success_count, failed_count, failed_products).
        """
        if not products_to_upsert:
            return 0, 0, []

        now = datetime.now(timezone.utc).isoformat()
        endpoint = f"{self.base_url}/products"
        prefer = "resolution=merge-duplicates,return=minimal"

        to_insert: List[Dict[str, Any]] = []
        to_update: List[Dict[str, Any]] = []

        for p in products_to_upsert:
            product_url = p.get("product_url")
            existing = existing_map.get(product_url)

            if existing is None:
                row = dict(p)
                row["updated_at"] = now
                to_insert.append(row)
            else:
                changed, diff = self._compare_products(existing, p)
                if changed:
                    diff["updated_at"] = now
                    diff["id"] = existing["id"]
                    to_update.append(diff)
                else:
                    pass

        all_ops = to_insert + to_update
        if not all_ops:
            return 0, 0, []

        normalized = self._normalize_batch(all_ops)
        success_count = 0
        failed_products = []

        for i in range(0, len(normalized), UPSERT_CHUNK_SIZE):
            chunk = normalized[i : i + UPSERT_CHUNK_SIZE]
            chunk_prepared = [self._prepare_row(row) for row in chunk]
            chunk_success = self._insert_chunk_with_retry(chunk_prepared, endpoint, prefer)
            success_count += chunk_success
            if chunk_success < len(chunk):
                failed_products.extend(chunk[chunk_success:])

        if failed_products:
            self._log_failed_products(failed_products, "Diffing upsert failed after 3 retries")

        return success_count, len(failed_products), failed_products


_db_manager = None


def get_db_manager() -> SupabaseManager:
    """Get or create global database manager instance."""
    global _db_manager
    if _db_manager is None:
        _db_manager = SupabaseManager()
    return _db_manager
