# About Blank Fashion Scraper

A comprehensive scraper for About Blank fashion store that extracts product data, generates image embeddings, and stores everything in Supabase.

## Features

- ✅ **Product Discovery**: Automatically discovers all product URLs from the shop-all collection
- ✅ **Data Extraction**: Extracts title, description, price, category, gender, sizes, and images
- ✅ **Image Embeddings**: Generates 768-dimensional embeddings using Google SigLIP model
- ✅ **Supabase Integration**: Stores all data in your Supabase database
- ✅ **Duplicate Prevention**: Skips products already in the database
- ✅ **Rate Limiting**: Respectful scraping with configurable delays
- ✅ **Error Handling**: Robust error handling and logging

## Data Mapping

| Field | Value |
|-------|-------|
| `source` | "scraper" |
| `brand` | "About Blank" |
| `country` | "US" |
| `currency` | "USD" |
| `gender` | "man" (except accessories = null) |
| `category` | "clothes", "accessories", or null |
| `size` | Comma-separated available sizes |
| `second_hand` | false |

## Requirements

- Python 3.8+
- Supabase account with products table
- HuggingFace account (optional, for model access)

## Installation

1. Clone/install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure your Supabase credentials in `config.py`

## Usage

### Full Scrape (All Products)
```bash
python main.py
```

### Test Run (5 Products)
```bash
python main_test.py
```

### Debug Tools
```bash
# Check site structure
python check_site.py

# Debug database
python check_db.py

# Debug product data
python debug_product.py

# Test all components
python test_scraper.py
```

## Configuration

Edit `config.py` to customize:

- **Supabase Connection**: Update URL and API key
- **Rate Limiting**: Adjust `REQUESTS_PER_SECOND` and `MAX_CONCURRENT_REQUESTS`
- **Categories**: Modify category mapping in `CATEGORY_MAPPING`
- **Embedding Model**: Change `EMBEDDING_MODEL` if needed

## Database Schema

The scraper expects a `products` table with these fields:

```sql
create table public.products (
  id text not null,
  source text null,
  product_url text null,
  affiliate_url text null,
  image_url text not null,
  brand text null,
  title text not null,
  description text null,
  category text null,
  gender text null,
  price double precision null,
  currency text null,
  search_tsv tsvector null,
  created_at timestamp with time zone null default now(),
  metadata text null,
  size text null,
  second_hand boolean null default false,
  embedding public.vector null,
  country text null,
  compressed_image_url text null,
  tags text[] null,
  search_vector tsvector null,
  constraint products_pkey primary key (id),
  constraint products_source_product_url_key unique (source, product_url)
)
```

## Performance

- **Discovery**: ~1-2 seconds per page
- **Product Scraping**: ~2-3 seconds per product
- **Embedding Generation**: ~6-8 seconds per image (CPU)
- **Database Insert**: ~0.2 seconds per product

**Total time for 422 products**: ~45-60 minutes

## Logging

Logs are saved to:
- `scraper.log` - Main application logs
- Console output for progress tracking

## Troubleshooting

### Common Issues

1. **Database Connection Failed**
   - Check Supabase URL and API key
   - Ensure service role key is set: `SUPABASE_SERVICE_ROLE_KEY`

2. **Embedding Generation Failed**
   - Check internet connection for image downloads
   - Verify SigLIP model access

3. **No Products Found**
   - Site structure may have changed
   - Check `check_site.py` for current structure

4. **Rate Limiting**
   - Adjust `REQUESTS_PER_SECOND` in config
   - Add delays between requests

### Debug Commands

```bash
# Test database connection
python -c "from database import get_db_manager; print('DB OK' if get_db_manager() else 'DB FAIL')"

# Test embedding generation
python -c "from embedding import get_embedder; print('Embedding OK' if get_embedder() else 'Embedding FAIL')"
```

## Architecture

```
main.py
├── scraper.py (Product discovery & scraping)
├── embedding.py (SigLIP image embeddings)
├── database.py (Supabase integration)
├── utils.py (Helper functions)
└── config.py (Configuration)
```

## Security

- Uses rotating user agents
- Implements rate limiting
- Respects robots.txt (implied)
- No aggressive scraping patterns

## License

This scraper is for educational/research purposes. Respect the website's terms of service and implement appropriate delays between requests.