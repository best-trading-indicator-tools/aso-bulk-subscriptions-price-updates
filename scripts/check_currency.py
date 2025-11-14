#!/usr/bin/env python3
"""Check what currency the prices are in"""
import json
import base64
from appstore_api import AppStoreConnectAPI

api = AppStoreConnectAPI()
subscription_id = "6743152682"

# Get prices with included data
endpoint = f"/subscriptions/{subscription_id}/prices"
params = {
    "include": "subscriptionPricePoint",
    "limit": 20
}

data = api._make_request(endpoint, params=params)
prices = data.get("data", [])
included = data.get("included", [])

# Build price point map
price_point_map = {}
for item in included:
    if item.get("type") == "subscriptionPricePoints":
        price_point_id = item.get("id")
        attrs = item.get("attributes", {})
        customer_price_str = attrs.get("customerPrice", "0")
        
        # Check if there's currency info
        print(f"Price Point ID: {price_point_id[:50]}...")
        print(f"  Customer Price: {customer_price_str}")
        print(f"  Attributes keys: {list(attrs.keys())}")
        print()

def decode_price_entry_id(price_entry_id):
    try:
        padded = price_entry_id + '=='
        decoded = base64.urlsafe_b64decode(padded)
        data = json.loads(decoded)
        return data.get('c', '')
    except:
        return None

# Check a few territories
print("\nTerritories and prices:")
for price_entry in prices[:10]:
    attrs = price_entry.get("attributes", {})
    start_date = attrs.get("startDate")
    preserved = attrs.get("preserved", False)
    
    if start_date is None and not preserved:
        price_entry_id = price_entry.get("id")
        territory = decode_price_entry_id(price_entry_id)
        
        price_point_ref = price_entry.get("relationships", {}).get("subscriptionPricePoint", {}).get("data", {})
        price_point_id = price_point_ref.get("id")
        
        if price_point_id in price_point_map:
            price = price_point_map[price_point_id].get("price", 0)
            print(f"{territory}: {price}")

