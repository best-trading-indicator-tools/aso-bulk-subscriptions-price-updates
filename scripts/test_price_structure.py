#!/usr/bin/env python3
"""Test script to understand price data structure"""
import json
from appstore_api import AppStoreConnectAPI

api = AppStoreConnectAPI()
subscription_id = "6743152682"  # Annual Subscription

# Get prices with included data
endpoint = f"/subscriptions/{subscription_id}/prices"
params = {
    "include": "subscriptionPricePoint",
    "limit": 5  # Just get a few to see structure
}

data = api._make_request(endpoint, params=params)

print("API Response Structure:")
print("="*80)
print(json.dumps(data, indent=2))

