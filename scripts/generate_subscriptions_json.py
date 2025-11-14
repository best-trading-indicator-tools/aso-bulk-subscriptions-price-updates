#!/usr/bin/env python3
"""
Generate subscriptions.json file from App Store Connect API
Reads configuration from .env file via config.py
"""
import json
import sys
import os

# Add parent directory to path to import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from appstore_api import AppStoreConnectAPI

def generate_subscriptions_json(output_file="subscriptions.json"):
    """
    Generate subscriptions.json file with all subscription data
    
    Args:
        output_file: Path to output JSON file (default: subscriptions.json in root)
    """
    print("="*100)
    print("Generating subscriptions.json")
    print("="*100)
    print(f"\nApp ID: {config.APP_ID}")
    print(f"Output file: {output_file}\n")
    
    # Validate configuration
    if not config.APP_ID:
        print("❌ Error: APP_ID not set in .env file")
        return False
    
    if not config.ISSUER_ID or not config.KEY_ID:
        print("❌ Error: App Store Connect API credentials not set in .env file")
        print("   Required: ISSUER_ID, KEY_ID, PRIVATE_KEY_PATH")
        return False
    
    api = AppStoreConnectAPI()
    app_id = config.APP_ID
    
    print(f"Fetching subscription products for app {app_id}...\n")
    
    try:
        # Get all subscription groups
        groups = api.get_subscription_groups(app_id)
        print(f"✓ Found {len(groups)} subscription group(s)\n")
        
        all_subscriptions = []
        
        for group in groups:
            group_id = group["id"]
            group_name = group.get("attributes", {}).get("referenceName", "Unknown")
            print(f"Group: {group_name} (ID: {group_id})")
            
            # Get subscriptions in this group
            subscriptions = api.get_subscriptions_in_group(group_id)
            print(f"  Found {len(subscriptions)} subscription(s) in this group")
            
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
                    
                    print(f"    ✓ {sub_name} ({sub_product_id})")
                    
                except Exception as e:
                    print(f"    ✗ Error fetching details for {sub_name}: {e}")
        
        # Save to JSON file
        output_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), output_file)
        with open(output_path, 'w') as f:
            json.dump(all_subscriptions, f, indent=2)
        
        print(f"\n{'='*100}")
        print(f"✓ Successfully generated {output_file}")
        print(f"✓ Found {len(all_subscriptions)} total subscription product(s)")
        print(f"✓ File saved to: {output_path}")
        print(f"{'='*100}")
        
        # Print summary table
        print("\nSUBSCRIPTION PRODUCTS SUMMARY")
        print("="*100)
        print(f"{'Name':<40} {'Product ID':<30} {'State':<15} {'ID':<40}")
        print("-"*100)
        for sub in all_subscriptions:
            print(f"{sub['name']:<40} {sub['productId']:<30} {sub['state']:<15} {sub['id']:<40}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Generate subscriptions.json from App Store Connect API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate subscriptions.json in root directory (default)
  python3 scripts/generate_subscriptions_json.py
  
  # Generate with custom filename
  python3 scripts/generate_subscriptions_json.py --output my_subscriptions.json
        """
    )
    
    parser.add_argument(
        "--output", "-o",
        default="subscriptions.json",
        help="Output filename (default: subscriptions.json)"
    )
    
    args = parser.parse_args()
    
    success = generate_subscriptions_json(args.output)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()

