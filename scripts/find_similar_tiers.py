#!/usr/bin/env python3
"""
Find price tiers used by other territories around a target price
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from appstore_api import AppStoreConnectAPI
from update_prices import get_price_details, decode_price_entry_id

SUBSCRIPTION_ID = "6743152682"
TARGET_PRICE = 51.63  # Target price for Panama

def main():
    print("="*100)
    print(f"Finding territories with prices around ${TARGET_PRICE:.2f} USD")
    print("="*100)
    
    api = AppStoreConnectAPI()
    
    # Get all price details
    price_details = get_price_details(api, SUBSCRIPTION_ID)
    
    # Find territories with prices close to target
    similar_prices = []
    for detail in price_details:
        price = detail.get("price", 0)
        territory = detail.get("territory", "")
        diff = abs(price - TARGET_PRICE)
        
        if diff <= 10:  # Within $10
            similar_prices.append({
                "territory": territory,
                "price": price,
                "diff": diff,
                "price_point_id": detail.get("id")
            })
    
    # Sort by difference
    similar_prices.sort(key=lambda x: x["diff"])
    
    print(f"\nFound {len(similar_prices)} territories with prices within $10 of ${TARGET_PRICE:.2f}:\n")
    print(f"{'Territory':<15} {'Price (USD)':<15} {'Difference':<15} {'Price Point ID':<60}")
    print("-" * 100)
    
    for item in similar_prices[:20]:  # Show top 20
        print(f"{item['territory']:<15} ${item['price']:<14.2f} ${item['diff']:<14.2f} {item['price_point_id'][:60]}...")
    
    if similar_prices:
        closest = similar_prices[0]
        print(f"\n✓ Closest match: {closest['territory']} at ${closest['price']:.2f} USD (diff: ${closest['diff']:.2f})")
        print(f"\n  NOTE: Price point IDs are territory-specific.")
        print(f"  You cannot use another territory's price point ID for Panama.")
        print(f"  However, this shows what price tier level would be appropriate.")
        print(f"  You may need to check if Panama has this tier available in App Store Connect.")

if __name__ == "__main__":
    main()

