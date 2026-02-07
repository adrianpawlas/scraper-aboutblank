# How We Import to Supabase (PostgREST)

This scraper imports products into Supabase using the **PostgREST REST API** over HTTP (no Supabase JS client). Same pattern as the reference guide.

---

## 1. Environment variables

Set in `.env` or the environment:

- **`SUPABASE_URL`** – Project URL, no trailing slash (e.g. `https://xxxx.supabase.co`)
- **`SUPABASE_KEY`** – Project API key (anon or service role with access to the `products` table)

`.env` is loaded with `load_dotenv(override=False)` in `config.py`. Fallback: `SUPABASE_ANON_KEY` if `SUPABASE_KEY` is not set.

---

## 2. How we call Supabase (HTTP)

- **Base URL:** `{SUPABASE_URL}/rest/v1`
- **Products:** `POST {SUPABASE_URL}/rest/v1/products`

**Headers (set in `database.py`):**

- `apikey`: SUPABASE_KEY  
- `Authorization`: `Bearer {SUPABASE_KEY}`  
- `Content-Type`: `application/json`

---

## 3. Upsert

We use:

- **`Prefer: resolution=merge-duplicates,return=minimal`** – on conflict (primary key `id`), update the row; minimal response.
- **Stable `id`** – `id = sha256(f"{source}:{product_url}")` so the same product always maps to the same row (upsert instead of duplicate inserts).

---

## 4. Same keys in every object

PostgREST requires **all objects in one request to have the same set of keys**. We normalize each batch:

- Collect all keys that appear in any product in the batch.
- For each product, output `{key: product.get(key) for key in all_keys}` (missing keys become `None`).

See `_normalize_batch()` in `database.py`.

---

## 5. Batching and retries

- Products are sent in **chunks of 100** (`UPSERT_CHUNK_SIZE` in `database.py`).
- If a chunk returns non‑2xx, we **retry that chunk one row at a time** and log failures so one bad row doesn’t block the rest.

---

## 6. Where it’s implemented

- **Config:** `config.py` – `SUPABASE_URL`, `SUPABASE_KEY` from env.
- **DB layer:** `database.py` – `SupabaseManager`: session, `get_existing_product_urls`, `insert_products_batch` (normalize + chunked upsert), `update_product_embedding`.
- **Stable id:** `utils.generate_product_id(source, product_url)` used in `scraper.py` for each product’s `id`.
- **Usage:** `scraper.py` builds product dicts (with `id`, `source`, `product_url`, …) and calls `db_manager.insert_products_batch(products)`.
