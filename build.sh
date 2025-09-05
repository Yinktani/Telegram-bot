#!/bin/bash
set -e
echo "Starting aggressive clean build..."

# Clear all caches
pip cache purge || true

# Upgrade pip
pip install --upgrade pip

# Uninstall telegram bot completely first
pip uninstall -y python-telegram-bot || true

# Install telegram bot with no dependencies first
pip install --no-cache-dir --no-deps python-telegram-bot==20.6

# Then install all other requirements
pip install --no-cache-dir -r requirements.txt

echo "Clean build completed successfully"
