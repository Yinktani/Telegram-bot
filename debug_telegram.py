import sys
import os

print("=== PYTHON TELEGRAM BOT DEBUG ===")
print(f"Python version: {sys.version}")
print(f"Python path: {sys.path}")

# Check if telegram module exists
try:
    import telegram
    print(f"✅ telegram module found: {telegram.__version__}")
    print(f"telegram location: {telegram.__file__}")
except ImportError as e:
    print(f"❌ telegram import failed: {e}")

# Check telegram.ext
try:
    from telegram.ext import Application
    print("✅ telegram.ext.Application imported successfully")
except ImportError as e:
    print(f"❌ telegram.ext.Application import failed: {e}")

# Check for conflicting installations
try:
    import pkg_resources
    telegram_packages = [pkg for pkg in pkg_resources.working_set if 'telegram' in pkg.project_name.lower()]
    print(f"Telegram packages found: {telegram_packages}")
except:
    print("Could not check package versions")

# Test Application creation
try:
    from telegram.ext import Application
    app = Application.builder().token("dummy_token").build()
    print("✅ Application.builder() works!")
except Exception as e:
    print(f"❌ Application.builder() failed: {e}")
    print(f"Error type: {type(e).__name__}")

print("=== END DEBUG ===")
