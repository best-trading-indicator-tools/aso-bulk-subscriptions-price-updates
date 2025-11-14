# Scripts Directory

This directory contains test and utility scripts for the ASO pricing tool.

## Test Scripts

- `test_one_country.py` - Test price calculation for a single country/territory (currently configured for Panama)
- `test_albania.py` - Test script to update prices for a single territory (currently configured for Australia)
- `test_price_structure.py` - Script to inspect the API response structure for subscription prices
- `test_update_one.py` - Test updating a single subscription
- `update_panama.py` - Example script showing how to update price for a single territory (Panama)

## Utility Scripts

- `check_scheduled_prices.py` - Check scheduled price changes for a subscription
- `check_currency.py` - Check what currency the prices are returned in
- `check_territories.py` - List all available territories for a subscription
- `decode_price_id.py` - Utility to decode price entry IDs to extract territory codes

## Usage

These scripts are for testing and debugging purposes. The main scripts (`update_prices.py`, `list_subscriptions.py`, `main.py`) are in the root directory.

### Examples

**Test price calculation for one country:**
```bash
python3 scripts/test_one_country.py
```

**Check scheduled price changes:**
```bash
python3 scripts/check_scheduled_prices.py
```

**Update single territory (example):**
```bash
python3 scripts/update_panama.py
```

**Check available territories:**
```bash
python3 scripts/check_territories.py
```

