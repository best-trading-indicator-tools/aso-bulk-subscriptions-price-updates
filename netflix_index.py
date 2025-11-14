import pandas as pd
import requests
import config
from typing import Dict, Optional

class NetflixIndex:
    """
    Netflix Index - Uses Netflix subscription pricing by country as PPP indicator
    Similar to Big Mac Index but uses Netflix Standard plan pricing
    """
    def __init__(self):
        self.data = None
        self.ratios = {}
        self.usd_price = None
    
    def fetch_data(self):
        """
        Fetch Netflix pricing data
        
        Note: Netflix does NOT provide a public API for pricing data.
        This implementation uses:
        1. Custom CSV URL (if NETFLIX_INDEX_URL is set in .env)
        2. Built-in curated dataset (based on publicly available Netflix pricing)
        
        Data sources:
        - Netflix pricing varies significantly by country ($2.82 in Pakistan to $22.89 in Switzerland)
        - Prices are subject to change and may not always be up-to-date
        - For missing countries, fallback mechanisms are used (Eurozone average, similar country proxies)
        - If no data is available, returns None (caller should handle fallback to Big Mac Index)
        """
        try:
            # Try to fetch from custom URL if configured
            netflix_url = getattr(config, 'NETFLIX_INDEX_URL', None)
            
            if netflix_url:
                print(f"  Attempting to fetch Netflix pricing from: {netflix_url}")
                response = requests.get(netflix_url, timeout=10)
                response.raise_for_status()
                from io import StringIO
                self.data = pd.read_csv(StringIO(response.text))
                print(f"  ✓ Loaded Netflix pricing from URL")
            else:
                # Use built-in Netflix pricing data
                # Note: These are approximate values based on publicly available information
                # Netflix pricing changes frequently and varies by plan type
                self.data = self._get_builtin_netflix_data()
                print(f"  ⚠️  Using built-in Netflix pricing data (may not be up-to-date)")
                print(f"  💡 Tip: Set NETFLIX_INDEX_URL in .env to use a custom data source")
            
            if self.data is None or self.data.empty:
                print("⚠️  Warning: No Netflix pricing data available")
                return False
            
            # Get USD price (Netflix US Standard plan)
            us_row = self.data[self.data['country_code'] == 'US']
            if not us_row.empty:
                self.usd_price = float(us_row.iloc[0]['price_usd'])
            else:
                # Fallback: use first row or default
                if not self.data.empty:
                    self.usd_price = float(self.data.iloc[0]['price_usd'])
                else:
                    self.usd_price = 15.49  # Netflix US Standard plan default (as of 2024)
            
            print(f"✓ Fetched Netflix Index data (USD base price: ${self.usd_price:.2f})")
            print(f"  ⚠️  Note: Netflix pricing data may not be comprehensive or up-to-date")
            print(f"  💡 Missing countries will use fallback mechanisms")
            return True
            
        except Exception as e:
            print(f"Error fetching Netflix Index data: {e}")
            # Fallback to built-in data
            try:
                self.data = self._get_builtin_netflix_data()
                if self.data is not None and not self.data.empty:
                    us_row = self.data[self.data['country_code'] == 'US']
                    if not us_row.empty:
                        self.usd_price = float(us_row.iloc[0]['price_usd'])
                    else:
                        self.usd_price = 15.49
                    print(f"✓ Using built-in Netflix Index data (USD base price: ${self.usd_price:.2f})")
                    print(f"  ⚠️  Warning: Built-in data may be outdated")
                    return True
            except Exception as e2:
                print(f"  Error loading built-in data: {e2}")
            
            print(f"⚠️  Could not load Netflix Index data")
            return False
    
    def _get_builtin_netflix_data(self) -> Optional[pd.DataFrame]:
        """
        Built-in Netflix pricing data (Netflix Standard plan prices in USD)
        
        WARNING: These are approximate values based on publicly available information.
        Netflix pricing:
        - Changes frequently
        - Varies by plan type (Basic, Standard, Premium)
        - May not be available in all countries
        - Can range from ~$2.82 (Pakistan) to ~$22.89 (Switzerland)
        
        Data sources referenced:
        - Visual Capitalist: https://www.visualcapitalist.com/cp/mapped-how-much-netflix-costs-in-every-country/
        - Statista: Netflix pricing statistics
        
        For accurate, up-to-date pricing, visit: https://www.netflix.com/
        """
        netflix_data = {
            'country_code': [
                'US', 'GB', 'CA', 'AU', 'DE', 'FR', 'IT', 'ES', 'NL', 'BE',
                'CH', 'AT', 'SE', 'NO', 'DK', 'FI', 'IE', 'PT', 'GR', 'PL',
                'CZ', 'HU', 'RO', 'BG', 'HR', 'SK', 'SI', 'EE', 'LV', 'LT',
                'JP', 'CN', 'KR', 'IN', 'BR', 'MX', 'AR', 'CL', 'CO', 'PE',
                'CR', 'UY', 'ZA', 'NZ', 'SG', 'MY', 'TH', 'PH', 'ID', 'VN',
                'TW', 'HK', 'TR', 'RU', 'IL', 'AE', 'SA', 'QA', 'KW', 'BH',
                'OM', 'EG', 'NG', 'KE'
            ],
            'price_usd': [
                15.49,  # US
                13.99,  # GB
                16.49,  # CA
                16.99,  # AU
                12.99,  # DE
                13.99,  # FR
                12.99,  # IT
                12.99,  # ES
                12.99,  # NL
                12.99,  # BE
                19.90,  # CH
                12.99,  # AT
                13.99,  # SE
                13.99,  # NO
                13.99,  # DK
                12.99,  # FI
                13.99,  # IE
                9.99,   # PT
                9.99,   # GR
                9.99,   # PL
                9.99,   # CZ
                9.99,   # HU
                9.99,   # RO
                9.99,   # BG
                9.99,   # HR
                9.99,   # SK
                9.99,   # SI
                9.99,   # EE
                9.99,   # LV
                9.99,   # LT
                12.99,  # JP
                7.99,   # CN
                12.99,  # KR
                7.99,   # IN
                7.99,   # BR
                7.99,   # MX
                7.99,   # AR
                7.99,   # CL
                7.99,   # CO
                7.99,   # PE
                7.99,   # CR
                7.99,   # UY
                7.99,   # ZA
                16.99,  # NZ
                12.99,  # SG
                7.99,   # MY
                7.99,   # TH
                7.99,   # PH
                7.99,   # ID
                7.99,   # VN
                12.99,  # TW
                12.99,  # HK
                7.99,   # TR
                7.99,   # RU
                12.99,  # IL
                12.99,  # AE
                12.99,  # SA
                12.99,  # QA
                12.99,  # KW
                12.99,  # BH
                12.99,  # OM
                7.99,   # EG
                7.99,   # NG
                7.99,   # KE
            ]
        }
        
        return pd.DataFrame(netflix_data)
    
    def get_country_ratio(self, country_code: str) -> Optional[float]:
        """
        Get Netflix price ratio for a country relative to USD
        Returns ratio (e.g., 0.9 means Netflix costs 0.9x less than in US)
        """
        if self.data is None or self.usd_price is None:
            return None
        
        # Handle US/USA - always return 1.0 as it's the base
        if country_code in ["US", "USA"]:
            return 1.0
        
        # Map App Store territory codes to country codes
        territory_to_country = self._get_territory_mapping()
        mapped_code = territory_to_country.get(country_code, country_code)
        
        # Get country data
        country_data = self.data[self.data['country_code'] == mapped_code]
        
        if not country_data.empty:
            country_price = float(country_data.iloc[0]['price_usd'])
            if country_price > 0:
                ratio = country_price / self.usd_price
                return ratio
        
        # Fallback: Use Euro area average for European countries
        euro_countries = {
            'AT', 'BE', 'NL', 'FI', 'IE', 'PT', 'GR', 'LU', 'MT', 'CY',
            'SI', 'SK', 'EE', 'LV', 'LT', 'HR', 'DE', 'FR', 'IT', 'ES',
            'AD', 'MC', 'SM'
        }
        if country_code in euro_countries:
            # Use average Eurozone Netflix price
            euro_avg = 12.99  # Average Eurozone Netflix price
            return euro_avg / self.usd_price
        
        # Fallback: Use similar country proxy
        proxy_ratio = self._estimate_ratio_from_proxies(country_code)
        if proxy_ratio is not None:
            return proxy_ratio
        
        # Final fallback: Use regional average based on GDP/economic indicators
        # This is a last resort when no data is available
        return self._estimate_regional_ratio(country_code)
    
    def _estimate_ratio_from_proxies(self, country_code: str) -> Optional[float]:
        """Estimate ratio using similar country proxies"""
        proxies = {
            'PA': 'CR',  # Panama -> Costa Rica
            'BS': 'CA',  # Bahamas -> Canada
            'BB': 'CA',  # Barbados -> Canada
            'TT': 'CA',  # Trinidad -> Canada
            'AG': 'CA',  # Antigua -> Canada
            'KN': 'CA',  # St. Kitts -> Canada
            'LC': 'CA',  # St. Lucia -> Canada
            'VC': 'CA',  # St. Vincent -> Canada
            'SC': 'ZA',  # Seychelles -> South Africa
            'BN': 'SG',  # Brunei -> Singapore
            'LI': 'CH',  # Liechtenstein -> Switzerland
            'IS': 'NO',  # Iceland -> Norway
        }
        
        proxy_code = proxies.get(country_code)
        if proxy_code:
            proxy_ratio = self.get_country_ratio(proxy_code)
            if proxy_ratio is not None:
                return proxy_ratio
        
        return None
    
    def _estimate_regional_ratio(self, country_code: str) -> Optional[float]:
        """
        Final fallback: Estimate ratio based on regional averages
        Used when no Netflix data is available for a country
        """
        # Regional averages (approximate Netflix pricing ratios)
        regional_ratios = {
            # Caribbean (similar to Latin America)
            'AG': 0.52, 'KN': 0.52, 'LC': 0.52, 'VC': 0.52, 'BS': 0.65, 'BB': 0.65, 'TT': 0.65,
            # Central America
            'PA': 0.52,  # Panama
            # Middle East (similar to Gulf countries)
            'BH': 0.84, 'OM': 0.84,
            # Other regions - use conservative estimate
        }
        
        if country_code in regional_ratios:
            return regional_ratios[country_code]
        
        # Default: return None - caller should use Big Mac Index as fallback
        return None
    
    def _get_territory_mapping(self) -> Dict[str, str]:
        """Map App Store territory codes to country codes"""
        return {
            'US': 'US', 'USA': 'US',
            'GB': 'GB', 'CA': 'CA', 'AU': 'AU', 'NZ': 'NZ',
            'DE': 'DE', 'FR': 'FR', 'IT': 'IT', 'ES': 'ES',
            'NL': 'NL', 'BE': 'BE', 'CH': 'CH', 'AT': 'AT',
            'SE': 'SE', 'NO': 'NO', 'DK': 'DK', 'FI': 'FI',
            'IE': 'IE', 'PT': 'PT', 'GR': 'GR', 'PL': 'PL',
            'CZ': 'CZ', 'HU': 'HU', 'RO': 'RO', 'BG': 'BG',
            'HR': 'HR', 'SK': 'SK', 'SI': 'SI', 'EE': 'EE',
            'LV': 'LV', 'LT': 'LT', 'JP': 'JP', 'CN': 'CN',
            'KR': 'KR', 'IN': 'IN', 'BR': 'BR', 'MX': 'MX',
            'AR': 'AR', 'CL': 'CL', 'CO': 'CO', 'PE': 'PE',
            'CR': 'CR', 'UY': 'UY', 'ZA': 'ZA', 'SG': 'SG',
            'MY': 'MY', 'TH': 'TH', 'PH': 'PH', 'ID': 'ID',
            'VN': 'VN', 'TW': 'TW', 'HK': 'HK', 'TR': 'TR',
            'RU': 'RU', 'IL': 'IL', 'AE': 'AE', 'SA': 'SA',
            'QA': 'QA', 'KW': 'KW', 'BH': 'BH', 'OM': 'OM',
            'EG': 'EG', 'NG': 'NG', 'KE': 'KE', 'PA': 'PA',
            'BS': 'BS', 'BB': 'BB', 'TT': 'TT', 'AG': 'AG',
            'KN': 'KN', 'LC': 'LC', 'VC': 'VC', 'SC': 'SC',
            'BN': 'BN', 'LI': 'LI', 'IS': 'IS',
        }
    
    def get_all_ratios(self) -> Dict[str, float]:
        """Get ratios for all available countries"""
        if self.data is None or self.usd_price is None:
            return {}
        
        ratios = {}
        territory_mapping = self._get_territory_mapping()
        
        for territory, country_code in territory_mapping.items():
            ratio = self.get_country_ratio(territory)
            if ratio is not None:
                ratios[territory] = ratio
        
        return ratios

