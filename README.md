# ASO Pricing - Big Mac Index Based Subscription Pricing

Automate subscription price updates for App Store Connect using the Big Mac Index to calculate purchasing power parity (PPP) adjusted prices across all territories.

## Overview

This tool calculates optimal subscription prices for different countries/territories based on the Big Mac Index, which measures purchasing power parity. It keeps your US base price unchanged and applies PPP-adjusted multipliers to all other territories, ensuring your pricing is fair and competitive globally.

## Features

- 🍔 **Big Mac Index Integration**: Automatically fetches the latest Big Mac Index data from The Economist
- 💰 **PPP-Based Pricing**: Calculates prices based on purchasing power parity
- 🌍 **Multi-Territory Support**: Handles all App Store territories with fallback ratios for countries without Big Mac data
- 📊 **Price Preview**: See calculated prices before applying changes
- 🔄 **Bulk Updates**: Update multiple subscriptions at once
- 📅 **Scheduled Changes**: Schedule price changes for future dates
- 🔐 **App Store Connect API**: Full integration with Apple's API

## Prerequisites

- Python 3.8+
- App Store Connect API Key (.p8 file)
- App Store Connect API credentials (Issuer ID, Key ID)
- App ID for your app

## Installation

1. Clone the repository:
```bash
git clone <your-repo-url>
cd aso-pricing
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure your credentials:
   - Copy `.env.example` to `.env`:
     ```bash
     cp .env.example .env
     ```
   - Edit `.env` and fill in your App Store Connect API credentials:
     ```bash
     APP_ID=your-app-id
     ISSUER_ID=your-issuer-id
     KEY_ID=your-key-id
     PRIVATE_KEY_PATH=AuthKey_XXXXX.p8
     ```

4. Place your App Store Connect API private key file (`AuthKey_XXXXX.p8`) in the root directory.

## Project Structure

```
aso-pricing/
├── README.md                 # This file
├── requirements.txt          # Python dependencies
├── .env.example              # Environment variables template
├── .env                      # Your credentials (gitignored, create from .env.example)
├── config.py                # Configuration (reads from .env)
├── auth.py                  # JWT token generation for API auth
├── appstore_api.py          # App Store Connect API client
├── bigmac_index.py          # Big Mac Index data fetcher and calculator
├── price_calculator.py      # Price calculation logic
├── exchange_rates.py         # Exchange rate fetcher
├── main.py                  # Main script (scan & preview)
├── list_subscriptions.py    # List all subscriptions
├── update_prices.py         # Bulk price update script
├── subscriptions.json        # Optional: Generated reference file (gitignored)
└── scripts/                 # Test and utility scripts
    ├── README.md
    ├── test_one_country.py  # Test price calculation for one country
    ├── update_panama.py     # Example: Update single territory
    ├── check_scheduled_prices.py  # Check scheduled price changes
    ├── check_currency.py    # Check currency information
    ├── check_territories.py # List available territories
    ├── decode_price_id.py   # Decode price entry IDs
    ├── test_albania.py      # Test script for single territory
    ├── test_price_structure.py  # Inspect API response structure
    └── test_update_one.py   # Test updating single subscription
```

## Usage

### 1. List All Subscriptions

View all subscription products for your app:

```bash
python3 list_subscriptions.py
```

Or use the dedicated script in the scripts folder:

```bash
python3 scripts/generate_subscriptions_json.py
```

This will:
- List all subscription groups and products
- Show current prices
- **Optionally save details to `subscriptions.json`** - This file contains all subscription metadata including IDs, names, product IDs, states, and price information.

**Important**: The `subscriptions.json` file is **NOT required** for the tool to function. All scripts fetch data directly from the App Store Connect API. This file is:
- **Optional** - Only created if you run `list_subscriptions.py` or `generate_subscriptions_json.py`
- **For reference only** - Useful for viewing subscription IDs and metadata offline
- **Gitignored** - Excluded from git via `.gitignore` since it contains app-specific data
- **Not used by other scripts** - All price update scripts fetch data directly from the API

To generate it, run:
```bash
python3 scripts/generate_subscriptions_json.py
```

**Note**: You don't need to generate `subscriptions.json` before using other scripts. All scripts work directly with the API. This file is purely for reference/backup purposes.

### 2. Preview Price Changes

Preview calculated prices before applying changes:

```bash
python3 main.py
```

This shows:
- Current prices vs calculated prices
- Big Mac Index ratios used
- Price differences per territory

### 3. Update Prices (Bulk)

Update prices for multiple subscriptions:

```bash
python3 update_prices.py
```

**Important**: This script will:
- Process all subscriptions listed in `SUBSCRIPTIONS_TO_UPDATE` from `.env`
- Show a preview before each update
- Ask for confirmation before applying changes
- Schedule price changes for tomorrow (or specified date)

**Configuration**: Set `SUBSCRIPTIONS_TO_UPDATE` in your `.env` file to select which subscriptions to update. Format: `"ID1:Name1,ID2:Name2,ID3:Name3"`

Example:
```bash
SUBSCRIPTIONS_TO_UPDATE="6743152682:Annual Subscription,6743152701:Monthly Subscription"
```

### 4. Update Single Territory (Example)

Update price for a specific territory:

```bash
python3 scripts/update_panama.py
```

This is an example script showing how to update a single territory. Modify it for your needs.

### 5. Test Price Calculation

Test price calculation for one country:

```bash
python3 scripts/test_one_country.py
```

## How It Works

### Big Mac Index

The Big Mac Index is an economic indicator that compares purchasing power between countries by comparing the price of a Big Mac burger. This tool uses it to calculate fair subscription prices.

**Formula**: `New Price = US Base Price × (Big Mac Price in Country / Big Mac Price in US)`

### Price Calculation Process

1. **Fetch Big Mac Index Data**: Downloads latest data from The Economist's GitHub repository
2. **Calculate Ratios**: Computes PPP ratios for each territory relative to US
3. **Apply Fallbacks**: Uses estimated ratios for countries without Big Mac data
4. **Find Price Tiers**: Matches calculated prices to Apple's available price tiers
5. **Schedule Changes**: Creates price change schedules via App Store Connect API

### Fallback Ratios

For countries without Big Mac Index data, the tool uses:
- Similar country proxies (e.g., Panama → Costa Rica)
- GDP per capita (PPP) estimates
- Regional averages (e.g., Euro area for EUR countries)

## API Reference

### Core Modules

#### `appstore_api.py`
App Store Connect API client with methods for:
- Getting subscriptions and prices
- Creating price changes
- Managing subscription groups

#### `bigmac_index.py`
Big Mac Index data fetcher and ratio calculator:
- `fetch_data()`: Downloads latest Big Mac Index data
- `get_country_ratio(territory_code)`: Gets PPP ratio for a territory
- `get_all_ratios()`: Gets ratios for all available territories

#### `price_calculator.py`
Price calculation engine:
- `calculate_new_price(base_price, territory_code)`: Calculates new price
- `find_nearest_price_tier()`: Finds matching Apple price tier

## Configuration

### Environment Variables (`.env`)

Create a `.env` file in the root directory with your credentials:

```bash
APP_ID=your-app-id                    # Your App Store Connect App ID
ISSUER_ID=your-issuer-id              # API Key Issuer ID
KEY_ID=your-key-id                    # API Key ID
PRIVATE_KEY_PATH=AuthKey_XXXXX.p8     # Path to your .p8 key file
API_BASE_URL=https://api.appstoreconnect.apple.com/v1
BIGMAC_INDEX_URL=https://raw.githubusercontent.com/TheEconomist/big-mac-data/master/output-data/big-mac-full-index.csv
BASE_CURRENCY=USD

# Subscription IDs to update (comma-separated ID:Name pairs)
SUBSCRIPTIONS_TO_UPDATE="ID1:Name1,ID2:Name2,ID3:Name3"
```

**Note**: The `.env` file is gitignored and will not be committed to the repository. Use `.env.example` as a template.

### Subscription Selection

Set `SUBSCRIPTIONS_TO_UPDATE` in your `.env` file. The format is a comma-separated list of `ID:Name` pairs:

```bash
SUBSCRIPTIONS_TO_UPDATE="ID1:Name1,ID2:Name2,ID3:Name3"
```

Example:
```bash
SUBSCRIPTIONS_TO_UPDATE="6743152682:Annual Subscription,6743152701:Monthly Subscription,6745085678:Weekly Subscription"
```

## Important Notes

### Price Change Scheduling

- **Future Dates Required**: After a subscription is approved, you cannot create immediate price changes. All changes must be scheduled for a future date (minimum 1 day ahead).
- **Propagation Delay**: API changes may take up to 1 hour to appear in App Store Connect dashboard (manual changes appear immediately).
- **User Notification**: Apple automatically notifies users of price increases and may require consent in some regions.

### Price Increases

When increasing subscription prices:
- Apple notifies existing subscribers via email and push notification
- Subscribers may need to consent to the new price
- If they don't consent, their subscription expires at the end of the current billing cycle

### Price Decreases

When decreasing prices:
- Existing subscriptions automatically renew at the lower price
- No user consent required

## Scripts Directory

The `scripts/` folder contains utility and test scripts:

- **Test Scripts**: For testing price calculations and API calls
- **Utility Scripts**: For debugging and inspecting data
- See `scripts/README.md` for details

## Troubleshooting

### API Authentication Errors

- Verify your `.p8` key file is in the correct location
- Check that `ISSUER_ID` and `KEY_ID` match your API key
- Ensure your API key has the necessary permissions

### Price Change Errors

- **409 Conflict**: A price change may already be scheduled for that territory
- **404 Not Found**: Check that subscription ID and price point ID are correct
- **400 Bad Request**: Verify request payload structure matches API requirements

### Missing Territory Data

- Some territories may not have Big Mac Index data
- The tool uses fallback ratios for these territories
- Check `bigmac_index.py` to add custom fallback ratios

## References

- [App Store Connect API Documentation](https://developer.apple.com/documentation/appstoreconnectapi)
- [Create Subscription Price Change API](https://developer.apple.com/documentation/appstoreconnectapi/post-v1-subscriptionprices)
- [Big Mac Index Data](https://github.com/TheEconomist/big-mac-data)
- [Managing Subscription Pricing](https://developer.apple.com/help/app-store-connect/manage-subscriptions/manage-pricing-for-auto-renewable-subscriptions/)

## License

[Add your license here]

## Contributing

[Add contribution guidelines if needed]

## Support

For issues or questions:
1. Check the troubleshooting section
2. Review App Store Connect API documentation
3. Check script output for error messages

---

**⚠️ Warning**: Always preview price changes before applying them. Price increases require user consent and may affect subscription renewals.

