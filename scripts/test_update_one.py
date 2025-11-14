#!/usr/bin/env python3
"""Test updating one subscription"""
import json
import base64
from appstore_api import AppStoreConnectAPI
from price_calculator import PriceCalculator
import config

def decode_price_entry_id(price_entry_id):
    """Decode price entry ID to extract territory"""
    try:
        padded = price_entry_id + '=='
        decoded = base64.urlsafe_b64decode(padded)
        data = json.loads(decoded)
        return data.get('c', '')
    except:
        return None

api = AppStoreConnectAPI()
calculator = PriceCalculator()
subscription_id = "6743152682"  # Annual Subscription
subscription_name = "Annual Subscription"

print(f"Testing price update for: {subscription_name} (ID: {subscription_id})")
print("="*100)

# Get price details
print("Fetching prices...")
endpoint = f"/subscriptions/{subscription_id}/prices"
params = {
    "include": "subscriptionPricePoint",
    "limit": 10  # Just test with first 10
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
        customer_price_str = attrs.get("customerPrice", "0")
        try:
            price = float(customer_price_str)
        except:
            price = 0
        price_point_map[price_point_id] = {"id": price_point_id, "price": price}

# Get territories and prices
price_details = []
for price_entry in prices:
    attrs = price_entry.get("attributes", {})
    start_date = attrs.get("startDate")
    preserved = attrs.get("preserved", False)
    
    if start_date is None and not preserved:
        price_entry_id = price_entry.get("id")
        territory = decode_price_entry_id(price_entry_id)
        
        if territory:
            price_point_ref = price_entry.get("relationships", {}).get("subscriptionPricePoint", {}).get("data", {})
            price_point_id = price_point_ref.get("id")
            
            if price_point_id in price_point_map:
                detail = price_point_map[price_point_id].copy()
                detail["territory"] = territory
                detail["price_entry_id"] = price_entry_id
                price_details.append(detail)

print(f"\nFound {len(price_details)} active price points")
print("\nSample territories and prices:")
for detail in price_details[:10]:
    print(f"  {detail['territory']}: ${detail['price']:.2f}")

# Get USA price
usa_price = None
for detail in price_details:
    if detail.get("territory") == "US":
        usa_price = detail.get("price")
        break

if usa_price:
    print(f"\nUSA base price: ${usa_price:.2f}")
    
    # Get ratios
    all_ratios = calculator.bigmac.get_all_ratios()
    print(f"\nBig Mac Index ratios available for {len(all_ratios)} countries")
    
    # Show sample calculations
    print("\nSample price calculations:")
    print(f"{'Territory':<15} {'Current':<15} {'Ratio':<15} {'New Price':<15}")
    print("-"*60)
    for detail in price_details[:10]:
        territory = detail.get("territory")
        current = detail.get("price")
        ratio = all_ratios.get(territory)
        if ratio:
            new_price = usa_price * ratio
            print(f"{territory:<15} ${current:<14.2f} {ratio:<15.3f} ${new_price:<14.2f}")
else:
    print("\nCould not find USA price. Looking for US...")
    for detail in price_details:
        if detail.get("territory") == "USA":
            usa_price = detail.get("price")
            print(f"Found USA price: ${usa_price:.2f}")
            break

