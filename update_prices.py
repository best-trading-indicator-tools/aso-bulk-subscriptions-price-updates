#!/usr/bin/env python3
"""
Update subscription prices based on Big Mac Index
Keeps USA base price, applies multipliers to all other countries
"""
import json
import base64
import sys
import time
from datetime import datetime, timedelta
from appstore_api import AppStoreConnectAPI
from price_calculator import PriceCalculator
from exchange_rates import ExchangeRates
import config
from concurrent.futures import ThreadPoolExecutor, as_completed

# Selected subscription IDs to update
# Load from config (which reads from .env)
# Format in .env: SUBSCRIPTIONS_TO_UPDATE="ID1:Name1,ID2:Name2,ID3:Name3"
SELECTED_SUBSCRIPTIONS = config.SUBSCRIPTIONS_TO_UPDATE

if not SELECTED_SUBSCRIPTIONS:
    print("⚠️  Warning: No subscriptions configured in .env file")
    print("   Set SUBSCRIPTIONS_TO_UPDATE in .env with format: ID1:Name1,ID2:Name2")
    print("   Example: SUBSCRIPTIONS_TO_UPDATE=\"6743152682:Annual Subscription,6743152701:Monthly Subscription\"")
    sys.exit(1)

def format_duration(seconds):
    """Format duration in seconds to hours/minutes/seconds"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    
    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    else:
        return f"{secs}s"

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

def get_price_details(api, subscription_id, exchange_rates=None):
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
    
    # Currency mapping for conversion
    currency_map = {
        "MX": "MXN", "BR": "BRL", "CA": "CAD", "PA": "USD",
        "US": "USD", "USA": "USD"
    }
    
    # Map prices to territories - collect all prices (active, scheduled, preserved)
    territory_candidates = {}  # territory -> list of candidate prices
    
    for price_entry in all_prices:
        attrs = price_entry.get("attributes", {})
        start_date = attrs.get("startDate")
        preserved = attrs.get("preserved", False)
        price_entry_id = price_entry.get("id")
        territory = decode_price_entry_id(price_entry_id)
        
        if not territory:
            continue
        
        price_point_ref = price_entry.get("relationships", {}).get("subscriptionPricePoint", {}).get("data", {})
        price_point_id = price_point_ref.get("id")
        
        if price_point_id not in price_point_map:
            continue
        
        price_local = price_point_map[price_point_id]["price"]
        
        # Convert to USD
        currency_code = currency_map.get(territory, "USD")
        price_usd = price_local
        if currency_code != "USD" and exchange_rates and exchange_rates.rates:
            converted = exchange_rates.convert_local_to_usd(price_local, currency_code)
            if converted:
                price_usd = converted
        
        # Filter out placeholder prices (> 2x reasonable price - will be filtered later with base price)
        # For now, just collect all reasonable prices
        
        if territory not in territory_candidates:
            territory_candidates[territory] = []
        
        territory_candidates[territory].append({
            "territory": territory,
            "price": price_usd,  # USD price for comparison
            "price_local": price_local,
            "currency_code": currency_code,
            "id": price_point_id,
            "price_entry_id": price_entry_id,
            "start_date": start_date,
            "preserved": preserved,
            "priority": 0
        })
    
    # Select best price for each territory: active > preserved > scheduled
    price_details = []
    for territory, candidates in territory_candidates.items():
        # Set priority
        for candidate in candidates:
            if candidate["start_date"] is None and not candidate["preserved"]:
                candidate["priority"] = 1  # Active - highest priority
            elif candidate["preserved"]:
                candidate["priority"] = 2  # Preserved - medium priority
            elif candidate["start_date"] and not candidate["preserved"]:
                candidate["priority"] = 3  # Scheduled - lowest priority
        
        # Sort by priority, then by price (ascending)
        candidates.sort(key=lambda x: (x["priority"], x["price"]))
        
        # Use best candidate
        best = candidates[0]
        detail = {
            "territory": best["territory"],
            "price": best["price"],  # USD price
            "price_local": best.get("price_local", best["price"]),
            "currency_code": best.get("currency_code", "USD"),
            "id": best["id"],
            "price_entry_id": best["price_entry_id"],
            "start_date": best.get("start_date")
        }
        price_details.append(detail)
    
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
            # Test ±30 tiers around target (optimized for performance)
            for tier_num in range(max(10000, base_tier - 30), min(11000, base_tier + 30), 10):
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
            
            # Make parallel requests (20 concurrent for faster discovery)
            if valid_requests:
                results = api._make_parallel_requests(valid_requests, max_workers=20)
                
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
    subscription_start_time = time.time()
    
    print(f"\n{'='*100}")
    print(f"Processing: {subscription_name} (ID: {subscription_id})")
    print(f"{'='*100}")
    
    # Get current exchange rates first (needed for currency conversion)
    print("Fetching current exchange rates...")
    exchange_start = time.time()
    if not exchange_rates.fetch_current_rates():
        print("  Warning: Could not fetch exchange rates. Currency conversion may be inaccurate.")
    exchange_duration = time.time() - exchange_start
    print(f"  ⏱️  Exchange rates fetched in {format_duration(exchange_duration)}")
    
    # Get current price details (with exchange rates for currency conversion)
    print("Fetching current prices...")
    prices_start = time.time()
    price_details = get_price_details(api, subscription_id, exchange_rates)
    prices_duration = time.time() - prices_start
    print(f"  ⏱️  Prices fetched in {format_duration(prices_duration)}")
    
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
    
    # Filter out placeholder prices (> 2x base price)
    max_reasonable_price = usa_price * 2
    filtered_price_details = []
    for detail in price_details:
        price_usd = detail.get("price", 0)
        if price_usd <= max_reasonable_price:
            filtered_price_details.append(detail)
        else:
            territory = detail.get("territory", "")
            price_local = detail.get("price_local", price_usd)
            currency = detail.get("currency_code", "USD")
            print(f"  ⚠️  Filtered out placeholder price for {territory}: ${price_local:.2f} {currency} (${price_usd:.2f} USD)")
    
    price_details = filtered_price_details
    
    # Get index ratios
    index_name = "Big Mac Index" if calculator.index_type == "bigmac" else "Netflix Index"
    print(f"  Fetching {index_name} ratios...")
    all_ratios = calculator.index.get_all_ratios()
    
    # Calculate new prices and prepare updates
    updates = []
    skipped = []
    territory_times = []
    
    print(f"\n  Calculating new prices...")
    calc_start_time = time.time()
    cumulative_time = 0
    
    for idx, detail in enumerate(price_details, 1):
        territory_start = time.time()
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
            territory_duration = time.time() - territory_start
            territory_times.append({"territory": territory, "duration": territory_duration})
            cumulative_time += territory_duration
            if idx % 10 == 0:
                print(f"    📊 Processed {idx}/{len(price_details)} territories | "
                      f"Elapsed: {format_duration(cumulative_time)}")
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
        tier_start = time.time()
        nearest_tier_id = find_nearest_price_tier(api, subscription_id, new_price_usd, territory, price_details, exchange_rates)
        tier_duration = time.time() - tier_start
        
        if nearest_tier_id:
            updates.append({
                "territory": territory,
                "current_price": current_price,  # This is in USD (converted)
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
        
        territory_duration = time.time() - territory_start
        territory_times.append({"territory": territory, "duration": territory_duration})
        cumulative_time += territory_duration
        
        # Show progress every 10 territories
        if idx % 10 == 0:
            print(f"    📊 Processed {idx}/{len(price_details)} territories | "
                  f"Elapsed: {format_duration(cumulative_time)}")
    
    calc_duration = time.time() - calc_start_time
    print(f"  ⏱️  Calculation completed in {format_duration(calc_duration)}")
    
    # Display preview
    print(f"\n  Preview of changes:")
    print(f"  {'Territory':<15} {'Current (USD)':<20} {'New (USD)':<15} {'Ratio':<10} {'Time':<12} {'Status':<20}")
    print(f"  {'-'*100}")
    
    # Build territory time lookup
    territory_time_map = {t["territory"]: t["duration"] for t in territory_times}
    
    for update in updates:
        # Get current price details for display
        current_detail = next((d for d in price_details if d.get("territory") == update['territory']), None)
        territory_time = format_duration(territory_time_map.get(update['territory'], 0))
        
        if current_detail:
            current_price_local = current_detail.get("price_local", update['current_price'])
            currency = current_detail.get("currency_code", "USD")
            if currency != "USD":
                current_display = f"${current_price_local:.2f} {currency} (${update['current_price']:.2f})"
                print(f"  {update['territory']:<15} {current_display:<20} ${update['calculated_price_usd']:<14.2f} {update['ratio']:<10.3f} {territory_time:<12} Ready to update")
            else:
                print(f"  {update['territory']:<15} ${update['current_price']:<19.2f} ${update['calculated_price_usd']:<14.2f} {update['ratio']:<10.3f} {territory_time:<12} Ready to update")
        else:
            print(f"  {update['territory']:<15} ${update['current_price']:<19.2f} ${update['calculated_price_usd']:<14.2f} {update['ratio']:<10.3f} {territory_time:<12} Ready to update")
    
    for skip in skipped:
        action = skip.get('action', 'Skipped')
        current_price = skip.get('current_price', 0)
        territory_time = format_duration(territory_time_map.get(skip['territory'], 0))
        print(f"  {skip['territory']:<15} ${current_price:<19.2f} {'-':<15} {'-':<10} {territory_time:<12} {action}")
    
    # Calculate timing statistics
    total_territory_time = sum(t["duration"] for t in territory_times)
    avg_territory_time = total_territory_time / len(territory_times) if territory_times else 0
    subscription_duration = time.time() - subscription_start_time
    
    print(f"\n  ⏱️  TIMING SUMMARY:")
    print(f"    Exchange rates: {format_duration(exchange_duration)}")
    print(f"    Fetch prices: {format_duration(prices_duration)}")
    print(f"    Calculate & find tiers: {format_duration(calc_duration)}")
    print(f"    Average per territory: {format_duration(avg_territory_time)}")
    print(f"    Total processing time: {format_duration(subscription_duration)}")
    
    print(f"\n  Summary: {len(updates)} territories ready to update, {len(skipped)} skipped")
    
    # Ask for confirmation
    if updates:
        response = input(f"\n  Update prices for {subscription_name}? (yes/no): ").strip().lower()
        if response == 'yes':
            print(f"  Updating prices...")
            success_count = 0
            error_count = 0
            
            # Parallelize price updates for faster execution
            def update_territory(update_item):
                try:
                    result = api.update_subscription_price(
                        subscription_id, 
                        update_item['price_point_id'],
                        start_date=start_date
                    )
                    return (True, update_item['territory'], None)
                except Exception as e:
                    return (False, update_item['territory'], str(e))
            
            # Use parallel execution for updates (max 10 concurrent to avoid rate limits)
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = {executor.submit(update_territory, update): update for update in updates}
                for future in as_completed(futures):
                    success, territory, error = future.result()
                    if success:
                        success_count += 1
                        print(f"    ✓ Updated {territory} (scheduled for {start_date or 'immediate'})")
                    else:
                        error_count += 1
                        print(f"    ✗ Error updating {territory}: {error}")
            
            print(f"\n  Update complete: {success_count} successful, {error_count} errors")
        else:
            print(f"  Skipped updating {subscription_name}")
    else:
        print(f"  No updates to apply for {subscription_name}")

def estimate_completion_time(api, subscriptions_list, exchange_rates):
    """Estimate completion time based on subscription count and territories"""
    print("\n" + "="*100)
    print("Estimating completion time...")
    print("="*100)
    
    # Fetch exchange rates for currency conversion
    exchange_rates.fetch_current_rates()
    
    # Sample first subscription to estimate territories per subscription
    sample_sub_id = list(subscriptions_list.keys())[0]
    try:
        sample_price_details = get_price_details(api, sample_sub_id, exchange_rates)
        avg_territories_per_sub = len(sample_price_details) if sample_price_details else 50
    except:
        avg_territories_per_sub = 50  # Default estimate
    
    total_subscriptions = len(subscriptions_list)
    estimated_territories = total_subscriptions * avg_territories_per_sub
    
    # Time estimates (in seconds) based on operations:
    # - Fetch price details: ~2-5s per subscription (pagination)
    # - Find price tier per territory: ~1-3s (with parallel requests)
    # - Update price per territory: ~0.5-1s (with parallel updates)
    # - User confirmation time: ~10s per subscription
    
    time_per_subscription = {
        'fetch_prices': 3,  # seconds
        'find_tiers': avg_territories_per_sub * 1.5,  # seconds (parallelized)
        'update_prices': avg_territories_per_sub * 0.7,  # seconds (parallelized)
        'user_confirmation': 10  # seconds
    }
    
    total_seconds = total_subscriptions * sum(time_per_subscription.values())
    
    # Add overhead for API rate limiting and retries
    total_seconds = int(total_seconds * 1.2)  # 20% buffer
    
    estimated_duration = timedelta(seconds=total_seconds)
    estimated_end_time = datetime.now() + estimated_duration
    
    print(f"  Subscriptions to process: {total_subscriptions}")
    print(f"  Estimated territories per subscription: ~{avg_territories_per_sub}")
    print(f"  Total territories: ~{estimated_territories}")
    print(f"\n  Estimated completion time: {estimated_duration}")
    print(f"  Estimated end time: {estimated_end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*100 + "\n")
    
    return estimated_duration, estimated_end_time

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
    subscriptions_list = dict(SELECTED_SUBSCRIPTIONS.items())
    total = len(subscriptions_list)
    
    # Estimate completion time before starting
    estimated_duration, estimated_end_time = estimate_completion_time(api, subscriptions_list, exchange_rates)
    
    # Confirm before proceeding
    response = input("Proceed with price updates? (yes/no): ").strip().lower()
    if response != 'yes':
        print("\nCancelled by user.")
        return
    
    start_time = datetime.now()
    overall_start_time = time.time()
    print(f"\nStarted at: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Expected completion: {estimated_end_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    subscriptions_items = list(subscriptions_list.items())
    subscription_times = []
    
    for idx, (subscription_id, subscription_name) in enumerate(subscriptions_items, 1):
        subscription_start = time.time()
        print(f"\n{'='*100}")
        print(f"PROCESSING SUBSCRIPTION {idx} of {total}")
        print(f"{'='*100}")
        
        try:
            update_subscription_prices(api, calculator, exchange_rates, subscription_id, subscription_name, start_date)
            
            subscription_duration = time.time() - subscription_start
            subscription_times.append({"name": subscription_name, "duration": subscription_duration})
            cumulative_subscription_time = sum(s["duration"] for s in subscription_times)
            
            print(f"\n  ⏱️  Subscription '{subscription_name}' completed in {format_duration(subscription_duration)}")
            print(f"  📊 Progress: {idx}/{total} subscriptions | Total elapsed: {format_duration(cumulative_subscription_time)}")
            
            if idx < total:
                response = input(f"\nContinue to next subscription? (yes/no): ").strip().lower()
                if response != 'yes':
                    print("\nStopped by user.")
                    break
        except Exception as e:
            subscription_duration = time.time() - subscription_start
            subscription_times.append({"name": subscription_name, "duration": subscription_duration})
            
            print(f"\n  ✗ Error processing {subscription_name}: {e}")
            import traceback
            traceback.print_exc()
            
            if idx < total:
                response = input(f"\nContinue to next subscription despite error? (yes/no): ").strip().lower()
                if response != 'yes':
                    print("\nStopped by user.")
                    break
    
    end_time = datetime.now()
    overall_duration = time.time() - overall_start_time
    actual_duration = end_time - start_time
    
    # Calculate subscription timing stats
    total_subscription_time = sum(s["duration"] for s in subscription_times)
    avg_subscription_time = total_subscription_time / len(subscription_times) if subscription_times else 0
    
    print("\n" + "="*100)
    print("All subscriptions processed!")
    print("="*100)
    print(f"Started: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Completed: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\n⏱️  FINAL TIMING SUMMARY:")
    print(f"  Actual duration: {format_duration(overall_duration)}")
    print(f"  Estimated duration: {format_duration(estimated_duration.total_seconds())}")
    if overall_duration < estimated_duration.total_seconds():
        time_saved = estimated_duration.total_seconds() - overall_duration
        print(f"  ✓ Completed {format_duration(time_saved)} faster than estimated!")
    elif overall_duration > estimated_duration.total_seconds():
        time_over = overall_duration - estimated_duration.total_seconds()
        print(f"  ⚠️  Took {format_duration(time_over)} longer than estimated")
    
    if subscription_times:
        print(f"\n  Per-subscription breakdown:")
        for sub_time in subscription_times:
            print(f"    • {sub_time['name']}: {format_duration(sub_time['duration'])}")
        print(f"  Average per subscription: {format_duration(avg_subscription_time)}")
    
    print("="*100)

if __name__ == "__main__":
    main()

