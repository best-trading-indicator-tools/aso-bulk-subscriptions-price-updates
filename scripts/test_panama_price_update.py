#!/usr/bin/env python3
"""
Test script to update Panama price with correct price point ID
"""
import sys
import os
import json
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from appstore_api import AppStoreConnectAPI
from price_calculator import PriceCalculator
from exchange_rates import ExchangeRates
from update_prices import get_price_details, get_usa_base_price, find_nearest_price_tier, decode_price_entry_id

SUBSCRIPTION_ID = "6743152682"  # Annual Subscription
SUBSCRIPTION_NAME = "Annual Subscription"
TERRITORY = "PA"  # Panama

def main():
    print("="*100)
    print(f"Testing Panama (PA) Price Update")
    print("="*100)
    
    api = AppStoreConnectAPI()
    calculator = PriceCalculator()
    exchange_rates = ExchangeRates()
    
    # Step 1: Get current prices
    print("\n1. Fetching current prices...")
    price_details = get_price_details(api, SUBSCRIPTION_ID)
    
    if not price_details:
        print("  ❌ No prices found.")
        return
    
    print(f"  ✓ Found {len(price_details)} price points")
    
    # Step 2: Get USA base price
    usa_price = get_usa_base_price(price_details)
    if usa_price is None or usa_price == 0:
        print("  ❌ Could not find USA base price.")
        return
    
    print(f"  ✓ USA base price: ${usa_price:.2f} USD")
    
    # Step 3: Get Panama current price
    panama_detail = None
    for detail in price_details:
        if detail.get("territory") == TERRITORY:
            panama_detail = detail
            break
    
    if not panama_detail:
        print(f"  ❌ No current price found for {TERRITORY}.")
        return
    
    current_price_pa = panama_detail.get("price", 0)
    current_price_point_id = panama_detail.get("id")
    print(f"  ✓ Panama current price: ${current_price_pa:.2f} USD")
    print(f"  ✓ Current price point ID: {current_price_point_id[:60]}...")
    
    # Step 4: Get Big Mac Index ratio
    print(f"\n2. Fetching Big Mac Index ratio for {TERRITORY}...")
    all_ratios = calculator.index.get_all_ratios()
    ratio = all_ratios.get(TERRITORY)
    
    if ratio is None:
        ratio = calculator.index.get_country_ratio(TERRITORY)
    
    if ratio is None:
        print(f"  ❌ No Big Mac Index data for {TERRITORY}.")
        return
    
    print(f"  ✓ Big Mac Index ratio: {ratio:.4f}")
    
    # Step 5: Calculate new USD price
    new_price_usd = usa_price * ratio
    print(f"\n3. Calculating new price...")
    print(f"  Base price (USD): ${usa_price:.2f}")
    print(f"  Ratio: {ratio:.4f}")
    print(f"  New price (USD): ${new_price_usd:.2f}")
    print(f"  Current price (USD): ${current_price_pa:.2f}")
    print(f"  Change: ${new_price_usd - current_price_pa:+.2f} USD")
    
    # Step 6: Get exchange rates
    print(f"\n4. Fetching exchange rates...")
    if not exchange_rates.fetch_current_rates():
        print("  ⚠ Warning: Could not fetch exchange rates.")
    
    # Step 7: Find all available tiers for Panama
    print(f"\n5. Finding available price tiers for {TERRITORY}...")
    
    # Get all price entries for Panama to see available tiers
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
            try:
                price_point_map[price_point_id] = float(customer_price)
            except:
                pass
    
    # Find all tiers used for Panama
    panama_tiers = []
    for price_entry in prices:
        attrs = price_entry.get("attributes", {})
        start_date = attrs.get("startDate")
        preserved = attrs.get("preserved", False)
        price_entry_id = price_entry.get("id")
        territory = decode_price_entry_id(price_entry_id)
        
        if territory == TERRITORY and not preserved:
            price_point_ref = price_entry.get("relationships", {}).get("subscriptionPricePoint", {}).get("data", {})
            tier_id = price_point_ref.get("id")
            tier_price = price_point_map.get(tier_id, 0)
            
            if tier_id not in [t["tier_id"] for t in panama_tiers]:
                panama_tiers.append({
                    "tier_id": tier_id,
                    "price": tier_price,
                    "is_current": tier_id == current_price_point_id,
                    "start_date": start_date
                })
    
    # Sort by price
    panama_tiers.sort(key=lambda x: x["price"])
    
    print(f"  Found {len(panama_tiers)} available tier(s) for {TERRITORY}:")
    for tier in panama_tiers:
        status = "CURRENT" if tier["is_current"] else "AVAILABLE"
        date_str = f" (scheduled: {tier['start_date']})" if tier["start_date"] else ""
        print(f"    • ${tier['price']:.2f} USD - {status}{date_str}")
        print(f"      Tier ID: {tier['tier_id'][:50]}...")
    
    # Step 8: Find all price points for Panama territory
    print(f"\n6. Finding all available price points for {TERRITORY}...")
    
    # Query all price points and filter for Panama
    all_panama_price_points = []
    cursor = None
    
    while True:
        endpoint = "/subscriptionPricePoints"
        params = {"limit": 200}
        if cursor:
            params["cursor"] = cursor
        
        try:
            data = api._make_request(endpoint, params=params)
            price_points = data.get("data", [])
            
            for pp in price_points:
                pp_id = pp.get("id")
                # Price point IDs are base64 encoded. For Panama, they contain "PA" in the encoded data
                # We can try to decode or check if it's used for PA by looking at price entries
                attrs = pp.get("attributes", {})
                customer_price = attrs.get("customerPrice", "0")
                try:
                    price = float(customer_price)
                    all_panama_price_points.append({
                        "id": pp_id,
                        "price": price
                    })
                except:
                    pass
            
            # Check for next page
            links = data.get("links", {})
            next_url = links.get("next")
            if next_url and "cursor=" in next_url:
                new_cursor = next_url.split("cursor=")[-1].split("&")[0]
                if cursor != new_cursor:
                    cursor = new_cursor
                else:
                    break
            else:
                break
        except Exception as e:
            print(f"  ⚠ Error fetching price points: {e}")
            break
    
    # Instead, let's find price points that are actually used for PA by checking all price entries
    print(f"  Searching price entries for {TERRITORY}...")
    panama_price_points_used = {}
    
    cursor = None
    while True:
        endpoint = f"/subscriptions/{SUBSCRIPTION_ID}/prices"
        params = {
            "include": "subscriptionPricePoint",
            "limit": 200
        }
        if cursor:
            params["cursor"] = cursor
        
        data = api._make_request(endpoint, params=params)
        prices = data.get("data", [])
        included = data.get("included", [])
        
        # Build price point map from included
        for item in included:
            if item.get("type") == "subscriptionPricePoints":
                pp_id = item.get("id")
                attrs = item.get("attributes", {})
                customer_price = attrs.get("customerPrice", "0")
                try:
                    panama_price_points_used[pp_id] = float(customer_price)
                except:
                    pass
        
        # Check price entries for PA
        for price_entry in prices:
            attrs = price_entry.get("attributes", {})
            price_entry_id = price_entry.get("id")
            territory = decode_price_entry_id(price_entry_id)
            
            if territory == TERRITORY:
                price_point_ref = price_entry.get("relationships", {}).get("subscriptionPricePoint", {}).get("data", {})
                pp_id = price_point_ref.get("id")
                if pp_id in panama_price_points_used:
                    # This price point is available for PA
                    pass
        
        # Check for next page
        links = data.get("links", {})
        next_url = links.get("next")
        if next_url and "cursor=" in next_url:
            new_cursor = next_url.split("cursor=")[-1].split("&")[0]
            if cursor != new_cursor:
                cursor = new_cursor
            else:
                break
        else:
            break
    
    # Now find nearest tier using the function
    print(f"\n7. Finding nearest price tier for ${new_price_usd:.2f} USD...")
    nearest_tier_id = find_nearest_price_tier(
        api, SUBSCRIPTION_ID, new_price_usd, TERRITORY, price_details, exchange_rates
    )
    
    if not nearest_tier_id:
        print("  ❌ Could not find matching price tier.")
        print(f"\n  NOTE: This might mean Apple doesn't have a price tier close to ${new_price_usd:.2f} USD")
        print(f"  for Panama. You may need to use a different price or check available tiers manually.")
        return
    
    # Find the price for the nearest tier
    nearest_tier_price = price_point_map.get(nearest_tier_id, 0)
    print(f"  ✓ Found price tier: ${nearest_tier_price:.2f} USD")
    print(f"  ✓ Tier ID: {nearest_tier_id[:60]}...")
    
    # Check if it's different from current
    if nearest_tier_id == current_price_point_id:
        print(f"\n  ⚠️  WARNING: The nearest tier is the SAME as current price!")
        print(f"  Calculated price: ${new_price_usd:.2f} USD")
        print(f"  Nearest tier price: ${nearest_tier_price:.2f} USD")
        print(f"  Current price: ${current_price_pa:.2f} USD")
        print(f"  Difference: ${abs(new_price_usd - nearest_tier_price):.2f} USD")
        print(f"\n  This means Apple doesn't have a tier close enough to ${new_price_usd:.2f} USD.")
        print(f"  The price change cannot be made because there's no suitable tier available.")
        print(f"  Consider: Adjusting the target price or checking if Panama needs a different pricing strategy.")
        return
    
    # Step 9: Preview
    print(f"\n{'='*100}")
    print("PREVIEW:")
    print(f"  Territory: {TERRITORY} (Panama)")
    print(f"  Current price: ${current_price_pa:.2f} USD")
    print(f"  Calculated price: ${new_price_usd:.2f} USD")
    print(f"  Nearest tier price: ${nearest_tier_price:.2f} USD")
    print(f"  Change: ${nearest_tier_price - current_price_pa:+.2f} USD")
    print(f"  Current price point ID: {current_price_point_id[:50]}...")
    print(f"  New price point ID: {nearest_tier_id[:50]}...")
    print(f"{'='*100}")
    
    # Step 10: Ask for confirmation
    response = input(f"\nUpdate price for {TERRITORY}? (yes/no): ").strip().lower()
    
    if response == 'yes':
        start_date_input = input("Start date (YYYY-MM-DD, or Enter for tomorrow): ").strip()
        start_date = None
        if start_date_input:
            try:
                datetime.strptime(start_date_input, "%Y-%m-%d")
                start_date = start_date_input
            except ValueError:
                print("Invalid date format. Using tomorrow.")
                start_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        else:
            start_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        
        print(f"\n6. Creating price change...")
        print(f"  Subscription: {SUBSCRIPTION_ID}")
        print(f"  Price Point ID: {nearest_tier_id[:60]}...")
        print(f"  Start Date: {start_date}")
        print()
        
        try:
            result = api.update_subscription_price(
                SUBSCRIPTION_ID,
                nearest_tier_id,
                start_date=start_date
            )
            
            print(f"  ✓ API Response:")
            print(f"    Result type: {type(result)}")
            print(f"    Result: {json.dumps(result, indent=2) if isinstance(result, dict) else result}")
            
            # Check if startDate was set correctly
            if isinstance(result, dict):
                attrs = result.get("attributes", {})
                returned_start_date = attrs.get("startDate")
                if returned_start_date == start_date:
                    print(f"\n  ✓✓✓ SUCCESS: Price change scheduled for {start_date}")
                elif returned_start_date is None:
                    print(f"\n  ⚠️  WARNING: API returned startDate: null (current price, not scheduled)")
                    print(f"  This might mean the price point is already the current price.")
                else:
                    print(f"\n  ⚠️  NOTE: API returned different start date: {returned_start_date}")
            
        except Exception as e:
            print(f"  ❌ Error: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("Cancelled.")

if __name__ == "__main__":
    main()

