#!/usr/bin/env python3
"""
Update subscription prices based on Big Mac Index
Keeps USA base price, applies multipliers to all other countries
"""
import json
import base64
from datetime import datetime, timedelta
from appstore_api import AppStoreConnectAPI
from price_calculator import PriceCalculator
from exchange_rates import ExchangeRates
import config

# Selected subscription IDs to update
SELECTED_SUBSCRIPTIONS = {
    "6743362609": "Annual 80% OFF Subscription",
    "6754931910": "Annual Expensive 2",
    "6743152682": "Annual Subscription",
    "6747279472": "Annual Subscription + Trial",
    "6754627997": "Annual Subscription Cheap",
    "6754931704": "Annual Subscription Expensive 1",
    "6745085678": "Weekly Subscription",
    "6754627884": "Weekly Subscription Cheap",
    "6743152701": "Monthly Subscription",
    "6754627901": "Monthly Subscription Cheap"
}

def decode_price_entry_id(price_entry_id):
    """Decode price entry ID to extract territory"""
    try:
        # Add padding if needed
        padded = price_entry_id + '=='
        decoded = base64.urlsafe_b64decode(padded)
        data = json.loads(decoded)
        return data.get('c', '')  # 'c' is the territory code
    except:
        return None

def get_price_details(api, subscription_id):
    """Get detailed price information including territories"""
    # Get prices with included data - fetch all pages
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
    
    # Build price point lookup
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
            
            price_point_map[price_point_id] = {
                "id": price_point_id,
                "price": price
            }
    
    # Map prices to territories - get active prices only (startDate is null and preserved is false)
    price_details = []
    seen_territories = set()
    
    for price_entry in all_prices:
        attrs = price_entry.get("attributes", {})
        start_date = attrs.get("startDate")
        preserved = attrs.get("preserved", False)
        
        # Get active price (no startDate means it's the current price)
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
    # Try both US and USA territory codes
    for detail in price_details:
        territory = detail.get("territory", "")
        if territory in ["US", "USA"]:
            return detail.get("price", 0)
    return None

def find_nearest_price_tier(api, subscription_id, target_price_usd, territory, price_details_all, exchange_rates):
    """
    Find the nearest Apple price tier for a target USD price
    
    Strategy:
    1. Get all available price points from subscription prices (they're included in the response)
    2. Find USA price points to establish tier index/position
    3. Find the tier in USA that matches our target USD price
    4. Use the same tier index for the target territory
    5. If exact match not found, find closest tier by converting to USD equivalent
    """
    try:
        # Fetch subscription prices with included price points
        endpoint = f"/subscriptions/{subscription_id}/prices"
        params = {
            "include": "subscriptionPricePoint",
            "limit": 200
        }
        
        data = api._make_request(endpoint, params=params)
        included = data.get("included", [])
        
        # Extract price points (tiers)
        price_points = {}
        for item in included:
            if item.get("type") == "subscriptionPricePoints":
                tier_id = item.get("id")
                attrs = item.get("attributes", {})
                customer_price_str = attrs.get("customerPrice", "0")
                try:
                    price = float(customer_price_str)
                    price_points[tier_id] = {
                        "id": tier_id,
                        "price": price,
                        "tier_id": tier_id
                    }
                except:
                    continue
        
        if not price_points:
            return None
        
        # Get USA price to establish baseline
        usa_price = None
        usa_tier_id = None
        for detail in price_details_all:
            if detail.get("territory") in ["US", "USA"]:
                usa_price = detail.get("price", 0)
                usa_tier_id = detail.get("id")  # This is the price_point_id
                break
        
        if not usa_price or not usa_tier_id:
            return None
        
        # Find all price entries to map tiers to territories
        # We need to get price entries and their relationships to price points
        all_price_entries = []
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
            
            # Build price point map
            tier_map = {}
            for item in included:
                if item.get("type") == "subscriptionPricePoints":
                    tier_id = item.get("id")
                    attrs = item.get("attributes", {})
                    customer_price_str = attrs.get("customerPrice", "0")
                    try:
                        price = float(customer_price_str)
                        tier_map[tier_id] = price
                    except:
                        pass
            
            # Map price entries to territories
            for price_entry in prices:
                attrs = price_entry.get("attributes", {})
                start_date = attrs.get("startDate")
                preserved = attrs.get("preserved", False)
                
                if start_date is None and not preserved:
                    price_entry_id = price_entry.get("id")
                    territory_code = decode_price_entry_id(price_entry_id)
                    
                    if territory_code:
                        price_point_ref = price_entry.get("relationships", {}).get("subscriptionPricePoint", {}).get("data", {})
                        tier_id = price_point_ref.get("id")
                        
                        if tier_id in tier_map:
                            all_price_entries.append({
                                "territory": territory_code,
                                "tier_id": tier_id,
                                "price": tier_map[tier_id]
                            })
            
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
        
        # Find USA tier price
        usa_tier_price = None
        for entry in all_price_entries:
            if entry["territory"] in ["US", "USA"] and entry["tier_id"] == usa_tier_id:
                usa_tier_price = entry["price"]
                break
        
        if not usa_tier_price:
            return None
        
        # Calculate which tier we need based on target_price_usd / usa_price ratio
        price_ratio = target_price_usd / usa_price if usa_price > 0 else 1.0
        target_tier_price_usd = usa_tier_price * price_ratio
        
        # Find all tiers used for target territory
        territory_tiers = [e for e in all_price_entries if e["territory"] == territory]
        
        if not territory_tiers:
            return None
        
        # Find closest tier for target territory
        # All target prices are in USD, so we need to convert tier prices to USD for comparison
        min_diff = float('inf')
        best_tier_id = None
        
        # Get currency for territory to convert tier prices back to USD
        currency_map = {
            "AU": "AUD", "GB": "GBP", "CA": "CAD", "EU": "EUR", "DE": "EUR",
            "FR": "EUR", "IT": "EUR", "ES": "EUR", "JP": "JPY", "CN": "CNY",
            "CH": "CHF", "SE": "SEK", "NO": "NOK", "DK": "DKK", "NZ": "NZD",
            "SG": "SGD", "HK": "HKD", "KR": "KRW", "IN": "INR", "BR": "BRL",
            "MX": "MXN", "AR": "ARS", "ZA": "ZAR", "AE": "AED", "SA": "SAR"
        }
        currency = currency_map.get(territory, "USD")
        
        for entry in territory_tiers:
            tier_price_local = entry["price"]  # Price in local currency
            
            # Convert tier price from local currency to USD for comparison
            if currency == "USD":
                tier_price_usd = tier_price_local
            elif exchange_rates and exchange_rates.rates:
                # Convert local currency tier price to USD
                tier_price_usd = exchange_rates.convert_local_to_usd(tier_price_local, currency)
                if tier_price_usd is None:
                    # Fallback: use relative pricing if conversion fails
                    if usa_tier_price > 0 and usa_price > 0:
                        # Estimate USD value based on ratio to USA tier
                        tier_price_usd = tier_price_local * (usa_price / usa_tier_price)
                    else:
                        continue
            else:
                # No exchange rates available - use relative pricing
                if usa_tier_price > 0 and usa_price > 0:
                    # Estimate: if USA tier is X USD and local tier is Y local currency,
                    # estimate USD as: Y * (USA_price / USA_tier_price)
                    tier_price_usd = tier_price_local * (usa_price / usa_tier_price)
                else:
                    continue
            
            # Compare target USD price with tier USD equivalent
            diff = abs(tier_price_usd - target_price_usd)
            
            if diff < min_diff:
                min_diff = diff
                best_tier_id = entry["tier_id"]
        
        return best_tier_id
        
    except Exception as e:
        print(f"  Error finding price tier for {territory}: {e}")
        import traceback
        traceback.print_exc()
        return None

def update_subscription_prices(api, calculator, exchange_rates, subscription_id, subscription_name, start_date=None):
    """Update prices for a subscription based on Big Mac Index"""
    print(f"\n{'='*100}")
    print(f"Processing: {subscription_name} (ID: {subscription_id})")
    print(f"{'='*100}")
    
    # Get current price details
    print("Fetching current prices...")
    price_details = get_price_details(api, subscription_id)
    
    if not price_details:
        print("  No prices found. Skipping.")
        return
    
    # Get USA base price
    usa_price = get_usa_base_price(price_details)
    if usa_price is None or usa_price == 0:
        print(f"  Could not find USA base price. Skipping.")
        return
    
    print(f"  USA base price: ${usa_price:.2f} USD")
    print(f"  Found {len(price_details)} price points")
    
    # Get Big Mac Index ratios
    print("  Fetching Big Mac Index ratios...")
    all_ratios = calculator.bigmac.get_all_ratios()
    
    # Get current exchange rates
    print("  Fetching current exchange rates...")
    if not exchange_rates.fetch_current_rates():
        print("  Warning: Could not fetch exchange rates. Proceeding with Big Mac Index only.")
    
    # Calculate new prices and prepare updates
    updates = []
    skipped = []
    
    print(f"\n  Calculating new prices...")
    for detail in price_details:
        territory = detail.get("territory", "")
        current_price = detail.get("price", 0)
        price_entry_id = detail.get("price_entry_id")
        
        # Skip USA - keep base price
        if territory in ["US", "USA"]:
            skipped.append({
                "territory": territory,
                "current_price": current_price,
                "action": "Keep unchanged (base price)"
            })
            continue
        
        # Get Big Mac Index ratio
        ratio = all_ratios.get(territory)
        if ratio is None:
            # Try alternative territory code formats
            ratio = calculator.bigmac.get_country_ratio(territory)
        
        if ratio is None:
            skipped.append({
                "territory": territory,
                "current_price": current_price,
                "action": "No Big Mac Index data available"
            })
            continue
        
        # Calculate new price in USD
        new_price_usd = usa_price * ratio
        
        # Find nearest price tier (matching by USD value, Apple converts to local currency)
        nearest_tier_id = find_nearest_price_tier(api, subscription_id, new_price_usd, territory, price_details, exchange_rates)
        
        if nearest_tier_id:
            updates.append({
                "territory": territory,
                "current_price": current_price,  # This is in local currency
                "calculated_price_usd": new_price_usd,  # This is in USD
                "ratio": ratio,
                "price_entry_id": price_entry_id,
                "price_point_id": nearest_tier_id
            })
        else:
            skipped.append({
                "territory": territory,
                "current_price": current_price,
                "calculated_price_usd": new_price_usd,
                "action": "Could not find matching price tier"
            })
    
    # Display preview
    print(f"\n  Preview of changes:")
    print(f"  {'Territory':<15} {'Current (local)':<20} {'New (USD)':<15} {'Ratio':<10} {'Status':<20}")
    print(f"  {'-'*80}")
    
    for update in updates:
        print(f"  {update['territory']:<15} {update['current_price']:<20.2f} ${update['calculated_price_usd']:<14.2f} {update['ratio']:<10.3f} Ready to update")
    
    for skip in skipped:
        action = skip.get('action', 'Skipped')
        print(f"  {skip['territory']:<15} ${skip['current_price']:<14.2f} {'-':<15} {'-':<10} {action}")
    
    print(f"\n  Summary: {len(updates)} territories ready to update, {len(skipped)} skipped")
    
    # Ask for confirmation
    if updates:
        response = input(f"\n  Update prices for {subscription_name}? (yes/no): ").strip().lower()
        if response == 'yes':
            print(f"  Updating prices...")
            success_count = 0
            error_count = 0
            
            for update in updates:
                try:
                    # Update price with start date
                    result = api.update_subscription_price(
                        subscription_id, 
                        update['price_point_id'],
                        start_date=start_date
                    )
                    success_count += 1
                    print(f"    ✓ Updated {update['territory']} (scheduled for {start_date or 'immediate'})")
                except Exception as e:
                    error_count += 1
                    print(f"    ✗ Error updating {update['territory']}: {e}")
            
            print(f"\n  Update complete: {success_count} successful, {error_count} errors")
        else:
            print(f"  Skipped updating {subscription_name}")
    else:
        print(f"  No updates to apply for {subscription_name}")

def main():
    print("="*100)
    print("ASO Pricing Update - Big Mac Index Based")
    print("="*100)
    print(f"\nSelected {len(SELECTED_SUBSCRIPTIONS)} subscription products to update")
    print("Strategy: Keep USA base price, apply Big Mac Index multipliers to all other countries")
    print("Using current exchange rates (November 14, 2025)")
    print("Price changes will take effect immediately\n")
    
    start_date = None  # Immediate
    
    api = AppStoreConnectAPI()
    calculator = PriceCalculator()
    exchange_rates = ExchangeRates()
    
    # Process each subscription one at a time
    subscriptions_list = list(SELECTED_SUBSCRIPTIONS.items())
    total = len(subscriptions_list)
    
    for idx, (subscription_id, subscription_name) in enumerate(subscriptions_list, 1):
        print(f"\n{'='*100}")
        print(f"PROCESSING SUBSCRIPTION {idx} of {total}")
        print(f"{'='*100}")
        
        try:
            update_subscription_prices(api, calculator, exchange_rates, subscription_id, subscription_name, start_date)
            
            if idx < total:
                response = input(f"\nContinue to next subscription? (yes/no): ").strip().lower()
                if response != 'yes':
                    print("\nStopped by user.")
                    break
        except Exception as e:
            print(f"\n  ✗ Error processing {subscription_name}: {e}")
            import traceback
            traceback.print_exc()
            
            if idx < total:
                response = input(f"\nContinue to next subscription despite error? (yes/no): ").strip().lower()
                if response != 'yes':
                    print("\nStopped by user.")
                    break
    
    print("\n" + "="*100)
    print("All subscriptions processed!")
    print("="*100)

if __name__ == "__main__":
    main()

