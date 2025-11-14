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
    
    # Check specifically for PA
    print(f"\n{'='*100}")
    print("Checking for Panama (PA) specifically...")
    pa_found = False
    for price_entry in prices:
        attrs = price_entry.get("attributes", {})
        start_date = attrs.get("startDate")
        price_entry_id = price_entry.get("id")
        territory = decode_price_entry_id(price_entry_id)
        
        if territory == "PA":
            if start_date:
                print(f"  ✓ Found scheduled price change for PA on {start_date}")
                pa_found = True
            else:
                print(f"  ✓ Found current price for PA (no start date = current price)")
                pa_found = True
    
    if not pa_found:
        print("  ⚠ Panama (PA) not found in price list")
    
    print(f"\n{'='*100}")

if __name__ == "__main__":
    main()

