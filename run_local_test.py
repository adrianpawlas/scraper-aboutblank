#!/usr/bin/env python3
"""
Local test that mocks DB so we can verify scraper + embedding logic without Supabase.
Run: python run_local_test.py
"""
import asyncio
import sys

# Inject mock database module so scraper never loads real supabase/websockets
class MockDbManager:
    def __init__(self):
        # In-memory "products" table keyed by id
        self.rows_by_id = {}
        self.last_seen_by_id = {}
        self.consecutive_misses_by_id = {}

    def _filter_select(self, row, select: str):
        cols = [c.strip() for c in (select or "").split(",") if c.strip()]
        if not cols:
            return dict(row)
        out = {}
        for c in cols:
            out[c] = row.get(c)
        return out

    def get_existing_product_urls(self, source):
        # Legacy method; not used by the new smart sync, but keep for compatibility.
        return set(
            row["product_url"]
            for row in self.rows_by_id.values()
            if row.get("source") == source and row.get("product_url")
        )

    def get_products_by_ids(self, ids, select):
        out = {}
        for _id in ids:
            row = self.rows_by_id.get(_id)
            if not row:
                continue
            out[_id] = self._filter_select(row, select)
            out[_id]["id"] = _id
        return out

    def get_existing_products_for_sync(self, source):
        out = []
        for pid, row in self.rows_by_id.items():
            if row.get("source") != source:
                continue
            r = dict(row)
            r["id"] = pid
            out.append(r)
        return out

    def upsert_products_batch(self, products_data):
        if not products_data:
            return 0, 0, []

        # Simulate merge-duplicates: overwrite by id.
        for p in products_data:
            pid = p.get("id")
            if not pid:
                continue
            self.rows_by_id[pid] = dict(p)
            if "consecutive_misses" in p:
                self.consecutive_misses_by_id[pid] = int(p.get("consecutive_misses") or 0)
            if "last_seen" in p:
                self.last_seen_by_id[pid] = p.get("last_seen")
        return len(products_data), 0, []

    def get_existing_product_ids_and_consecutive_misses(self, source):
        out = {}
        for pid, row in self.rows_by_id.items():
            if row.get("source") != source:
                continue
            out[pid] = int(self.consecutive_misses_by_id.get(pid, 0) or 0)
        return out

    def update_products_last_seen(self, product_ids):
        now = "MOCK_NOW"
        for pid in product_ids:
            if pid in self.rows_by_id:
                self.last_seen_by_id[pid] = now
                self.consecutive_misses_by_id[pid] = 0
                self.rows_by_id[pid]["last_seen"] = now
                self.rows_by_id[pid]["consecutive_misses"] = 0
        return len(product_ids)

    def set_consecutive_misses_for_ids(self, ids, misses):
        misses = int(misses)
        for pid in ids:
            self.consecutive_misses_by_id[pid] = misses
            if pid in self.rows_by_id:
                self.rows_by_id[pid]["consecutive_misses"] = misses
        return len(ids)

    def delete_stale_products(self, source, threshold=2):
        to_delete = []
        for pid, row in self.rows_by_id.items():
            if row.get("source") != source:
                continue
            misses = int(self.consecutive_misses_by_id.get(pid, 0) or 0)
            if misses >= threshold:
                to_delete.append(pid)
        for pid in to_delete:
            self.rows_by_id.pop(pid, None)
            self.last_seen_by_id.pop(pid, None)
            self.consecutive_misses_by_id.pop(pid, None)
        return len(to_delete)

class FakeDatabaseModule:
    _instance = None
    @staticmethod
    def get_db_manager():
        if FakeDatabaseModule._instance is None:
            FakeDatabaseModule._instance = MockDbManager()
        return FakeDatabaseModule._instance

sys.modules["database"] = FakeDatabaseModule()

# Now import scraper (it will use our fake database)
from scraper import AboutBlankScraper

async def main():
    print("=== Local test (mocked DB) ===\n")
    scraper = AboutBlankScraper()
    print("Discovering product URLs...")
    urls = await scraper.discover_product_urls()
    if not urls:
        print("No new URLs (or discovery failed).")
        return 1
    print(f"Found {len(urls)} product URLs. Scraping first 2...\n")
    products = await scraper.scrape_all_products(urls[:2])
    if not products:
        print("No products scraped.")
        return 1
    print("Running smart sync (embeddings generated only if needed)...\n")
    sync_result = await scraper.sync_products_to_db(products)

    for i, p in enumerate(products):
        print(f"Product {i+1}: {p.get('title')}")
        print(f"  image_url: {bool(p.get('image_url'))}")
        print(
            f"  additional_images: {p.get('additional_images', '')[:80]}..."
            if (p.get('additional_images') or '') and len(p.get('additional_images') or '') > 80
            else f"  additional_images: {p.get('additional_images')}"
        )
        print(f"  image_embedding dims: {len(p.get('image_embedding') or [])}")
        print(f"  info_embedding dims: {len(p.get('info_embedding') or [])}")

    print(f"\n[MOCK] Sync result: {sync_result}")
    print("=== Local test passed ===\n")
    return 0

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
