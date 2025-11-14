#!/usr/bin/env python3
"""
Update subscription prices based on Big Mac Index
Keeps USA base price, applies multipliers to all other countries
"""
import json
import base64
import sys
from datetime import datetime, timedelta
from appstore_api import AppStoreConnectAPI
from price_calculator import PriceCalculator
from exchange_rates import ExchangeRates
import config

# Selected subscription IDs to update
# Load from config (which reads from .env)
# Format in .env: SUBSCRIPTIONS_TO_UPDATE="ID1:Name1,ID2:Name2,ID3:Name3"
SELECTED_SUBSCRIPTIONS = config.SUBSCRIPTIONS_TO_UPDATE

if not SELECTED_SUBSCRIPTIONS:
    print("⚠️  Warning: No subscriptions configured in .env file")
    print("   Set SUBSCRIPTIONS_TO_UPDATE in .env with format: ID1:Name1,ID2:Name2")
    print("   Example: SUBSCRIPTIONS_TO_UPDATE=\"6743152682:Annual Subscription,6743152701:Monthly Subscription\"")
    sys.exit(1)

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

def decode_price_point_id(price_point_id):
    """Decode price point ID to extract subscription, territory, and tier code"""
    try:
        padded = price_point_id + '=='
        decoded = base64.urlsafe_b64decode(padded)
        data = json.loads(decoded)
        return {
            'subscription_id': data.get('s', ''),
            'territory': data.get('t', ''),
            'tier_code': data.get('p', '')
        }
    except Exception as e:
        return None

def encode_price_point_id(subscription_id, territory, tier_code):
    """Encode price point ID from components"""
    try:
        data = {
            's': subscription_id,
            't': territory,
            'p': tier_code
        }
        json_str = json.dumps(data, separators=(',', ':'))
        encoded = base64.urlsafe_b64encode(json_str.encode()).decode().rstrip('=')
        return encoded
    except Exception as e:
        return None

def find_nearest_price_tier(api, subscription_id, target_price_usd, territory, price_details_all, exchange_rates):
    """
    Find the next tier ABOVE target price (not closest, but first tier above target)
    
    Strategy:
    1. Get ALL available price points from subscription prices (not just territory-specific ones)
    2. Decode price point IDs to extract tier codes
    3. Group by tier code and find average price per tier
    4. Select the tier with smallest price that is >= target_price_usd
    5. Find or construct price point ID for target territory with selected tier
    """
    try:
        # Fetch ALL price points from API (all pages)
        all_price_points = {}
        cursor = None
        
        # Map territory codes: 2-letter to 3-letter for price point IDs
        territory_3letter_map = {
            "PA": "PAN", "US": "USA", "AT": "AUT", "DE": "DEU", "FR": "FRA",
            "IT": "ITA", "ES": "ESP", "GB": "GBR", "CA": "CAN", "AU": "AUS",
            "JP": "JPN", "CN": "CHN", "IN": "IND", "BR": "BRA", "MX": "MEX"
        }
        territory_3letter = territory_3letter_map.get(territory, territory.upper()[:3])
        
        while True:
            endpoint = f"/subscriptions/{subscription_id}/prices"
            params = {
                "include": "subscriptionPricePoint",
                "limit": 200
            }
            if cursor:
                params["cursor"] = cursor
            
            data = api._make_request(endpoint, params=params)
            included = data.get("included", [])
            
            # Extract all price points and decode them
            for item in included:
                if item.get("type") == "subscriptionPricePoints":
                    pp_id = item.get("id")
                    attrs = item.get("attributes", {})
                    customer_price_str = attrs.get("customerPrice", "0")
                    
                    try:
                        price = float(customer_price_str)
                        decoded = decode_price_point_id(pp_id)
                        
                        if decoded:
                            all_price_points[pp_id] = {
                                "id": pp_id,
                                "price": price,
                                "territory": decoded['territory'],
                                "tier_code": decoded['tier_code'],
                                "subscription_id": decoded['subscription_id']
                            }
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
        
        if not all_price_points:
            return None
        
        # Group by tier code and calculate average price per tier
        tier_codes = {}
        for pp_id, pp_data in all_price_points.items():
            tier_code = pp_data['tier_code']
            price = pp_data['price']
            
            if tier_code not in tier_codes:
                tier_codes[tier_code] = []
            tier_codes[tier_code].append(price)
        
        # Find tiers ABOVE target price
        candidates_above = []
        candidates_below = []
        
        for tier_code, prices in tier_codes.items():
            avg_price = sum(prices) / len(prices) if prices else 0
            
            if avg_price >= target_price_usd:
                candidates_above.append({
                    'tier_code': tier_code,
                    'avg_price': avg_price,
                    'diff': avg_price - target_price_usd
                })
            else:
                candidates_below.append({
                    'tier_code': tier_code,
                    'avg_price': avg_price,
                    'diff': target_price_usd - avg_price
                })
        
        # Sort above-target by price (ascending - smallest above target first)
        candidates_above.sort(key=lambda x: x['avg_price'])
        # Sort below-target by difference (ascending - closest below target first)
        candidates_below.sort(key=lambda x: x['diff'])
        
        # Select best tier: prefer tier above target, fallback to closest below
        if candidates_above:
            best_candidate = candidates_above[0]
            best_tier_code = best_candidate['tier_code']
        elif candidates_below:
            best_candidate = candidates_below[0]
            best_tier_code = best_candidate['tier_code']
        else:
            return None
        
        # Find price point ID for target territory with selected tier
        # IMPORTANT: Only use tiers that already exist for this territory
        # Apple doesn't allow creating new tier combinations - each territory has fixed available tiers
        
        best_price_point_id = None
        
        # Try to find existing price point for territory with this tier
        for pp_id, pp_data in all_price_points.items():
            pp_territory = pp_data['territory']
            # Check both 3-letter code and 2-letter code
            if (pp_territory == territory_3letter or pp_territory == territory) and pp_data['tier_code'] == best_tier_code:
                best_price_point_id = pp_id
                # Verify the price is reasonable (not too far from target)
                actual_price = pp_data['price']
                if abs(actual_price - target_price_usd) / target_price_usd > 0.5:  # More than 50% difference
                    print(f"  ⚠️  Warning: Tier {best_tier_code} exists for {territory} but price is ${actual_price:.2f} (target: ${target_price_usd:.2f})")
                break
        
        # If not found, discover ALL available price points for this territory
        # by constructing price point IDs and checking if they exist (like website UI)
        if not best_price_point_id:
            # First, collect tiers already found
            territory_tiers = []
            for pp_id, pp_data in all_price_points.items():
                pp_territory = pp_data['territory']
                if pp_territory == territory_3letter or pp_territory == territory:
                    territory_tiers.append({
                        'tier_code': pp_data['tier_code'],
                        'price': pp_data['price'],
                        'pp_id': pp_id
                    })
            
            # Then, test tier codes around target price to discover more options (parallel)
            tier_codes_to_test = set()
            # Add candidate tier codes
            for candidate in candidates_above + candidates_below:
                tier_codes_to_test.add(candidate['tier_code'])
            
            # Test tier codes in focused range around target price
            # Estimate tier range based on target price (roughly $0.005 per tier unit)
            base_tier = int(target_price_usd / 0.005) if target_price_usd > 0 else 10300
            # Test ±50 tiers around target (reduced from ±100 for performance)
            for tier_num in range(max(10000, base_tier - 50), min(11000, base_tier + 50), 10):
                tier_codes_to_test.add(str(tier_num))
            
            # Prepare parallel requests for tier code testing
            request_functions = []
            tier_code_list = sorted(tier_codes_to_test)
            
            for tier_code in tier_code_list:
                test_pp_id = encode_price_point_id(subscription_id, territory_3letter, tier_code)
                if test_pp_id:
                    pp_endpoint = f"/subscriptionPricePoints/{test_pp_id}"
                    request_functions.append((lambda ep: lambda: api._make_request(ep))(pp_endpoint))
                else:
                    request_functions.append(None)
            
            # Filter out None requests and track indices
            valid_requests = []
            valid_indices = []
            for idx, req in enumerate(request_functions):
                if req is not None:
                    valid_requests.append(req)
                    valid_indices.append(idx)
            
            # Make parallel requests (15 concurrent for faster discovery)
            if valid_requests:
                results = api._make_parallel_requests(valid_requests, max_workers=15)
                
                # Process results
                for result_idx, result in enumerate(results):
                    if result and result.get('data'):
                        original_idx = valid_indices[result_idx]
                        tier_code = tier_code_list[original_idx]
                        attrs = result['data'].get('attributes', {})
                        price = float(attrs.get('customerPrice', '0'))
                        
                        # Add if not already found
                        if not any(t['tier_code'] == tier_code for t in territory_tiers):
                            test_pp_id = encode_price_point_id(subscription_id, territory_3letter, tier_code)
                            territory_tiers.append({
                                'tier_code': tier_code,
                                'price': price,
                                'pp_id': test_pp_id
                            })
            
            if territory_tiers:
                # Find tier closest to target (prefer above, fallback to closest below)
                territory_tiers_above = [t for t in territory_tiers if t['price'] >= target_price_usd]
                if territory_tiers_above:
                    # Use smallest tier above target
                    best_territory_tier = min(territory_tiers_above, key=lambda x: x['price'])
                    best_price_point_id = best_territory_tier['pp_id']
                    print(f"  ⚠️  Tier {best_tier_code} not available for {territory}, using tier {best_territory_tier['tier_code']} (${best_territory_tier['price']:.2f})")
                else:
                    # Use closest tier below target
                    best_territory_tier = max(territory_tiers, key=lambda x: x['price'])
                    best_price_point_id = best_territory_tier['pp_id']
                    print(f"  ⚠️  No tier above target for {territory}, using tier {best_territory_tier['tier_code']} (${best_territory_tier['price']:.2f})")
            else:
                # No tiers found for this territory at all - cannot proceed
                print(f"  ❌ No price points found for territory {territory}")
                return None
        
        return best_price_point_id
        
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
    
    # Get index ratios
    index_name = "Big Mac Index" if calculator.index_type == "bigmac" else "Netflix Index"
    print(f"  Fetching {index_name} ratios...")
    all_ratios = calculator.index.get_all_ratios()
    
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
        
        # Get index ratio
        ratio = all_ratios.get(territory)
        if ratio is None:
            # Try alternative territory code formats
            ratio = calculator.index.get_country_ratio(territory)
        
        if ratio is None:
            index_name = "Big Mac Index" if calculator.index_type == "bigmac" else "Netflix Index"
            
            # For Netflix Index, try falling back to Big Mac Index
            if calculator.index_type == "netflix":
                try:
                    import bigmac_index
                    bigmac = bigmac_index.BigMacIndex()
                    bigmac.fetch_data()
                    bigmac_ratio = bigmac.get_country_ratio(territory)
                    if bigmac_ratio is not None:
                        ratio = bigmac_ratio
                        print(f"    ⚠️  {territory}: Using Big Mac Index as fallback (Netflix data unavailable)")
                    else:
                        skipped.append({
                            "territory": territory,
                            "current_price": current_price,
                            "action": f"No {index_name} or Big Mac Index data available"
                        })
                        continue
                except:
                    skipped.append({
                        "territory": territory,
                        "current_price": current_price,
                        "action": f"No {index_name} data available (fallback failed)"
                    })
                    continue
            else:
                skipped.append({
                    "territory": territory,
                    "current_price": current_price,
                    "action": f"No {index_name} data available"
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
    print("ASO Pricing Update - PPP Index Based")
    print("="*100)
    print(f"\nSelected {len(SELECTED_SUBSCRIPTIONS)} subscription product(s) to update")
    if not SELECTED_SUBSCRIPTIONS:
        print("⚠️  No subscriptions configured. Set SUBSCRIPTIONS_TO_UPDATE in .env file.")
        return
    
    # Choose index type
    print("\n" + "="*100)
    print("Select Pricing Index:")
    print("="*100)
    print("1. Big Mac Index (default) - Purchasing power parity based on Big Mac prices")
    print("2. Netflix Index - Purchasing power parity based on Netflix subscription prices")
    print()
    
    index_choice = input("Choose index (1 or 2, default: 1): ").strip()
    if index_choice == "2":
        index_type = "netflix"
        index_name = "Netflix Index"
    else:
        index_type = "bigmac"
        index_name = "Big Mac Index"
    
    print(f"\n✓ Using {index_name}")
    
    # Get start date
    print("\n" + "="*100)
    print("Price Change Start Date:")
    print("="*100)
    print("Note: Apple requires a future date for price changes (minimum 1 day ahead)")
    print("Format: YYYY-MM-DD (e.g., 2025-11-15)")
    print()
    
    start_date_input = input("Enter start date (YYYY-MM-DD) or press Enter for tomorrow: ").strip()
    
    if start_date_input:
        # Validate date format
        try:
            datetime.strptime(start_date_input, "%Y-%m-%d")
            start_date = start_date_input
        except ValueError:
            print("⚠️  Invalid date format. Using tomorrow as default.")
            start_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        start_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    
    print(f"✓ Price changes will take effect on: {start_date}")
    
    print("\n" + "="*100)
    print("Configuration Summary:")
    print("="*100)
    print(f"Index Type: {index_name}")
    print(f"Start Date: {start_date}")
    print(f"Strategy: Keep USA base price, apply {index_name} multipliers to all other countries")
    print("="*100 + "\n")
    
    api = AppStoreConnectAPI()
    calculator = PriceCalculator(index_type=index_type)
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

