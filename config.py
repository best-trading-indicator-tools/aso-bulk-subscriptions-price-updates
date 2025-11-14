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
BASE_CURRENCY = os.getenv("BASE_CURRENCY", "USD")

