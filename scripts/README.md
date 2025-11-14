# Scripts Directory

This directory contains essential utility scripts for the ASO pricing tool.

## Utility Scripts

- `generate_subscriptions_json.py` - Generate subscriptions.json file from App Store Connect API (reads from .env)
- `check_scheduled_prices.py` - Check scheduled price changes for a subscription
- `decode_price_id.py` - Utility to decode price entry IDs to extract territory codes

## Usage

These scripts are utility tools. The main scripts (`update_prices.py`, `list_subscriptions.py`, `main.py`) are in the root directory.

### Examples

**Generate subscriptions.json:**
```bash
python3 scripts/generate_subscriptions_json.py
```

**Check scheduled price changes:**
```bash
python3 scripts/check_scheduled_prices.py
```

**Decode a price entry ID:**
```bash
python3 scripts/decode_price_id.py
```

