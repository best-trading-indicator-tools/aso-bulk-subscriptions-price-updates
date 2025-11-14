#!/usr/bin/env python3
"""
List all active subscription products for the app
"""
import json
import config
from appstore_api import AppStoreConnectAPI

def main():
    api = AppStoreConnectAPI()
    app_id = config.APP_ID
    
    print(f"Fetching subscription products for app {app_id}...\n")
    
    # Get all subscription groups
    try:
        groups = api.get_subscription_groups(app_id)
        print(f"Found {len(groups)} subscription group(s)\n")
        
        all_subscriptions = []
        
        for group in groups:
            group_id = group["id"]
            group_name = group.get("attributes", {}).get("referenceName", "Unknown")
            print(f"Group: {group_name} (ID: {group_id})")
            
            # Get subscriptions in this group
            subscriptions = api.get_subscriptions_in_group(group_id)
            print(f"  Found {len(subscriptions)} subscription(s) in this group\n")
            
            for sub in subscriptions:
                sub_id = sub["id"]
                sub_attrs = sub.get("attributes", {})
                sub_name = sub_attrs.get("name", "Unknown")
                sub_product_id = sub_attrs.get("productId", "Unknown")
                sub_state = sub_attrs.get("subscriptionState", "Unknown")
                
                # Get detailed subscription info including prices
                try:
                    details = api.get_subscription_details(sub_id)
                    prices = api.get_subscription_prices(sub_id)
                    
                    subscription_info = {
                        "id": sub_id,
                        "name": sub_name,
                        "productId": sub_product_id,
                        "state": sub_state,
                        "groupName": group_name,
                        "groupId": group_id,
                        "prices": prices,
                        "details": details
                    }
                    all_subscriptions.append(subscription_info)
                    
                    print(f"  - {sub_name}")
                    print(f"    Product ID: {sub_product_id}")
                    print(f"    State: {sub_state}")
                    print(f"    Subscription ID: {sub_id}")
                    print(f"    Prices: {len(prices)} price point(s)")
                    print()
                    
                except Exception as e:
                    print(f"    Error fetching details: {e}\n")
        
        # Save to JSON file for reference
        output_file = "subscriptions.json"
        with open(output_file, 'w') as f:
            json.dump(all_subscriptions, f, indent=2)
        
        print(f"\n✓ Found {len(all_subscriptions)} total subscription product(s)")
        print(f"✓ Details saved to {output_file}")
        
        # Print summary table
        print("\n" + "="*80)
        print("SUBSCRIPTION PRODUCTS SUMMARY")
        print("="*80)
        print(f"{'Name':<30} {'Product ID':<30} {'State':<15} {'ID':<40}")
        print("-"*80)
        for sub in all_subscriptions:
            print(f"{sub['name']:<30} {sub['productId']:<30} {sub['state']:<15} {sub['id']:<40}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

