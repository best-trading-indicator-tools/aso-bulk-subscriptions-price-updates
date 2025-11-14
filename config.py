import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# App Store Connect API Configuration
APP_ID = os.getenv("APP_ID", "")
ISSUER_ID = os.getenv("ISSUER_ID", "")
KEY_ID = os.getenv("KEY_ID", "")
PRIVATE_KEY_PATH = os.getenv("PRIVATE_KEY_PATH", "")

# API Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "https://api.appstoreconnect.apple.com/v1")
BIGMAC_INDEX_URL = os.getenv(
    "BIGMAC_INDEX_URL",
    "https://raw.githubusercontent.com/TheEconomist/big-mac-data/master/output-data/big-mac-full-index.csv"
)
NETFLIX_INDEX_URL = os.getenv("NETFLIX_INDEX_URL", None)  # Optional: URL to Netflix pricing CSV
BASE_CURRENCY = os.getenv("BASE_CURRENCY", "USD")

# Subscription IDs to update (comma-separated list of ID:Name pairs)
# Format: "ID1:Name1,ID2:Name2,ID3:Name3"
# Example: "6743152682:Annual Subscription,6743152701:Monthly Subscription"
SUBSCRIPTIONS_TO_UPDATE = {}

_subscriptions_str = os.getenv("SUBSCRIPTIONS_TO_UPDATE", "")
if _subscriptions_str:
    for pair in _subscriptions_str.split(","):
        pair = pair.strip()
        if ":" in pair:
            sub_id, sub_name = pair.split(":", 1)
            SUBSCRIPTIONS_TO_UPDATE[sub_id.strip()] = sub_name.strip()

