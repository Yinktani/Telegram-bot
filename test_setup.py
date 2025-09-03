#!/usr/bin/env python3
"""
Test script for SGI Bot Phase 1
Run this before starting the main bot to ensure everything works
"""

import os
import sys
from dotenv import load_dotenv

def test_environment():
    """Test if all required environment variables are set"""
    load_dotenv()
    
    required_vars = ['TELEGRAM_BOT_TOKEN', 'GOOGLE_SPREADSHEET_ID', 'ADMIN_USER_IDS']
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ Missing environment variables: {', '.join(missing_vars)}")
        return False
    
    # Validate admin user IDs format
    admin_ids = os.getenv('ADMIN_USER_IDS')
    try:
        [int(uid.strip()) for uid in admin_ids.split(',')]
        print(f"✅ Admin user IDs format valid: {admin_ids}")
    except ValueError:
        print("❌ ADMIN_USER_IDS must be comma-separated numbers (e.g., 123456789,987654321)")
        return False
    
    print("✅ All required environment variables are set")
    return True

def test_google_sheets():
    """Test Google Sheets connection"""
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        
        # Test credentials file exists for local development
        if not os.path.exists('credentials.json'):
            print("❌ credentials.json file not found")
            print("   Make sure you've downloaded your service account key file")
            return False
        
        print("✅ credentials.json file found")
        
        # Test connection
        creds = Credentials.from_service_account_file(
            'credentials.json',
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        
        gc = gspread.authorize(creds)
        spreadsheet_id = os.getenv('GOOGLE_SPREADSHEET_ID')
        sheet = gc.open_by_key(spreadsheet_id).sheet1
        
        print("✅ Google Sheets connection successful")
        
        # Test reading headers
        headers = sheet.row_values(1)
        expected_headers = ['Name', 'User_ID', 'Group', 'Current_Points', 'Strikes', 'Status', 'Daily1', 'Daily2', 'Daily3', 'Weekly1', 'Weekly2']
        
        if headers != expected_headers:
            print("❌ Sheet headers don't match expected format")
            print(f"   Expected: {expected_headers}")
            print(f"   Found: {headers}")
            print("   Please update your spreadsheet headers")
            return False
        
        print("✅ Sheet headers are correct")
        
        records = sheet.get_all_records()
        print(f"✅ Found {len(records)} existing records")
        
        return True
        
    except Exception as e:
        print(f"❌ Google Sheets connection failed: {e}")
        return False

def test_telegram_bot():
    """Test Telegram bot token"""
    try:
        from telegram import Bot
        import asyncio
        
        bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        bot = Bot(token=bot_token)
        
        # Test bot info
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        bot_info = loop.run_until_complete(bot.get_me())
        
        print(f"✅ Telegram bot connection successful")
        print(f"   Bot name: {bot_info.first_name}")
        print(f"   Bot username: @{bot_info.username}")
        
        return True
        
    except Exception as e:
        print(f"❌ Telegram bot connection failed: {e}")
        return False

def test_admin_setup():
    """Test admin configuration"""
    try:
        admin_ids = os.getenv('ADMIN_USER_IDS')
        admin_list = [int(uid.strip()) for uid in admin_ids.split(',')]
        
        print(f"✅ Configured {len(admin_list)} admin(s)")
        print("   To get your Telegram User ID, send /start to @userinfobot")
        print(f"   Current admin IDs: {admin_list}")
        
        return True
        
    except Exception as e:
        print(f"❌ Admin setup error: {e}")
        return False

def main():
    """Run all tests"""
    print("🧪 Testing SGI Bot Phase 1 Setup...\n")
    
    tests_passed = 0
    total_tests = 4
    
    # Test 1: Environment variables
    print("1. Testing environment variables...")
    if test_environment():
        tests_passed += 1
    print()
    
    # Test 2: Google Sheets
    print("2. Testing Google Sheets connection...")
    if test_google_sheets():
        tests_passed += 1
    print()
    
    # Test 3: Telegram Bot
    print("3. Testing Telegram bot connection...")
    if test_telegram_bot():
        tests_passed += 1
    print()
    
    # Test 4: Admin Setup
    print("4. Testing admin configuration...")
    if test_admin_setup():
        tests_passed += 1
    print()
    
    # Results
    print("=" * 50)
    print(f"Tests passed: {tests_passed}/{total_tests}")
    
    if tests_passed == total_tests:
        print("🎉 All tests passed! Your SGI Bot is ready to run.")
        print("\nNext steps:")
        print("1. Run: python sgi_bot_phase1.py")
        print("2. Add bot to your Telegram groups")
        print("3. Test with /start command")
        print("4. Register users with /register senior or /register junior")
    else:
        print("❌ Some tests failed. Please fix the issues above.")
        sys.exit(1)

if __name__ == "__main__":
    main()