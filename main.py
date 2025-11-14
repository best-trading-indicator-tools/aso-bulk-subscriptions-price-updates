#!/usr/bin/env python3
"""
Main script to scan subscription products, calculate Big Mac Index-based prices,
and perform bulk updates
"""
import json
import sys
from appstore_api import AppStoreConnectAPI
from price_calculator import PriceCalculator
import config

def scan_subscriptions():
    """Scan and list all subscription products"""
    api = AppStoreConnectAPI()
    app_id = config.APP_ID
    
    print(f"Scanning subscription products for app {app_id}...\n")
    
    try:
        groups = api.get_subscription_groups(app_id)
        print(f"Found {len(groups)} subscription group(s)\n")
        
        all_subscriptions = []
        
        for group in groups:
            group_id = group["id"]
            group_name = group.get("attributes", {}).get("referenceName", "Unknown")
            
            subscriptions = api.get_subscriptions_in_group(group_id)
            
            for sub in subscriptions:
                sub_id = sub["id"]
                sub_attrs = sub.get("attributes", {})
                sub_name = sub_attrs.get("name", "Unknown")
                sub_product_id = sub_attrs.get("productId", "Unknown")
                sub_state = sub_attrs.get("subscriptionState", "Unknown")
                
                # Get prices
                try:
                    prices = api.get_subscription_prices(sub_id)
                    
                    subscription_info = {
                        "id": sub_id,
                        "name": sub_name,
                        "productId": sub_product_id,
                        "state": sub_state,
                        "groupName": group_name,
                        "groupId": group_id,
                        "prices": prices
                    }
                    all_subscriptions.append(subscription_info)
                    
                except Exception as e:
                    print(f"  Error fetching prices for {sub_name}: {e}")
        
        # Save to JSON
        output_file = "subscriptions.json"
        with open(output_file, 'w') as f:
            json.dump(all_subscriptions, f, indent=2)
        
        print(f"\n✓ Found {len(all_subscriptions)} subscription product(s)")
        print(f"✓ Details saved to {output_file}\n")
        
        # Print summary
        print("="*100)
        print("SUBSCRIPTION PRODUCTS")
        print("="*100)
        print(f"{'#':<4} {'Name':<40} {'Product ID':<30} {'State':<15} {'Prices':<10}")
        print("-"*100)
        
        for idx, sub in enumerate(all_subscriptions, 1):
            price_count = len(sub.get('prices', []))
            print(f"{idx:<4} {sub['name']:<40} {sub['productId']:<30} {sub['state']:<15} {price_count:<10}")
        
        return all_subscriptions
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return []

def show_price_preview(subscription_id: str, subscription_name: str, base_price: float):
    """Show price preview for a subscription"""
    api = AppStoreConnectAPI()
    calculator = PriceCalculator()
    
    print(f"\nCalculating prices for: {subscription_name}")
    print(f"Base price: ${base_price:.2f} {config.BASE_CURRENCY}\n")
    
    # Get current prices
    prices = api.get_subscription_prices(subscription_id)
    
    if not prices:
        print("No prices found for this subscription.")
        return None
    
    # Generate comparison report
    # Note: We need to parse the price data structure from API
    # For now, we'll calculate based on available territories
    print("Price Preview (Current vs Proposed):")
    print("="*100)
    print(f"{'Territory':<15} {'Current Price':<20} {'Proposed Price':<20} {'Ratio':<15} {'Status':<15}")
    print("-"*100)
    
    # Get all ratios
    all_ratios = calculator.bigmac.get_all_ratios()
    
    preview_data = []
    for price_entry in prices:
        # Parse price entry structure
        price_point = price_entry.get('relationships', {}).get('subscriptionPricePoint', {}).get('data', {})
        price_point_id = price_point.get('id')
        
        # Get territory from included data if available
        # For now, we'll need to make another call or parse differently
        # This is a simplified version
        
        territory = "Unknown"
        current_price = 0
        
        # Calculate proposed price
        ratio = all_ratios.get(territory)
        proposed_price = base_price * ratio if ratio else None
        
        preview_data.append({
            'territory': territory,
            'current_price': current_price,
            'proposed_price': proposed_price,
            'ratio': ratio,
            'price_point_id': price_point_id
        })
    
    return preview_data

def main():
    print("="*100)
    print("ASO Pricing Update Tool - Big Mac Index Based")
    print("="*100)
    print()
    
    # Step 1: Scan subscriptions
    subscriptions = scan_subscriptions()
    
    if not subscriptions:
        print("No subscriptions found. Exiting.")
        return
    
    print("\n" + "="*100)
    print("Next steps:")
    print("1. Review the subscription products listed above")
    print("2. Tell me which subscription product IDs you want to update")
    print("3. Provide the base price (USD) for each subscription")
    print("="*100)

if __name__ == "__main__":
    main()

