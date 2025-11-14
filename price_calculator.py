import bigmac_index
import netflix_index
import config
from typing import Dict, List, Optional

class PriceCalculator:
    def __init__(self, index_type: str = "bigmac"):
        """
        Initialize price calculator with chosen index type
        
        Args:
            index_type: "bigmac" or "netflix"
        """
        self.index_type = index_type.lower()
        
        if self.index_type == "netflix":
            self.index = netflix_index.NetflixIndex()
            self.index.fetch_data()
        else:  # Default to Big Mac Index
            self.index_type = "bigmac"
            self.index = bigmac_index.BigMacIndex()
            self.index.fetch_data()
    
    def calculate_new_price(self, base_price: float, territory_code: str) -> Optional[float]:
        """
        Calculate new price based on selected index ratio
        new_price = base_price * (index_price_territory / index_price_usd)
        """
        ratio = self.index.get_country_ratio(territory_code)
        if ratio is None:
            return None
        
        new_price = base_price * ratio
        return new_price
    
    def calculate_all_prices(self, base_price: float, territories: List[str]) -> Dict[str, Optional[float]]:
        """Calculate new prices for multiple territories"""
        prices = {}
        for territory in territories:
            prices[territory] = self.calculate_new_price(base_price, territory)
        return prices
    
    def find_nearest_price_tier(self, calculated_price: float, price_tiers: List[Dict]) -> Optional[str]:
        """
        Find the nearest Apple price tier for a calculated price
        Returns the price point ID of the nearest tier
        """
        if not price_tiers:
            return None
        
        min_diff = float('inf')
        nearest_tier_id = None
        
        for tier in price_tiers:
            tier_data = tier.get('attributes', {})
            price = tier_data.get('customerPrice', {}).get('value', 0)
            
            if price > 0:
                diff = abs(price - calculated_price)
                if diff < min_diff:
                    min_diff = diff
                    nearest_tier_id = tier.get('id')
        
        return nearest_tier_id
    
    def generate_comparison_report(self, subscription_name: str, current_prices: Dict[str, Dict], base_price: float) -> List[Dict]:
        """
        Generate a comparison report showing current vs proposed prices
        Returns list of dictionaries with territory, current price, proposed price, ratio
        """
        report = []
        all_ratios = self.index.get_all_ratios()
        
        for territory, price_info in current_prices.items():
            current_price_data = price_info.get('attributes', {}).get('subscriptionPricePoint', {})
            current_price = current_price_data.get('attributes', {}).get('customerPrice', {}).get('value', 0)
            
            ratio = all_ratios.get(territory)
            if ratio is None:
                ratio = self.index.get_country_ratio(territory)
            
            proposed_price = None
            if ratio:
                proposed_price = base_price * ratio
            
            report.append({
                'territory': territory,
                'current_price': current_price,
                'proposed_price': proposed_price,
                'ratio': ratio,
                'price_info': price_info
            })
        
        return report

