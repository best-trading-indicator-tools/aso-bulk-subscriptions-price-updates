#!/usr/bin/env python3
"""
Check scheduled price changes for a subscription
"""
import sys
import os
# Add parent directory to path to import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from appstore_api import AppStoreConnectAPI
from update_prices import get_price_details, decode_price_entry_id
import json
from datetime import datetime

SUBSCRIPTION_ID = "6743152682"  # Annual Subscription

def main():
    print("="*100)
    print(f"Checking scheduled price changes for Annual Subscription")
    print("="*100)
    
    api = AppStoreConnectAPI()
    
    # Get all prices (including scheduled ones)
    print("\nFetching all prices (including scheduled changes)...")
    endpoint = f"/subscriptions/{SUBSCRIPTION_ID}/prices"
    params = {
        "include": "subscriptionPricePoint",
        "limit": 200
    }
    
    data = api._make_request(endpoint, params=params)
    prices = data.get("data", [])
    
    # Group by start date
    scheduled_changes = {}
    current_prices = []
    
    for price_entry in prices:
        attrs = price_entry.get("attributes", {})
        start_date = attrs.get("startDate")
        preserved = attrs.get("preserved", False)
        price_entry_id = price_entry.get("id")
        territory = decode_price_entry_id(price_entry_id)
        
        if start_date:
            # Scheduled price change
            if start_date not in scheduled_changes:
                scheduled_changes[start_date] = []
            scheduled_changes[start_date].append(territory)
        elif not preserved:
            # Current price
            current_prices.append(territory)
    
    print(f"\nCurrent prices: {len(current_prices)} territories")
    print(f"Scheduled price changes: {len(scheduled_changes)} dates\n")
    
    # Show scheduled changes
    if scheduled_changes:
        print("Scheduled Price Changes:")
        print("-" * 80)
        for start_date in sorted(scheduled_changes.keys()):
            territories = scheduled_changes[start_date]
            print(f"  {start_date}: {len(territories)} Countries or Regions")
            # Show if PA is in this date
            if "PA" in territories:
                print(f"    ✓ Panama (PA) is scheduled for this date!")
            if len(territories) <= 10:
                print(f"    Territories: {', '.join(sorted(territories))}")
    else:
        print("No scheduled price changes found.")
    
    # Check specifically for PA with full details
    print(f"\n{'='*100}")
    print("Checking for Panama (PA) specifically...")
    pa_entries = []
    
    # Build price point map for reference
    included = data.get("included", [])
    price_point_map = {}
    for item in included:
        if item.get("type") == "subscriptionPricePoints":
            price_point_id = item.get("id")
            attrs = item.get("attributes", {})
            customer_price = attrs.get("customerPrice", "0")
            price_point_map[price_point_id] = customer_price
    
    for price_entry in prices:
        attrs = price_entry.get("attributes", {})
        start_date = attrs.get("startDate")
        preserved = attrs.get("preserved", False)
        price_entry_id = price_entry.get("id")
        territory = decode_price_entry_id(price_entry_id)
        
        if territory == "PA":
            price_point_ref = price_entry.get("relationships", {}).get("subscriptionPricePoint", {}).get("data", {})
            price_point_id = price_point_ref.get("id")
            price = price_point_map.get(price_point_id, "Unknown")
            
            pa_entries.append({
                "price_entry_id": price_entry_id,
                "price_point_id": price_point_id,
                "price": price,
                "start_date": start_date,
                "preserved": preserved
            })
    
    if pa_entries:
        print(f"\n  Found {len(pa_entries)} price entry/entries for Panama (PA):")
        print("  " + "-" * 96)
        for entry in pa_entries:
            status = "SCHEDULED" if entry["start_date"] else "CURRENT"
            preserved_str = " (PRESERVED)" if entry["preserved"] else ""
            print(f"  • Status: {status}{preserved_str}")
            print(f"    Price Entry ID: {entry['price_entry_id']}")
            print(f"    Price Point ID: {entry['price_point_id'][:60]}...")
            print(f"    Price: {entry['price']}")
            if entry["start_date"]:
                print(f"    Start Date: {entry['start_date']}")
            print()
    else:
        print("  ⚠ Panama (PA) not found in price list")
    
    # Check if 2025-11-15 was supposed to be scheduled
    print(f"\n  Checking for scheduled changes on 2025-11-15...")
    if "2025-11-15" in scheduled_changes:
        territories_1115 = scheduled_changes["2025-11-15"]
        if "PA" in territories_1115:
            print(f"  ✓ Panama (PA) IS scheduled for 2025-11-15")
        else:
            print(f"  ✗ Panama (PA) is NOT scheduled for 2025-11-15")
            print(f"    Territories scheduled for 2025-11-15: {', '.join(sorted(territories_1115))}")
    else:
        print(f"  ✗ No price changes scheduled for 2025-11-15")
        print(f"    This suggests the price change was NOT created successfully")
    
    print(f"\n{'='*100}")

if __name__ == "__main__":
    main()

