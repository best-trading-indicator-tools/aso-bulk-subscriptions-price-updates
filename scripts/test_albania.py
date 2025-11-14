#!/usr/bin/env python3
"""
Test script - Update prices for Albania only
"""
import json
import base64
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from appstore_api import AppStoreConnectAPI
from price_calculator import PriceCalculator
from exchange_rates import ExchangeRates
import config

# Test with one subscription
TEST_SUBSCRIPTION_ID = "6743152682"  # Annual Subscription
TEST_SUBSCRIPTION_NAME = "Annual Subscription"
TEST_TERRITORY = "AU"  # Australia (for testing)

def decode_price_entry_id(price_entry_id):
    """Decode price entry ID to extract territory"""
    try:
        padded = price_entry_id + '=='
        decoded = base64.urlsafe_b64decode(padded)
        data = json.loads(decoded)
        return data.get('c', '')
    except:
        return None

def get_price_details(api, subscription_id):
    """Get detailed price information including territories"""
    all_prices = []
    all_included = []
    cursor = None
    
    while True:
        endpoint = f"/subscriptions/{subscription_id}/prices"
        params = {
            "include": "subscriptionPricePoint",
            "limit": 200
        }
        if cursor:
            params["cursor"] = cursor
        
        data = api._make_request(endpoint, params=params)
        prices = data.get("data", [])
        included = data.get("included", [])
        
        all_prices.extend(prices)
        all_included.extend(included)
        
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
    
    price_point_map = {}
    for item in all_included:
        if item.get("type") == "subscriptionPricePoints":
            price_point_id = item.get("id")
            attrs = item.get("attributes", {})
            customer_price_str = attrs.get("customerPrice", "0")
            try:
                price = float(customer_price_str)
            except:
                price = 0
            price_point_map[price_point_id] = {"id": price_point_id, "price": price}
    
    price_details = []
    seen_territories = set()
    
    for price_entry in all_prices:
        attrs = price_entry.get("attributes", {})
        start_date = attrs.get("startDate")
        preserved = attrs.get("preserved", False)
        
        if start_date is None and not preserved:
            price_entry_id = price_entry.get("id")
            territory = decode_price_entry_id(price_entry_id)
            
            if territory and territory not in seen_territories:
                price_point_ref = price_entry.get("relationships", {}).get("subscriptionPricePoint", {}).get("data", {})
                price_point_id = price_point_ref.get("id")
                
                if price_point_id in price_point_map:
                    detail = price_point_map[price_point_id].copy()
                    detail["territory"] = territory
                    detail["price_entry_id"] = price_entry_id
                    price_details.append(detail)
                    seen_territories.add(territory)
    
    return price_details

def get_usa_base_price(price_details):
    """Extract USA base price"""
    for detail in price_details:
        territory = detail.get("territory", "")
        if territory in ["US", "USA"]:
            return detail.get("price", 0)
    return None

def find_nearest_price_tier(api, subscription_id, target_price_usd, territory, price_details_all, exchange_rates):
    """
    Find the nearest Apple price tier - import from update_prices module
    """
    # Import the function from the main update_prices module
    from update_prices import find_nearest_price_tier as find_tier
    return find_tier(api, subscription_id, target_price_usd, territory, price_details_all, exchange_rates)

def main():
    print("="*100)
    print("TEST: Update price for Australia only")
    print("="*100)
    print(f"\nSubscription: {TEST_SUBSCRIPTION_NAME} (ID: {TEST_SUBSCRIPTION_ID})")
    print(f"Territory: Australia ({TEST_TERRITORY})\n")
    
    api = AppStoreConnectAPI()
    calculator = PriceCalculator()
    exchange_rates = ExchangeRates()
    
    # Get current prices
    print("Fetching current prices...")
    price_details = get_price_details(api, TEST_SUBSCRIPTION_ID)
    
    if not price_details:
        print("  No prices found.")
        return
    
    # Get USA base price
    usa_price = get_usa_base_price(price_details)
    if usa_price is None or usa_price == 0:
        print("  Could not find USA base price.")
        return
    
    print(f"  USA base price: ${usa_price:.2f} USD")
    
    # Get Australia current price
    territory_detail = None
    for detail in price_details:
        if detail.get("territory") == TEST_TERRITORY:
            territory_detail = detail
            break
    
    if not territory_detail:
        print(f"  Could not find current price for Australia.")
        return
    
    current_price_au = territory_detail.get("price", 0)
    print(f"  Australia current price: {current_price_au:.2f} AUD (local currency)")
    
    # Get Big Mac Index ratio
    print("\nFetching Big Mac Index ratio...")
    all_ratios = calculator.bigmac.get_all_ratios()
    ratio = all_ratios.get(TEST_TERRITORY)
    
    if ratio is None:
        ratio = calculator.bigmac.get_country_ratio(TEST_TERRITORY)
    
    if ratio is None:
        print(f"  No Big Mac Index data for Australia.")
        return
    
    print(f"  Big Mac Index ratio: {ratio:.3f}")
    
    # Calculate new USD price
    new_price_usd = usa_price * ratio
    print(f"  New price (USD): ${new_price_usd:.2f}")
    
    # Get exchange rates
    print("\nFetching exchange rates...")
    if exchange_rates.fetch_current_rates():
        rate_aud = exchange_rates.get_rate("AUD")
        if rate_aud:
            new_price_aud = exchange_rates.convert_usd_to_local(new_price_usd, "AUD")
            print(f"  Exchange rate (USD to AUD): {rate_aud:.4f}")
            print(f"  New price (AUD): {new_price_aud:.2f} AUD")
    
    # Find matching price tier
    print("\nFinding matching Apple price tier...")
    tier_id = find_nearest_price_tier(api, TEST_SUBSCRIPTION_ID, new_price_usd, TEST_TERRITORY, price_details, exchange_rates)
    
    if not tier_id:
        print("  Could not find matching price tier.")
        return
    
    print(f"  Found matching tier ID: {tier_id[:50]}...")
    
    # Get the actual tier price to show
    endpoint = "/subscriptionPricePoints"
    params = {
        "filter[id]": tier_id
    }
    try:
        data = api._make_request(endpoint, params=params)
        tier_data = data.get("data", [])
        if tier_data:
            tier_price = tier_data[0].get("attributes", {}).get("customerPrice", "0")
            print(f"  Tier price: {tier_price} ALL")
    except:
        pass
    
    # Ask for confirmation
    print("\n" + "="*100)
    print("SUMMARY:")
    print(f"  Territory: Australia ({TEST_TERRITORY})")
    print(f"  Current price: {current_price_au:.2f} AUD")
    print(f"  New price (USD): ${new_price_usd:.2f}")
    print(f"  Big Mac Index ratio: {ratio:.3f}")
    print("="*100)
    
    response = input("\nUpdate price for Australia? (yes/no): ").strip().lower()
    
    if response == 'yes':
        date_input = input("Start date (YYYY-MM-DD, or Enter for immediate): ").strip()
        start_date = None
        if date_input:
            try:
                datetime.strptime(date_input, "%Y-%m-%d")
                start_date = date_input
            except ValueError:
                print("Invalid date format. Using immediate.")
        
        try:
            result = api.update_subscription_price(
                TEST_SUBSCRIPTION_ID,
                tier_id,
                start_date=start_date
            )
            print(f"\n✓ Successfully updated price for Australia!")
            print(f"  Scheduled for: {start_date or 'immediate'}")
        except Exception as e:
            print(f"\n✗ Error updating price: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("Cancelled.")

if __name__ == "__main__":
    main()

