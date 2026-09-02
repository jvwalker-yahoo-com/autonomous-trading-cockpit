"""
eToro Connection Verification Script (Read-Only).
Safely validates API keys and connection status without placing real trades.
Usage:
    python -m src.services.etoro.test_connection
"""
import sys
import json
from .client import EToroClient

def main():
    print("==================================================")
    print("   eToro API Connection Verification (Read-Only)  ")
    print("==================================================")
    
    client = EToroClient()
    print(f"Base URL: {client.base_url}")
    print(f"API Key Configured: {'[YES]' if client.api_key else '[NO - Not set]'}")
    print(f"User Key Configured: {'[YES]' if client.user_key else '[NO - Not set]'}")
    print("--------------------------------------------------")

    if not client.is_configured():
        print("NOTICE: eToro credentials not fully configured in environment.")
        print("To connect to your real eToro account, set:")
        print("  ETORO_API_KEY=<your_api_key>")
        print("  ETORO_USER_KEY=<your_user_key>")
        print("  ETORO_BASE_URL=https://api.etoro.com")
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
        print("\nSUCCESS: Connected and authenticated with eToro!")
        return 0
    else:
        print(f"\nSTATUS: {res.get('message')}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
