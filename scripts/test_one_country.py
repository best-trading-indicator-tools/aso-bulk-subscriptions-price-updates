#!/usr/bin/env python3
"""
Test price calculation for one subscription and one country
"""
import json
import base64
from appstore_api import AppStoreConnectAPI
from price_calculator import PriceCalculator
from exchange_rates import ExchangeRates
import config

# Test configuration
TEST_SUBSCRIPTION_ID = "6743152682"  # Annual Subscription
TEST_SUBSCRIPTION_NAME = "Annual Subscription"
TEST_COUNTRY = "PA"  # Panama - using fallback ratio
TEST_COUNTRY_NAME = "Panama"

def get_territory_currency(territory_code: str) -> str:
    """Get currency code for a territory"""
    # Common territory to currency mappings
    territory_currency_map = {
        'US': 'USD', 'PA': 'USD',  # Panama uses USD
        'GB': 'GBP', 'CA': 'CAD', 'AU': 'AUD', 'NZ': 'NZD',
        'JP': 'JPY', 'CN': 'CNY', 'KR': 'KRW', 'TW': 'TWD',
        'IN': 'INR', 'BR': 'BRL', 'MX': 'MXN', 'AR': 'ARS',
        'CL': 'CLP', 'CO': 'COP', 'PE': 'PEN', 'CR': 'CRC',
        'UY': 'UYU', 'ZA': 'ZAR', 'SG': 'SGD', 'MY': 'MYR',
        'TH': 'THB', 'PH': 'PHP', 'ID': 'IDR', 'VN': 'VND',
        'HK': 'HKD', 'TR': 'TRY', 'RU': 'RUB', 'IL': 'ILS',
        'AE': 'AED', 'SA': 'SAR', 'QA': 'QAR', 'KW': 'KWD',
        'BH': 'BHD', 'OM': 'OMN', 'EG': 'EGP', 'NG': 'NGN',
        'KE': 'KES',
        # Eurozone countries
        'AT': 'EUR', 'BE': 'EUR', 'NL': 'EUR', 'FI': 'EUR',
        'IE': 'EUR', 'PT': 'EUR', 'GR': 'EUR', 'LU': 'EUR',
        'MT': 'EUR', 'CY': 'EUR', 'SI': 'EUR', 'SK': 'EUR',
        'EE': 'EUR', 'LV': 'EUR', 'LT': 'EUR', 'HR': 'EUR',
        'DE': 'EUR', 'FR': 'EUR', 'IT': 'EUR', 'ES': 'EUR',
        'AD': 'EUR', 'MC': 'EUR', 'SM': 'EUR',
        # Other European
        'CH': 'CHF', 'SE': 'SEK', 'NO': 'NOK', 'DK': 'DKK',
        'PL': 'PLN', 'CZ': 'CZK', 'HU': 'HUF', 'RO': 'RON',
        'BG': 'BGN', 'IS': 'ISK',
    }
    return territory_currency_map.get(territory_code, 'USD')

def decode_price_entry_id(price_entry_id):
    """Decode price entry ID to extract territory"""
    try:
        padded = price_entry_id + '=='
        decoded = base64.urlsafe_b64decode(padded)
        data = json.loads(decoded)
        return data.get('c', '')
    except:
        return None

def get_price_details(api, subscription_id):
    """Get detailed price information including territories"""
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
        next_link = links.get("next")
        if next_link:
            # Extract cursor from next link
            import urllib.parse
            parsed = urllib.parse.urlparse(next_link)
            query_params = urllib.parse.parse_qs(parsed.query)
            cursor = query_params.get("cursor", [None])[0]
            if not cursor:
                break
        else:
            break
    
    # Build price point map
    price_point_map = {}
    for item in all_included:
        if item.get("type") == "subscriptionPricePoints":
            price_point_id = item.get("id")
            attrs = item.get("attributes", {})
            customer_price_str = attrs.get("customerPrice", "0")
            
            try:
                price_value = float(customer_price_str)
            except:
                price_value = 0
            
            price_point_map[price_point_id] = {
                "id": price_point_id,
                "price": price_value
            }
    
    # Build price details
    price_details = []
    for price_entry in all_prices:
        attrs = price_entry.get("attributes", {})
        start_date = attrs.get("startDate")
        preserved = attrs.get("preserved", False)
        
        # Only get active prices (no start date and not preserved)
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
                    detail["currency"] = get_territory_currency(territory)
                    price_details.append(detail)
    
    return price_details

def get_usa_base_price(price_details):
    """Get USA base price from price details"""
    for detail in price_details:
        if detail.get("territory") in ["US", "USA"]:
            return detail.get("price", 0)
    return None

def main():
    print("="*100)
    print(f"TEST: Price Calculation for {TEST_COUNTRY_NAME} ({TEST_COUNTRY})")
    print("="*100)
    print(f"\nSubscription: {TEST_SUBSCRIPTION_NAME} (ID: {TEST_SUBSCRIPTION_ID})")
    print(f"Country: {TEST_COUNTRY_NAME} ({TEST_COUNTRY})\n")
    
    # Initialize
    api = AppStoreConnectAPI()
    calculator = PriceCalculator()
    exchange_rates = ExchangeRates()
    
    # Get current prices
    print("1. Fetching current prices...")
    price_details = get_price_details(api, TEST_SUBSCRIPTION_ID)
    
    if not price_details:
        print("   ❌ No prices found.")
        return
    
    print(f"   ✓ Found {len(price_details)} price points")
    
    # Get USA base price
    usa_price = get_usa_base_price(price_details)
    if usa_price is None or usa_price == 0:
        print("   ❌ Could not find USA base price.")
        return
    
    print(f"   ✓ USA base price: ${usa_price:.2f} USD")
    
    # Get country current price
    country_detail = None
    for detail in price_details:
        if detail.get("territory") == TEST_COUNTRY:
            country_detail = detail
            break
    
    if country_detail:
        current_price = country_detail.get("price", 0)
        currency = country_detail.get("currency", "")
        print(f"   ✓ {TEST_COUNTRY_NAME} current price: {current_price:.2f} {currency}")
    else:
        print(f"   ⚠ No current price found for {TEST_COUNTRY_NAME} (will calculate new price)")
    
    # Get Big Mac Index ratio
    print(f"\n2. Fetching Big Mac Index ratio for {TEST_COUNTRY_NAME}...")
    all_ratios = calculator.bigmac.get_all_ratios()
    ratio = all_ratios.get(TEST_COUNTRY)
    
    if ratio is None:
        ratio = calculator.bigmac.get_country_ratio(TEST_COUNTRY)
    
    if ratio is None:
        print(f"   ❌ No ratio available for {TEST_COUNTRY_NAME}.")
        return
    
    ratio_source = "Big Mac Index (direct)" if TEST_COUNTRY in ['QA', 'KW', 'BH', 'OM', 'SA', 'SG', 'JP', 'CR', 'UY'] else "Fallback ratio (estimated)"
    print(f"   ✓ Ratio: {ratio:.4f} ({ratio_source})")
    
    # Calculate new price
    print(f"\n3. Calculating new price...")
    new_price_usd = usa_price * ratio
    print(f"   Base price (USD): ${usa_price:.2f}")
    print(f"   Ratio: {ratio:.4f}")
    print(f"   New price (USD): ${new_price_usd:.2f}")
    
    # Get exchange rate for local currency
    if country_detail:
        local_currency = country_detail.get("currency", "")
        if local_currency and local_currency != "USD":
            print(f"\n4. Converting to local currency ({local_currency})...")
            if exchange_rates.fetch_current_rates():
                rate = exchange_rates.get_rate(local_currency)
                if rate:
                    new_price_local = new_price_usd * rate
                    print(f"   Exchange rate: 1 USD = {rate:.4f} {local_currency}")
                    print(f"   New price ({local_currency}): {new_price_local:.2f}")
                    if country_detail:
                        current_price = country_detail.get("price", 0)
                        change = new_price_local - current_price
                        change_pct = (change / current_price * 100) if current_price > 0 else 0
                        print(f"   Current price: {current_price:.2f} {local_currency}")
                        print(f"   Change: {change:+.2f} {local_currency} ({change_pct:+.1f}%)")
    
    print(f"\n{'='*100}")
    print("TEST COMPLETE")
    print(f"{'='*100}")

if __name__ == "__main__":
    main()

