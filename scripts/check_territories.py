#!/usr/bin/env python3
"""Check what territories are available"""
import json
import base64
from appstore_api import AppStoreConnectAPI

def decode_price_entry_id(price_entry_id):
    try:
        padded = price_entry_id + '=='
        decoded = base64.urlsafe_b64decode(padded)
        data = json.loads(decoded)
        return data.get('c', '')
    except:
        return None

api = AppStoreConnectAPI()
subscription_id = "6743152682"

endpoint = f"/subscriptions/{subscription_id}/prices"
params = {
    "include": "subscriptionPricePoint",
    "limit": 50
}

data = api._make_request(endpoint, params=params)
prices = data.get("data", [])

territories = []
for price_entry in prices:
    attrs = price_entry.get("attributes", {})
    start_date = attrs.get("startDate")
    preserved = attrs.get("preserved", False)
    
    if start_date is None and not preserved:
        price_entry_id = price_entry.get("id")
        territory = decode_price_entry_id(price_entry_id)
        if territory:
            territories.append(territory)

territories = sorted(set(territories))
print(f"Found {len(territories)} territories:")
print("\n".join(territories))

# Check for Albania variations
print("\nLooking for Albania...")
for t in territories:
    if 'AL' in t or 'albania' in t.lower():
        print(f"Found: {t}")

