#!/usr/bin/env python3
"""
Update price for Panama only - Annual Subscription
"""
from appstore_api import AppStoreConnectAPI
from price_calculator import PriceCalculator
from exchange_rates import ExchangeRates
from update_prices import get_price_details, get_usa_base_price, find_nearest_price_tier, decode_price_entry_id

# Configuration
SUBSCRIPTION_ID = "6743152682"  # Annual Subscription
SUBSCRIPTION_NAME = "Annual Subscription"
TARGET_TERRITORY = "PA"  # Panama
# Start date must be in the future - cannot create immediate price changes after subscription is approved
from datetime import datetime, timedelta
START_DATE = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")  # Tomorrow

def main():
    print("="*100)
    print(f"Updating price for {TARGET_TERRITORY} - {SUBSCRIPTION_NAME}")
    print("="*100)
    
    api = AppStoreConnectAPI()
    calculator = PriceCalculator()
    exchange_rates = ExchangeRates()
    
    # Get current price details
    print("\n1. Fetching current prices...")
    price_details = get_price_details(api, SUBSCRIPTION_ID)
    
    if not price_details:
        print("  ❌ No prices found.")
        return
    
    print(f"  ✓ Found {len(price_details)} price points")
    
    # Get USA base price
    usa_price = get_usa_base_price(price_details)
    if usa_price is None or usa_price == 0:
        print("  ❌ Could not find USA base price.")
        return
    
    print(f"  ✓ USA base price: ${usa_price:.2f} USD")
    
    # Find Panama price detail
    panama_detail = None
    for detail in price_details:
        if detail.get("territory") == TARGET_TERRITORY:
            panama_detail = detail
            break
    
    if not panama_detail:
        print(f"  ❌ No current price found for {TARGET_TERRITORY}.")
        return
    
    current_price = panama_detail.get("price", 0)
    print(f"  ✓ {TARGET_TERRITORY} current price: ${current_price:.2f} USD")
    
    # Get Big Mac Index ratio
    print(f"\n2. Fetching Big Mac Index ratio for {TARGET_TERRITORY}...")
    all_ratios = calculator.bigmac.get_all_ratios()
    ratio = all_ratios.get(TARGET_TERRITORY)
    
    if ratio is None:
        ratio = calculator.bigmac.get_country_ratio(TARGET_TERRITORY)
    
    if ratio is None:
        print(f"  ❌ No ratio available for {TARGET_TERRITORY}.")
        return
    
    print(f"  ✓ Ratio: {ratio:.4f}")
    
    # Calculate new price
    print(f"\n3. Calculating new price...")
    new_price_usd = usa_price * ratio
    print(f"  Base price (USD): ${usa_price:.2f}")
    print(f"  Ratio: {ratio:.4f}")
    print(f"  New price (USD): ${new_price_usd:.2f}")
    print(f"  Current price (USD): ${current_price:.2f}")
    print(f"  Change: ${new_price_usd - current_price:+.2f} USD")
    
    # Get exchange rates
    print(f"\n4. Fetching exchange rates...")
    if not exchange_rates.fetch_current_rates():
        print("  ⚠ Warning: Could not fetch exchange rates.")
    
    # Find nearest price tier
    print(f"\n5. Finding nearest price tier...")
    nearest_tier_id = find_nearest_price_tier(
        api, SUBSCRIPTION_ID, new_price_usd, TARGET_TERRITORY, price_details, exchange_rates
    )
    
    if not nearest_tier_id:
        print("  ❌ Could not find matching price tier.")
        return
    
    print(f"  ✓ Found price tier: {nearest_tier_id}")
    
    # Preview
    print(f"\n{'='*100}")
    print("PREVIEW:")
    print(f"  Territory: {TARGET_TERRITORY}")
    print(f"  Current price: ${current_price:.2f} USD")
    print(f"  New price: ${new_price_usd:.2f} USD")
    print(f"  Change: ${new_price_usd - current_price:+.2f} USD")
    print(f"  Effective: {START_DATE or 'Immediate'}")
    print(f"{'='*100}")
    
    # Ask for confirmation (auto-confirm if running non-interactively)
    import sys
    if sys.stdin.isatty():
        response = input(f"\nUpdate price for {TARGET_TERRITORY}? (yes/no): ").strip().lower()
        if response != 'yes':
            print("  Cancelled.")
            return
    else:
        print(f"\n  Auto-confirming update for {TARGET_TERRITORY}...")
    
    # Update price
    print(f"\n6. Updating price...")
    try:
        result = api.update_subscription_price(
            SUBSCRIPTION_ID,
            nearest_tier_id,
            start_date=START_DATE
        )
        print(f"  ✓ Successfully updated price for {TARGET_TERRITORY}!")
        print(f"  ✓ Price change effective: {START_DATE or 'Immediate'}")
        print(f"\n  You should see this change in App Store Connect shortly.")
    except Exception as e:
        print(f"  ❌ Error updating price: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

