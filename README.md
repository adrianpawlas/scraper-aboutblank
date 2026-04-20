# About Blank Scraper

A web scraper for the About Blank fashion store that extracts product data, generates embeddings, and imports to Supabase.

## Features

- Scrapes all products from About Blank store
- Extracts: title, price, categories, sizes, images
- Generates 768-dim embeddings using Google/SigLIP-base-patch16-384
- Imports to Supabase database
- Automated scheduling (Monday/Friday at midnight)

## Setup

1. Clone the repo:
```bash
git clone https://github.com/adrianpawlas/scraper-aboutblank.git
cd scraper-aboutblank
```

2. Copy environment file:
```bash
cp .env.example .env
# Edit .env with your Supabase credentials
```

3. Install dependencies:
```bash
pip install -r requirements.txt
playwright install chromium
```

## Usage

### Manual Run
```bash
python main.py
```

### Test Mode (3 products)
```bash
python main.py --test
```

### Test with custom count
```bash
python main.py --test --count 10
```

## Automation

### macOS (launchd)
```bash
# Install the launchd agent
cp com.adrianpawlas.scraper-aboutblank.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.adrianpawlas.scraper-aboutblank.plist

# To run manually:
./run_automation.sh
```

### GitHub Actions
The `.github/workflows/scrape.yml` workflow runs automatically on:
- Monday at midnight
- Friday at midnight
- Manual trigger via GitHub UI

To use GitHub Actions, add these secrets in your GitHub repo settings:
- `SUPABASE_URL`
- `SUPABASE_KEY`

## Project Structure

```
.
├── config.py              # Configuration
├── scraper.py            # Web scraper
├── embedding_service.py   # SigLIP embeddings
├── database.py           # Supabase import
├── main.py              # Entry point
├── run_automation.sh    # Automation script
├── .env                 # Environment (not tracked)
├── .env.example         # Environment template
└── .github/workflows/   # GitHub Actions
```

## Supabase Table Schema

The scraper expects a `products` table with these columns:
- `id` (text, primary key)
- `source` (text)
- `product_url` (text)
- `image_url` (text)
- `brand` (text)
- `title` (text)
- `category` (text)
- `price` (text)
- `image_embedding` (vector, 768)
- `info_embedding` (vector, 768)
- ... and more
