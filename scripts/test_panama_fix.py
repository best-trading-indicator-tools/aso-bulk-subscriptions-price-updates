#!/usr/bin/env python3
"""
Standalone script to fix Panama price update
Finds available price points from ALL territories, not just Panama-specific ones

IMPORTANT: You CANNOT create new price points!
- Price points are pre-defined by Apple (800 per currency)
- You can only use existing price points that Apple has already created
- Each territory has a fixed set of available tiers
- Use equalizations endpoint to discover all available price points for a territory
- If a tier doesn't exist for a territory, you cannot create it - you must use what's available
"""
import sys
import os
import json
import base64
import argparse
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from appstore_api import AppStoreConnectAPI
from price_calculator import PriceCalculator
from exchange_rates import ExchangeRates
from update_prices import get_price_details, get_usa_base_price, decode_price_entry_id

SUBSCRIPTION_ID = "6743152682"  # Annual Subscription
TERRITORY = "PA"  # Panama (2-letter code for price entries)
TERRITORY_3LETTER = "PAN"  # Panama (3-letter code for price point IDs)

def decode_price_point_id(price_point_id):
    """Decode price point ID to extract subscription, territory, and tier code"""
    try:
        # Add padding if needed
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

def main(auto_confirm=False, start_date=None):
    print("="*100)
    print(f"Panama (PA) Price Update - Finding Available Price Points")
    print("="*100)
    
    api = AppStoreConnectAPI()
    calculator = PriceCalculator()
    exchange_rates = ExchangeRates()
    
    # Step 1: Get current prices and calculate target
    print("\n1. Fetching current prices and calculating target...")
    price_details = get_price_details(api, SUBSCRIPTION_ID)
    
    if not price_details:
        print("  ❌ No prices found.")
        return
    
    usa_price = get_usa_base_price(price_details)
    if usa_price is None or usa_price == 0:
        print("  ❌ Could not find USA base price.")
        return
    
    print(f"  ✓ USA base price: ${usa_price:.2f} USD")
    
    # Get Panama current price
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
    
    # Decode current price point to understand structure
    current_decoded = decode_price_point_id(current_price_point_id)
    if current_decoded:
        print(f"  ✓ Decoded current price point:")
        print(f"    Subscription: {current_decoded['subscription_id']}")
        print(f"    Territory: {current_decoded['territory']}")
        print(f"    Tier Code: {current_decoded['tier_code']}")
    
    # Calculate target price
    all_ratios = calculator.index.get_all_ratios()
    ratio = all_ratios.get(TERRITORY) or calculator.index.get_country_ratio(TERRITORY)
    
    if ratio is None:
        print(f"  ❌ No Big Mac Index data for {TERRITORY}.")
        return
    
    target_price_usd = usa_price * ratio
    print(f"\n2. Target price calculation:")
    print(f"  ✓ Big Mac Index ratio: {ratio:.4f}")
    print(f"  ✓ Target price: ${target_price_usd:.2f} USD")
    print(f"  ✓ Current price: ${current_price_pa:.2f} USD")
    print(f"  ✓ Change needed: ${target_price_usd - current_price_pa:+.2f} USD")
    
    # Step 2: Fetch ALL price points from API
    print(f"\n3. Fetching ALL price points from API...")
    all_price_points = {}
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
        included = data.get("included", [])
        
        # Extract all price points
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
    
    print(f"  ✓ Found {len(all_price_points)} unique price points")
    
    # Step 3: Find price points closest to target price
    print(f"\n4. Finding price points closest to ${target_price_usd:.2f} USD...")
    
    # Group by tier code and find closest prices
    tier_codes = {}
    for pp_id, pp_data in all_price_points.items():
        tier_code = pp_data['tier_code']
        price = pp_data['price']
        
        if tier_code not in tier_codes:
            tier_codes[tier_code] = []
        tier_codes[tier_code].append({
            'price': price,
            'territory': pp_data['territory'],
            'price_point_id': pp_id
        })
    
    # Find tier codes with prices ABOVE target (not closest, but next tier above)
    candidates_above = []
    candidates_below = []
    
    for tier_code, price_points in tier_codes.items():
        # Get average or representative price for this tier
        prices = [pp['price'] for pp in price_points]
        avg_price = sum(prices) / len(prices) if prices else 0
        
        if avg_price >= target_price_usd:
            candidates_above.append({
                'tier_code': tier_code,
                'avg_price': avg_price,
                'diff': avg_price - target_price_usd,  # Difference above target
                'price_points': price_points
            })
        else:
            candidates_below.append({
                'tier_code': tier_code,
                'avg_price': avg_price,
                'diff': target_price_usd - avg_price,  # Difference below target
                'price_points': price_points
            })
    
    # Sort above-target by price (ascending - smallest above target first)
    candidates_above.sort(key=lambda x: x['avg_price'])
    # Sort below-target by difference (ascending - closest below target first)
    candidates_below.sort(key=lambda x: x['diff'])
    
    print(f"  Tiers ABOVE target (${target_price_usd:.2f} USD):")
    if candidates_above:
        for i, candidate in enumerate(candidates_above[:5], 1):
            print(f"    {i}. Tier {candidate['tier_code']}: ${candidate['avg_price']:.2f} USD (+${candidate['diff']:.2f} above)")
            territories = list(set([pp['territory'] for pp in candidate['price_points']]))
            print(f"       Used by: {', '.join(sorted(territories)[:10])}{'...' if len(territories) > 10 else ''}")
    else:
        print(f"    No tiers found above target")
    
    print(f"\n  Tiers BELOW target (closest):")
    for i, candidate in enumerate(candidates_below[:3], 1):
        print(f"    {i}. Tier {candidate['tier_code']}: ${candidate['avg_price']:.2f} USD (-${candidate['diff']:.2f} below)")
    
    # Step 4: Discover ALL available price points for Panama FIRST
    # IMPORTANT: Only use tiers that already exist for Panama
    # Apple doesn't allow creating new tier combinations - each territory has fixed available tiers
    # Price points are pre-defined by Apple (800 per currency) - you CANNOT create new ones
    print(f"\n5. Discovering ALL available price points for {TERRITORY}...")
    
    # Method 1: Find tiers from currently active/scheduled prices
    panama_available_tiers = []
    for pp_id, pp_data in all_price_points.items():
        pp_territory = pp_data['territory']
        if pp_territory == TERRITORY_3LETTER or pp_territory == TERRITORY:
            panama_available_tiers.append({
                'tier_code': pp_data['tier_code'],
                'price': pp_data['price'],
                'pp_id': pp_id
            })
    
    # Method 2: Try constructing price point IDs for tier codes around target price
    # This discovers available price points (like the website UI shows)
    # OPTIMIZED: Only test tier codes around target price to reduce API calls
    print(f"  Testing tier codes around target price (${target_price_usd:.2f})...")
    
    # Get tier codes from candidates (most likely to exist)
    tier_codes_to_test = set()
    for candidate in candidates_above + candidates_below:
        tier_codes_to_test.add(candidate['tier_code'])
    
    # Test tier codes in a focused range around target price
    # Start from tier codes that would give prices around target
    # Based on discovered prices: 10330=$50.99, 10340=$54.00, so test 10300-10400
    for tier_num in range(10300, 10400, 10):
        tier_codes_to_test.add(str(tier_num))
    # Add some specific tiers we know exist
    for tier_num in [10248, 10325, 10330, 10340, 10345, 10350, 10356, 10360, 10369]:
        tier_codes_to_test.add(str(tier_num))
    
    discovered_count = 0
    tested_count = 0
    total_to_test = len(tier_codes_to_test)
    print(f"  → Testing {total_to_test} tier codes...")
    
    for tier_code in sorted(tier_codes_to_test):
        tested_count += 1
        if tested_count % 10 == 0:
            print(f"    Progress: {tested_count}/{total_to_test} tier codes tested...")
        
        # Construct price point ID for Panama with this tier
        test_pp_id = encode_price_point_id(SUBSCRIPTION_ID, TERRITORY_3LETTER, tier_code)
        if not test_pp_id:
            continue
        
        # Try to fetch this price point - if it exists, it's available!
        try:
            pp_endpoint = f"/subscriptionPricePoints/{test_pp_id}"
            pp_data = api._make_request(pp_endpoint)
            if pp_data.get('data'):
                attrs = pp_data['data'].get('attributes', {})
                price = float(attrs.get('customerPrice', '0'))
                
                # Add if not already found
                if not any(t['tier_code'] == tier_code for t in panama_available_tiers):
                    panama_available_tiers.append({
                        'tier_code': tier_code,
                        'price': price,
                        'pp_id': test_pp_id
                    })
                    discovered_count += 1
                    print(f"    ✓ Found Tier {tier_code}: ${price:.2f} USD")
        except:
            # Price point doesn't exist for this tier/territory combination
            pass
    
    print(f"  ✓ Tested {tested_count} tier codes, discovered {discovered_count} additional price points")
    
    
    if not panama_available_tiers:
        print(f"  ❌ No price points found for {TERRITORY} at all")
        return
    
    # Remove duplicates and sort by price
    seen_tiers = {}
    for tier_info in panama_available_tiers:
        tier_code = tier_info['tier_code']
        if tier_code not in seen_tiers or tier_info['price'] > seen_tiers[tier_code]['price']:
            seen_tiers[tier_code] = tier_info
    
    panama_available_tiers = sorted(seen_tiers.values(), key=lambda x: x['price'])
    
    print(f"  ✓ Found {len(panama_available_tiers)} tier(s) available for {TERRITORY}:")
    for tier_info in panama_available_tiers:
        diff = tier_info['price'] - target_price_usd
        status = "✓ ABOVE" if diff >= 0 else "BELOW"
        print(f"    • Tier {tier_info['tier_code']}: ${tier_info['price']:.2f} USD ({status} target by ${abs(diff):.2f})")
    
    # NOW select the best tier from Panama's actual available options
    # Find best tier above target from available tiers
    tiers_above = [t for t in panama_available_tiers if t['price'] >= target_price_usd]
    if tiers_above:
        best_available = min(tiers_above, key=lambda x: x['price'])
        panama_price_point_id = best_available['pp_id']
        actual_price = best_available['price']
        best_tier_code = best_available['tier_code']
        best_price = actual_price
        diff = actual_price - target_price_usd
        print(f"\n  ✓ Selected tier ABOVE target: {best_tier_code} = ${actual_price:.2f} USD (+${diff:.2f} above target)")
    else:
        # Use highest available tier (closest below target)
        best_available = max(panama_available_tiers, key=lambda x: x['price'])
        panama_price_point_id = best_available['pp_id']
        actual_price = best_available['price']
        best_tier_code = best_available['tier_code']
        best_price = actual_price
        diff = target_price_usd - actual_price
        print(f"\n  ⚠️  No tier above target available, using highest: {best_tier_code} = ${actual_price:.2f} USD")
        print(f"  ⚠️  This is ${diff:.2f} below target price")
    
    # Use actual_price if we found it, otherwise use best_price
    final_price = actual_price if actual_price is not None else best_price
    
    # Verify it's different from current
    if panama_price_point_id == current_price_point_id:
        print(f"\n  ⚠️  WARNING: The selected tier is the SAME as current price!")
        print(f"  Current: ${current_price_pa:.2f} USD")
        print(f"  Selected tier: ${final_price:.2f} USD")
        print(f"  Target was: ${target_price_usd:.2f} USD")
        
        if not auto_confirm:
            response = input(f"\n  Proceed anyway with tier {best_tier_code}? (yes/no): ").strip().lower()
            if response != 'yes':
                print("  Cancelled.")
                return
        else:
            print(f"  ⚠️  Skipping - same as current price")
            return
    else:
        print(f"  ✓ Selected tier is different from current (current: ${current_price_pa:.2f} USD, new: ${final_price:.2f} USD)")
    
    # Step 5: Preview and confirm
    print(f"\n{'='*100}")
    print("PREVIEW:")
    print(f"  Territory: {TERRITORY} (Panama)")
    print(f"  Current price: ${current_price_pa:.2f} USD")
    print(f"  Target price: ${target_price_usd:.2f} USD")
    print(f"  Selected tier price: ${final_price:.2f} USD")
    print(f"  Change: ${final_price - current_price_pa:+.2f} USD")
    if final_price < target_price_usd:
        print(f"  ⚠️  Note: Selected price is ${target_price_usd - final_price:.2f} below target (no higher tier available)")
    print(f"  Current price point ID: {current_price_point_id[:50]}...")
    print(f"  New price point ID: {panama_price_point_id[:50]}...")
    print(f"{'='*100}")
    
    # Step 6: Check for existing scheduled price changes and delete if needed
    print(f"\n6. Checking for existing scheduled price changes...")
    endpoint = f"/subscriptions/{SUBSCRIPTION_ID}/prices"
    params = {"include": "subscriptionPricePoint", "limit": 200}
    
    scheduled_price_entry_id = None
    try:
        data = api._make_request(endpoint, params=params)
        prices = data.get("data", [])
        
        for price_entry in prices:
            attrs = price_entry.get("attributes", {})
            price_entry_id = price_entry.get("id")
            territory = decode_price_entry_id(price_entry_id)
            
            if territory == TERRITORY and attrs.get("startDate"):
                scheduled_price_entry_id = price_entry_id
                scheduled_date = attrs.get("startDate")
                print(f"  ⚠️  Found scheduled price change for {TERRITORY} on {scheduled_date}")
                print(f"     Price Entry ID: {price_entry_id}")
                break
    except Exception as e:
        print(f"  ⚠️  Could not check for scheduled prices: {e}")
    
    # Step 7: Create price change
    if auto_confirm:
        response = 'yes'
        if not start_date:
            start_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        print(f"\n  Auto-confirming update (non-interactive mode)...")
    else:
        response = input(f"\nCreate price change for {TERRITORY}? (yes/no): ").strip().lower()
    
    if response == 'yes':
        # Delete existing scheduled price if found
        if scheduled_price_entry_id:
            print(f"\n7. Deleting existing scheduled price change...")
            try:
                api.delete_subscription_price(scheduled_price_entry_id)
                print(f"  ✓ Deleted scheduled price change")
            except Exception as e:
                print(f"  ⚠️  Could not delete scheduled price: {e}")
                print(f"  Will try to create new one anyway...")
        
        print(f"\n8. Creating new price change...")
        if not start_date:
            if auto_confirm:
                start_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
            else:
                start_date_input = input("Start date (YYYY-MM-DD, or Enter for tomorrow): ").strip()
                if start_date_input:
                    try:
                        datetime.strptime(start_date_input, "%Y-%m-%d")
                        start_date = start_date_input
                    except ValueError:
                        print("Invalid date format. Using tomorrow.")
                        start_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
                else:
                    start_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        
        print(f"  Subscription: {SUBSCRIPTION_ID}")
        print(f"  Price Point ID: {panama_price_point_id[:60]}...")
        print(f"  Start Date: {start_date}")
        print()
        
        try:
            result = api.update_subscription_price(
                SUBSCRIPTION_ID,
                panama_price_point_id,
                start_date=start_date
            )
            
            print(f"  ✓ API Response:")
            print(f"    Result: {json.dumps(result, indent=2) if isinstance(result, dict) else result}")
            
            # Check if startDate was set correctly
            if isinstance(result, dict):
                attrs = result.get("attributes", {})
                returned_start_date = attrs.get("startDate")
                if returned_start_date == start_date:
                    print(f"\n  ✓✓✓ SUCCESS: Price change scheduled for {start_date}")
                elif returned_start_date is None:
                    print(f"\n  ⚠️  WARNING: API returned startDate: null")
                    print(f"  This might mean the price point is already the current price.")
                else:
                    print(f"\n  ✓ Price change scheduled for {returned_start_date}")
            
        except Exception as e:
            print(f"  ❌ Error: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("Cancelled.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Update Panama subscription price")
    parser.add_argument("--yes", "-y", action="store_true", help="Auto-confirm without prompting")
    parser.add_argument("--start-date", "-d", type=str, help="Start date (YYYY-MM-DD), defaults to tomorrow")
    
    args = parser.parse_args()
    
    main(auto_confirm=args.yes, start_date=args.start_date)

