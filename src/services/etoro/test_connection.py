"""
eToro Connection Verification Script (Read-Only).
Safely validates API keys and connection status without placing real trades.
Usage:
    python -m src.services.etoro.test_connection
"""
import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv
from .client import EToroClient

# Load environment variables
load_dotenv()

def main():
    print("==================================================")
    print("   eToro API Connection Verification (Read-Only)  ")
    print("==================================================")
    
    # Check environment and local state file
    saved_api_key = os.getenv("ETORO_API_KEY", "").strip()
    saved_user_key = os.getenv("ETORO_USER_KEY", "").strip()
    saved_base_url = os.getenv("ETORO_BASE_URL", "https://public-api.etoro.com").strip()

    state_file = Path("data/trading_state.json")
    if state_file.exists():
        try:
            with open(state_file, "r") as f:
                st = json.load(f).get("settings", {})
                saved_api_key = saved_api_key or st.get("etoro_api_key", "").strip()
                saved_user_key = saved_user_key or st.get("etoro_user_key", "").strip()
                if st.get("etoro_base_url"):
                    saved_base_url = st.get("etoro_base_url").strip()
        except Exception:
            pass

    client = EToroClient(api_key=saved_api_key, user_key=saved_user_key, base_url=saved_base_url)
    print(f"Base URL: {client.base_url}")
    print(f"API Key Configured: {'[YES]' if client.api_key else '[NO - Not set]'}")
    print(f"User Key Configured: {'[YES]' if client.user_key else '[NO - Not set]'}")
    print("--------------------------------------------------")

    if not client.is_configured():
        print("NOTICE: eToro credentials not configured in environment or local state.")
        print("To connect, configure ETORO_API_KEY and ETORO_USER_KEY in .env or Settings.")
        print("--------------------------------------------------")
        print("Testing mock/headers generation...")
        headers = client._build_headers()
        print("Sample injected headers:")
        for k, v in headers.items():
            if k in ("x-api-key", "x-user-key") and v:
                print(f"  {k}: {v[:4]}****{v[-4:]}")
            else:
                print(f"  {k}: {v}")
        return 0

    print("Attempting authentication handshake with eToro API...")
    res = client.test_connection()
    print("Result:")
    print(json.dumps(res, indent=2))
    
    if res.get("connected"):
        print("\nSUCCESS (HTTP 200): Connected and authenticated with eToro!")
        return 0
    else:
        print(f"\nSTATUS ({res.get('status_code', 'ERR')}): {res.get('message')}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
