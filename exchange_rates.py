"""
Fetch current exchange rates for currency conversion
"""
import requests
from typing import Dict, Optional
from datetime import datetime

class ExchangeRates:
    def __init__(self):
        self.rates = {}
        self.base_currency = "USD"
        self.fetch_date = None
    
    def fetch_current_rates(self) -> bool:
        """
        Fetch current exchange rates from exchangerate-api.com (free tier)
        Fallback to alternative APIs if needed
        """
        try:
            # Try exchangerate-api.com (free, no API key needed)
            url = "https://api.exchangerate-api.com/v4/latest/USD"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            self.rates = data.get("rates", {})
            self.fetch_date = data.get("date", datetime.now().strftime("%Y-%m-%d"))
            self.base_currency = data.get("base", "USD")
            
            print(f"✓ Fetched exchange rates for {len(self.rates)} currencies (date: {self.fetch_date})")
            return True
            
        except Exception as e:
            print(f"Error fetching exchange rates from exchangerate-api.com: {e}")
            
            # Fallback: Try fixer.io (requires free API key, but has better coverage)
            # For now, we'll use a simple fallback or manual rates
            try:
                # Alternative: Use exchangerate.host (free, no key)
                url = "https://api.exchangerate.host/latest?base=USD"
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                if data.get("success", False):
                    self.rates = data.get("rates", {})
                    self.fetch_date = datetime.now().strftime("%Y-%m-%d")
                    print(f"✓ Fetched exchange rates from exchangerate.host (date: {self.fetch_date})")
                    return True
            except Exception as e2:
                print(f"Error fetching from exchangerate.host: {e2}")
            
            return False
    
    def get_rate(self, currency_code: str) -> Optional[float]:
        """Get exchange rate for a currency (1 USD = X currency)"""
        if currency_code == "USD":
            return 1.0
        
        rate = self.rates.get(currency_code.upper())
        if rate:
            return float(rate)
        
        return None
    
    def convert_usd_to_local(self, usd_amount: float, currency_code: str) -> Optional[float]:
        """Convert USD amount to local currency"""
        rate = self.get_rate(currency_code)
        if rate:
            return usd_amount * rate
        return None
    
    def convert_local_to_usd(self, local_amount: float, currency_code: str) -> Optional[float]:
        """Convert local currency amount to USD"""
        rate = self.get_rate(currency_code)
        if rate and rate > 0:
            return local_amount / rate
        return None

