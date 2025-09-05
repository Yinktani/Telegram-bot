#!/bin/bash
set -e
echo "=== COMPLETE ENVIRONMENT RESET ==="

# Remove ALL telegram-related packages
pip uninstall -y python-telegram-bot telegram python-telegram-bot-raw telepot pytelegrambotapi || true

# Clear all caches
pip cache purge
rm -rf /tmp/pip-*
rm -rf ~/.cache/pip

# Remove any local __pycache__
find . -name "*.pyc" -delete
find . -name "__pycache__" -delete

# Upgrade pip to latest
pip install --upgrade pip setuptools wheel

echo "Installing python-telegram-bot fresh..."

# Install with verbose output to see what happens
pip install --no-cache-dir --verbose python-telegram-bot==20.6

# Verify installation
python -c "import telegram; print('SUCCESS:', telegram.__version__)"

# Install other requirements
pip install --no-cache-dir gspread==5.12.0
pip install --no-cache-dir google-auth==2.23.4
pip install --no-cache-dir google-auth-oauthlib==1.1.0
pip install --no-cache-dir python-dotenv==1.0.0

echo "=== INSTALLATION COMPLETE ==="
