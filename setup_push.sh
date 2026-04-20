#!/bin/bash
# Setup script to push to GitHub
# Run this once: brew install gh && gh auth login

set -e

echo "Installing gh CLI..."
brew install gh

echo "Logging in to GitHub..."
gh auth login

echo "Adding remote..."
git remote add origin https://github.com/adrianpawlas/scraper-aboutblank.git 2>/dev/null || true

echo "Pushing to GitHub..."
git push -u origin main