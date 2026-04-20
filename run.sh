#!/bin/bash

set -e

echo "Installing dependencies..."
pip install -r requirements.txt

echo "Installing Playwright browsers..."
playwright install chromium

echo "Running scraper..."
python main.py