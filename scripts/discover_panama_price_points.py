#!/usr/bin/env python3
"""
Discover ALL available price points for Panama by checking multiple tiers
This mimics what the website UI shows - all selectable price points
"""
import sys
import os
import json
import base64

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from appstore_api import AppStoreConnectAPI
from update_prices import decode_price_point_id, encode_price_point_id

SUBSCRIPTION_ID = "6743152682"
TERRITORY = "PAN"  # 3-letter code for price points

def decode_price_point_id(price_point_id):
    """Decode price point ID"""
    try:
        padded = price_point_id + '=='
        decoded = base64.urlsafe_b64decode(padded)
        data = json.loads(decoded)
        return {
            'subscription_id': data.get('s', ''),
            'territory': data.get('t', ''),
            'tier_code': data.get('p', '')
        }
    except:
        return None

def encode_price_point_id(subscription_id, territory, tier_code):
    """Encode price point ID"""
    try:
        data = {
            's': subscription_id,
            't': territory,
            'p': tier_code
        }
        json_str = json.dumps(data, separators=(',', ':'))
        encoded = base64.urlsafe_b64encode(json_str.encode()).decode().rstrip('=')
        return encoded
    except:
        return None

def check_price_point_exists(api, price_point_id):
    """Check if a price point exists by trying to fetch it"""
    try:
        endpoint = f"/subscriptionPricePoints/{price_point_id}"
        data = api._make_request(endpoint)
        if data.get('data'):
            attrs = data['data'].get('attributes', {})
            price = float(attrs.get('customerPrice', '0'))
            return True, price
        return False, None
    except Exception as e:
        # 404 means it doesn't exist
        if '404' in str(e) or 'not found' in str(e).lower():
            return False, None
        # Other errors might mean it exists but we can't access it
        return None, None

def main():
    print("="*100)
    print("Discovering ALL Available Price Points for Panama")
    print("="*100)
    
    api = AppStoreConnectAPI()
    
    # Strategy 1: Get all price points from subscription prices endpoint
    print("\n1. Fetching all price points currently used in subscription...")
    all_used_price_points = {}
    cursor = None
    
    while True:
        endpoint = f"/subscriptions/{SUBSCRIPTION_ID}/prices"
        params = {"include": "subscriptionPricePoint", "limit": 200}
        if cursor:
            params["cursor"] = cursor
        
        data = api._make_request(endpoint, params=params)
        included = data.get("included", [])
        
        for item in included:
            if item.get("type") == "subscriptionPricePoints":
                pp_id = item.get("id")
                attrs = item.get("attributes", {})
                price = float(attrs.get("customerPrice", "0"))
                decoded = decode_price_point_id(pp_id)
                
                if decoded and decoded['territory'] == TERRITORY:
                    all_used_price_points[decoded['tier_code']] = {
                        'pp_id': pp_id,
                        'price': price,
                        'tier_code': decoded['tier_code']
                    }
        
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
    
    print(f"  Found {len(all_used_price_points)} price points currently used for Panama")
    
    # Strategy 2: Try common tier codes to see if they exist for Panama
    print("\n2. Testing common tier codes for Panama...")
    print("   (This checks if price points exist even if not currently used)")
    
    # Common tier codes around our target price ($51.63)
    # Based on what we saw: 10240 ($49.99), 10250 ($56.57), 10325 ($49.90), etc.
    test_tiers = [
        "10240", "10248", "10250", "10300", "10325", "10345", "10356", "10369",
        "10200", "10210", "10220", "10230", "10260", "10270", "10280", "10290",
        "10310", "10320", "10330", "10340", "10350", "10360", "10370", "10380"
    ]
    
    discovered_price_points = {}
    
    for tier_code in test_tiers:
        pp_id = encode_price_point_id(SUBSCRIPTION_ID, TERRITORY, tier_code)
        if pp_id:
            exists, price = check_price_point_exists(api, pp_id)
            if exists:
                discovered_price_points[tier_code] = {
                    'pp_id': pp_id,
                    'price': price,
                    'tier_code': tier_code
                }
                print(f"  ✓ Tier {tier_code}: ${price:.2f} USD")
    
    # Strategy 3: Check equalizations from a known price point
    print("\n3. Checking equalizations from current Panama price point...")
    if all_used_price_points:
        current_tier = list(all_used_price_points.keys())[0]
        current_pp_id = all_used_price_points[current_tier]['pp_id']
        
        try:
            eq_endpoint = f"/subscriptionPricePoints/{current_pp_id}/equalizations"
            eq_params = {"limit": 200}
            all_equalizations = []
            eq_cursor = None
            
            while True:
                if eq_cursor:
                    eq_params['cursor'] = eq_cursor
                eq_data = api._make_request(eq_endpoint, params=eq_params)
                equalizations = eq_data.get('data', [])
                all_equalizations.extend(equalizations)
                
                links = eq_data.get('links', {})
                next_url = links.get('next')
                if next_url and 'cursor=' in next_url:
                    new_cursor = next_url.split('cursor=')[-1].split('&')[0]
                    if eq_cursor != new_cursor:
                        eq_cursor = new_cursor
                    else:
                        break
                else:
                    break
            
            panama_from_eq = []
            for eq in all_equalizations:
                eq_pp_id = eq.get('id')
                decoded = decode_price_point_id(eq_pp_id)
                if decoded and decoded['territory'] == TERRITORY:
                    price = float(eq.get('attributes', {}).get('customerPrice', '0'))
                    panama_from_eq.append({
                        'pp_id': eq_pp_id,
                        'price': price,
                        'tier_code': decoded['tier_code']
                    })
            
            print(f"  Found {len(panama_from_eq)} Panama price points from equalizations")
            for pp in panama_from_eq:
                if pp['tier_code'] not in discovered_price_points:
                    discovered_price_points[pp['tier_code']] = pp
                    print(f"  ✓ Tier {pp['tier_code']}: ${pp['price']:.2f} USD (from equalizations)")
        except Exception as e:
            print(f"  ⚠️  Error checking equalizations: {e}")
    
    # Combine all discovered price points
    all_panama_price_points = {**all_used_price_points, **discovered_price_points}
    
    # Sort by price
    sorted_points = sorted(all_panama_price_points.values(), key=lambda x: x['price'])
    
    print(f"\n{'='*100}")
    print(f"SUMMARY: All Available Price Points for Panama")
    print(f"{'='*100}")
    print(f"{'Tier':<10} {'Price (USD)':<15} {'Price Point ID':<60}")
    print("-"*100)
    
    for pp in sorted_points:
        print(f"{pp['tier_code']:<10} ${pp['price']:<14.2f} {pp['pp_id'][:60]}...")
    
    print(f"\nTotal: {len(sorted_points)} price points available for Panama")
    
    # Show target price context
    target_price = 51.63
    print(f"\nTarget price: ${target_price:.2f} USD")
    print("\nPrice points ABOVE target:")
    above_target = [pp for pp in sorted_points if pp['price'] >= target_price]
    if above_target:
        for pp in above_target:
            diff = pp['price'] - target_price
            print(f"  • Tier {pp['tier_code']}: ${pp['price']:.2f} USD (+${diff:.2f})")
    else:
        print("  None found")
    
    print("\nPrice points BELOW target (closest):")
    below_target = [pp for pp in sorted_points if pp['price'] < target_price]
    if below_target:
        for pp in below_target[-5:]:  # Show 5 closest below
            diff = target_price - pp['price']
            print(f"  • Tier {pp['tier_code']}: ${pp['price']:.2f} USD (-${diff:.2f})")

if __name__ == "__main__":
    main()

