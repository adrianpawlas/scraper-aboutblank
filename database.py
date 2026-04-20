import supabase
from config import SUPABASE_URL, SUPABASE_KEY, SOURCE
from datetime import datetime


class DatabaseService:
    def __init__(self):
        self.client = supabase.create_client(SUPABASE_URL, SUPABASE_KEY)
        print("DatabaseService initialized")

    def generate_product_id(self, product_url: str) -> str:
        url_part = product_url.split("/products/")[-1].split("?")[0] if "/products/" in product_url else product_url
        return f"{SOURCE}_{url_part}"

    def format_price(self, price_str: str) -> str:
        return price_str.strip() if price_str else None

    def format_additional_images(self, images: list) -> str:
        if not images:
            return None
        return " , ".join(images)

    def format_categories(self, categories: list) -> str:
        if not categories:
            return None
        return ", ".join(categories)

    def prepare_product_data(self, product: dict) -> dict:
        categories = product.get("categories", [])
        additional_images = product.get("additional_images", [])
        metadata = product.get("metadata", {})

        price_parts = []
        for currency, amount in metadata.get("prices", {}).items():
            if amount:
                price_parts.append(f"{amount}{currency}")

        return {
            "id": self.generate_product_id(product["product_url"]),
            "source": SOURCE,
            "product_url": product["product_url"],
            "affiliate_url": product.get("affiliate_url"),
            "image_url": product.get("image_url"),
            "brand": product.get("brand", "About Blank"),
            "title": product.get("title"),
            "description": product.get("description"),
            "category": self.format_categories(categories),
            "gender": product.get("gender"),
            "created_at": datetime.utcnow().isoformat(),
            "metadata": str(metadata) if metadata else None,
            "size": product.get("size"),
            "second_hand": False,
            "image_embedding": product.get("image_embedding"),
            "country": metadata.get("country"),
            "compressed_image_url": product.get("compressed_image_url"),
            "tags": product.get("tags"),
            "price": ", ".join(price_parts) if price_parts else None,
            "sale": ", ".join(price_parts) if price_parts and metadata.get("on_sale") else None,
            "additional_images": self.format_additional_images(additional_images),
            "info_embedding": product.get("info_embedding"),
        }

    def insert_products(self, products: list) -> dict:
        results = {"inserted": 0, "failed": 0, "errors": []}

        for product in products:
            try:
                product_data = self.prepare_product_data(product)
                result = self.client.table("products").upsert(product_data, on_conflict="id").execute()
                if result.data:
                    results["inserted"] += 1
                else:
                    results["failed"] += 1
                    results["errors"].append(f"No data returned for {product.get('title', 'unknown')}")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append(str(e))
                print(f"Failed to insert product {product.get('title', 'unknown')}: {e}")

        return results

    def batch_insert(self, products: list, batch_size: int = 50) -> dict:
        total_results = {"inserted": 0, "failed": 0, "errors": []}

        for i in range(0, len(products), batch_size):
            batch = products[i:i + batch_size]
            batch_results = self.insert_products(batch)
            total_results["inserted"] += batch_results["inserted"]
            total_results["failed"] += batch_results["failed"]
            total_results["errors"].extend(batch_results["errors"])
            print(f"Batch {i // batch_size + 1}: Inserted {batch_results['inserted']}, Failed {batch_results['failed']}")

        return total_results