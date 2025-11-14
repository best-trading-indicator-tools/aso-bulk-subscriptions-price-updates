import jwt
import time
from pathlib import Path
import config

def generate_token():
    """Generate JWT token for App Store Connect API authentication"""
    # Read the private key
    key_path = Path(config.PRIVATE_KEY_PATH)
    if not key_path.exists():
        raise FileNotFoundError(f"Private key file not found: {config.PRIVATE_KEY_PATH}")
    
    with open(key_path, 'r') as f:
        private_key = f.read()
    
    # Create the token
    headers = {
        "alg": "ES256",
        "kid": config.KEY_ID,
        "typ": "JWT"
    }
    
    payload = {
        "iss": config.ISSUER_ID,
        "iat": int(time.time()),
        "exp": int(time.time()) + 1200,  # 20 minutes
        "aud": "appstoreconnect-v1"
    }
    
    token = jwt.encode(payload, private_key, algorithm="ES256", headers=headers)
    return token

