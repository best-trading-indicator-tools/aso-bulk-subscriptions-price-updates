#!/usr/bin/env python3
"""Decode price entry IDs to extract territory"""
import base64
import json

# Example price entry ID
price_id = "eyJhIjoiNjc0MzE1MjY4MiIsImMiOiJBRSIsImQiOjAsInAiOiIwIn0"

try:
    decoded = base64.urlsafe_b64decode(price_id + '==')
    data = json.loads(decoded)
    print("Decoded:", data)
    print("Territory:", data.get('c'))
except Exception as e:
    print(f"Error: {e}")

