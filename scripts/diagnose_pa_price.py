#!/usr/bin/env python3
"""
Diagnose Panama price change issue
"""
import sys
import os
import json
import base64
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from appstore_api import AppStoreConnectAPI
from update_prices import decode_price_entry_id

SUBSCRIPTION_ID = "6743152682"
ATTEMPTED_PRICE_POINT_ID = "eyJzIjoiNjc0MzE1MjY4MiIsInQiOiJQQU4iLCJwIjoiMTAzMDAifQ"

def main():
    print("="*100)
    print("Diagnosing Panama (PA) Price Change Issue")
    print("="*100)
    
    api = AppStoreConnectAPI()
    
    # Get all prices
    endpoint = f"/subscriptions/{SUBSCRIPTION_ID}/prices"
    params = {
        "include": "subscriptionPricePoint",
        "limit": 200
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
            customer_price = attrs.get("customerPrice", "0")
            price_point_map[price_point_id] = {
                "price": customer_price,
                "full_id": price_point_id
            }
    
    # Find PA entries
    print("\n1. Current Panama (PA) Price Entry:")
    print("-" * 100)
    pa_current = None
    for price_entry in prices:
        attrs = price_entry.get("attributes", {})
        start_date = attrs.get("startDate")
        preserved = attrs.get("preserved", False)
        price_entry_id = price_entry.get("id")
        territory = decode_price_entry_id(price_entry_id)
        
        if territory == "PA" and not start_date and not preserved:
            price_point_ref = price_entry.get("relationships", {}).get("subscriptionPricePoint", {}).get("data", {})
            price_point_id = price_point_ref.get("id")
            price_info = price_point_map.get(price_point_id, {})
            
            pa_current = {
                "price_entry_id": price_entry_id,
                "price_point_id": price_point_id,
                "price": price_info.get("price", "Unknown")
            }
            
            print(f"   Price Entry ID: {price_entry_id}")
            print(f"   Price Point ID: {price_point_id}")
            print(f"   Current Price: {pa_current['price']}")
            break
    
    # Compare with attempted price point
    print("\n2. Attempted Price Point:")
    print("-" * 100)
    print(f"   Price Point ID: {ATTEMPTED_PRICE_POINT_ID}")
    attempted_price = price_point_map.get(ATTEMPTED_PRICE_POINT_ID, {}).get("price", "Unknown")
    print(f"   Price: {attempted_price}")
    
    # Analysis
    print("\n3. Analysis:")
    print("-" * 100)
    if pa_current:
        if pa_current["price_point_id"] == ATTEMPTED_PRICE_POINT_ID:
            print("   ⚠️  PROBLEM IDENTIFIED:")
            print("   The price point ID you tried to schedule is ALREADY the current price point!")
            print("   Apple cannot schedule a price change to the same price that's already active.")
            print("   This is why the API created a current price entry (startDate: null) instead of a scheduled one.")
            print("\n   SOLUTION:")
            print("   You need to use a DIFFERENT price point ID that represents a different price tier.")
        else:
            print(f"   ✓ Different price points:")
            print(f"     Current: {pa_current['price_point_id'][:50]}...")
            print(f"     Attempted: {ATTEMPTED_PRICE_POINT_ID[:50]}...")
            print(f"   This should work, but there might be another issue (conflict, invalid tier, etc.)")
    
    # Check for any scheduled PA entries
    print("\n4. Scheduled Price Entries for PA:")
    print("-" * 100)
    scheduled_pa = []
    for price_entry in prices:
        attrs = price_entry.get("attributes", {})
        start_date = attrs.get("startDate")
        price_entry_id = price_entry.get("id")
        territory = decode_price_entry_id(price_entry_id)
        
        if territory == "PA" and start_date:
            price_point_ref = price_entry.get("relationships", {}).get("subscriptionPricePoint", {}).get("data", {})
            price_point_id = price_point_ref.get("id")
            price_info = price_point_map.get(price_point_id, {})
            
            scheduled_pa.append({
                "start_date": start_date,
                "price_point_id": price_point_id,
                "price": price_info.get("price", "Unknown")
            })
    
    if scheduled_pa:
        for entry in scheduled_pa:
            print(f"   • Scheduled for {entry['start_date']}:")
            print(f"     Price Point ID: {entry['price_point_id'][:50]}...")
            print(f"     Price: {entry['price']}")
    else:
        print("   No scheduled price changes found for PA")
    
    print("\n" + "="*100)

if __name__ == "__main__":
    main()

