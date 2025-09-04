#!/usr/bin/env python3
"""
Diagnostic script to isolate Google Sheets connection issues
with retry-capable setup function.
"""

import os
import json
import time
from dotenv import load_dotenv
from google.auth.transport.requests import Request

# -------------------------------------------------------------------
# Google Sheets setup with retry logic
# -------------------------------------------------------------------
def setup_google_sheets():
    """Setup Google Sheets client for both production and development"""
    import gspread
    from google.oauth2.service_account import Credentials

    for attempt in range(3):  # Try 3 times
        try:
            if 'GOOGLE_CREDENTIALS' in os.environ:
                print("Using production Google credentials from environment variable")
                creds_json = json.loads(os.environ['GOOGLE_CREDENTIALS'])
                credentials = Credentials.from_service_account_info(creds_json)
                gc = gspread.authorize(credentials)
            else:
                print("Using local credentials.json file")
                gc = gspread.service_account(filename='credentials.json')
            
            return gc
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt < 2:  # Don't wait on last attempt
                print("Retrying in 5 seconds...")
                time.sleep(5)
            else:
                print("All attempts failed")
                raise

# -------------------------------------------------------------------
# Diagnostics
# -------------------------------------------------------------------
def diagnose_credentials():
    """Check credentials.json file"""
    print("🔍 Diagnosing credentials.json...")
    
    if not os.path.exists('credentials.json'):
        print("❌ credentials.json not found")
        return False
    
    try:
        with open('credentials.json', 'r') as f:
            creds = json.load(f)
        
        required_keys = ['type', 'project_id', 'private_key', 'client_email']
        missing_keys = [key for key in required_keys if key not in creds]
        
        if missing_keys:
            print(f"❌ Missing keys in credentials.json: {missing_keys}")
            return False
        
        print(f"✅ Service account email: {creds['client_email']}")
        print(f"✅ Project ID: {creds['project_id']}")
        print(f"✅ Credentials file structure looks good")
        
        return True
        
    except json.JSONDecodeError:
        print("❌ credentials.json is not valid JSON")
        return False
    except Exception as e:
        print(f"❌ Error reading credentials.json: {e}")
        return False

def test_basic_auth():
    """Test basic Google authentication"""
    try:
        from google.oauth2.service_account import Credentials
        
        print("\n🔍 Testing basic Google authentication...")
        
        creds = Credentials.from_service_account_file(
            'credentials.json',
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        
        print("✅ Service account credentials loaded successfully")
        
        # Check if credentials are expired or invalid
        if creds.expired:
            print("⚠️  Credentials are expired, attempting refresh...")
            creds.refresh(Request())
        
        return True
        
    except Exception as e:
        print(f"❌ Authentication failed: {e}")
        return False

def test_gspread_import():
    """Test if gspread can be imported and initialized"""
    try:
        print("\n🔍 Testing gspread library...")
        import gspread
        print("✅ gspread imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Failed to import gspread: {e}")
        print("   Try: pip install gspread")
        return False

def test_spreadsheet_access():
    """Test actual spreadsheet access"""
    try:
        load_dotenv()
        import gspread
        from google.oauth2.service_account import Credentials
        
        print("\n🔍 Testing spreadsheet access...")
        
        # Use the setup function here
        gc = setup_google_sheets()
        
        spreadsheet_id = os.getenv('GOOGLE_SPREADSHEET_ID')
        
        if not spreadsheet_id:
            print("❌ GOOGLE_SPREADSHEET_ID not set in environment")
            return False
        
        print(f"✅ Attempting to access spreadsheet: {spreadsheet_id}")
        
        # Try to open the spreadsheet
        sheet = gc.open_by_key(spreadsheet_id).sheet1
        print("✅ Successfully opened spreadsheet")
        
        # Try to read first row
        headers = sheet.row_values(1)
        print(f"✅ Successfully read headers: {headers}")
        
        return True
        
    except gspread.exceptions.APIError as e:
        print(f"❌ Google Sheets API error: {e}")
        if "PERMISSION_DENIED" in str(e):
            print("   → Make sure you shared the spreadsheet with your service account email")
        elif "NOT_FOUND" in str(e):
            print("   → Check if your GOOGLE_SPREADSHEET_ID is correct")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

# -------------------------------------------------------------------
# Main runner
# -------------------------------------------------------------------
def main():
    """Run all diagnostics"""
    print("🧪 Google Sheets Connection Diagnostics\n")
    
    tests = [
        ("Credentials file check", diagnose_credentials),
        ("gspread library", test_gspread_import),
        ("Basic authentication", test_basic_auth),
        ("Spreadsheet access", test_spreadsheet_access)
    ]
    
    passed = 0
    for test_name, test_func in tests:
        print(f"\n{'='*50}")
        print(f"Running: {test_name}")
        print('='*50)
        
        if test_func():
            passed += 1
        else:
            print(f"\n❌ {test_name} failed. Fix this before continuing.")
            break
    
    print(f"\n{'='*50}")
    print(f"Diagnostics complete: {passed}/{len(tests)} passed")
    
    if passed == len(tests):
        print("🎉 All Google Sheets tests passed!")
        print("Your credentials and spreadsheet access are working correctly.")
    else:
        print("❌ Please fix the issues above and try again.")

if __name__ == "__main__":
    main()
