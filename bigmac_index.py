import pandas as pd
import requests
import config
from typing import Dict, Optional

class BigMacIndex:
    def __init__(self):
        self.data = None
        self.ratios = {}
        self.usd_price = None
    
    def fetch_data(self):
        """Fetch Big Mac Index data from TheEconomist GitHub repo"""
        try:
            response = requests.get(config.BIGMAC_INDEX_URL)
            response.raise_for_status()
            
            # Read CSV data
            from io import StringIO
            self.data = pd.read_csv(StringIO(response.text))
            
            # Get the latest data (assuming data is sorted by date)
            latest_data = self.data.sort_values('date', ascending=False).iloc[0]
            
            # Find USD price
            usd_row = self.data[self.data['currency_code'] == 'USD'].sort_values('date', ascending=False)
            if not usd_row.empty:
                self.usd_price = usd_row.iloc[0]['dollar_price']
            else:
                # Fallback: use US row
                us_row = self.data[self.data['iso_a3'] == 'USA'].sort_values('date', ascending=False)
                if not us_row.empty:
                    self.usd_price = us_row.iloc[0]['dollar_price']
            
            print(f"✓ Fetched Big Mac Index data (USD base price: ${self.usd_price:.2f})")
            return True
            
        except Exception as e:
            print(f"Error fetching Big Mac Index data: {e}")
            return False
    
    def get_country_ratio(self, country_code: str) -> Optional[float]:
        """
        Get Big Mac price ratio for a country relative to USD
        Returns ratio (e.g., 1.5 means Big Mac costs 1.5x more than in US)
        """
        if self.data is None or self.usd_price is None:
            return None
        
        # Handle US/USA - always return 1.0 as it's the base
        if country_code in ["US", "USA"]:
            return 1.0
        
        # Map App Store territory codes to ISO codes
        territory_to_iso = self._get_territory_mapping()
        iso_code = territory_to_iso.get(country_code, country_code)
        
        # Get latest data for this country
        latest_date = self.data['date'].max()
        country_data = self.data[
            (self.data['iso_a3'] == iso_code) & 
            (self.data['date'] == latest_date)
        ]
        
        if country_data.empty:
            # Try by currency code
            country_data = self.data[
                (self.data['currency_code'] == country_code) & 
                (self.data['date'] == latest_date)
            ]
        
        if not country_data.empty:
            country_price = country_data.iloc[0]['dollar_price']
            if pd.notna(country_price) and country_price > 0:
                ratio = country_price / self.usd_price
                return ratio
        
        # Fallback: Use Euro area ratio for European countries without specific data
        euro_countries = {
            'AT', 'BE', 'NL', 'FI', 'IE', 'PT', 'GR', 'LU', 'MT', 'CY',
            'SI', 'SK', 'EE', 'LV', 'LT', 'HR', 'DE', 'FR', 'IT', 'ES',
            'AD', 'MC', 'SM'  # European microstates that use EUR
        }
        if country_code in euro_countries:
            euro_data = self.data[
                (self.data['iso_a3'] == 'EUZ') & 
                (self.data['date'] == latest_date)
            ]
            if not euro_data.empty:
                euro_price = euro_data.iloc[0]['dollar_price']
                if pd.notna(euro_price) and euro_price > 0:
                    return euro_price / self.usd_price
        
        # Fallback: Try to estimate ratio using alternative indices
        estimated_ratio = self._estimate_ratio_from_alternatives(country_code, visited=set())
        if estimated_ratio is not None:
            return estimated_ratio
        
        return None
    
    def _estimate_ratio_from_alternatives(self, country_code: str, visited: Optional[set] = None) -> Optional[float]:
        """
        Estimate Big Mac ratio using alternative indices when direct data is unavailable.
        Uses GDP per capita (PPP), similar country proxies, or regional averages.
        
        Args:
            country_code: Territory code to estimate ratio for
            visited: Set of country codes already visited (prevents infinite recursion)
        """
        if visited is None:
            visited = set()
        
        if country_code in visited:
            return None  # Prevent infinite recursion
        
        visited.add(country_code)
        
        # First check fallback ratios dictionary
        fallback_ratios = self._get_fallback_ratios()
        if country_code in fallback_ratios:
            return fallback_ratios[country_code]
        
        # Try similar country proxy based on region/economy
        similar_country_proxies = self._get_similar_country_proxies()
        if country_code in similar_country_proxies:
            proxy_code = similar_country_proxies[country_code]
            # Try to get ratio from proxy country (which should have Big Mac data)
            # Use direct Big Mac lookup to avoid recursion
            if self.data is not None and self.usd_price is not None:
                territory_mapping = self._get_territory_mapping()
                iso_code = territory_mapping.get(proxy_code, proxy_code)
                latest_date = self.data['date'].max()
                proxy_data = self.data[
                    (self.data['iso_a3'] == iso_code) & 
                    (self.data['date'] == latest_date)
                ]
                if not proxy_data.empty:
                    proxy_price = proxy_data.iloc[0]['dollar_price']
                    if pd.notna(proxy_price) and proxy_price > 0:
                        return proxy_price / self.usd_price
            
            # Fallback: try get_country_ratio but with visited set to prevent recursion
            # This will use Euro fallback or other mechanisms
            proxy_ratio = self._get_country_ratio_direct(proxy_code, visited)
            if proxy_ratio is not None:
                return proxy_ratio
        
        return None
    
    def _get_country_ratio_direct(self, country_code: str, visited: set) -> Optional[float]:
        """Internal method to get ratio without calling estimate_alternatives recursively"""
        if country_code in ["US", "USA"]:
            return 1.0
        
        if self.data is None or self.usd_price is None:
            return None
        
        territory_mapping = self._get_territory_mapping()
        iso_code = territory_mapping.get(country_code, country_code)
        latest_date = self.data['date'].max()
        
        country_data = self.data[
            (self.data['iso_a3'] == iso_code) & 
            (self.data['date'] == latest_date)
        ]
        
        if not country_data.empty:
            country_price = country_data.iloc[0]['dollar_price']
            if pd.notna(country_price) and country_price > 0:
                return country_price / self.usd_price
        
        # Check Euro fallback
        euro_countries = {
            'AT', 'BE', 'NL', 'FI', 'IE', 'PT', 'GR', 'LU', 'MT', 'CY',
            'SI', 'SK', 'EE', 'LV', 'LT', 'HR', 'DE', 'FR', 'IT', 'ES',
            'AD', 'MC', 'SM'  # European microstates
        }
        if country_code in euro_countries:
            euro_data = self.data[
                (self.data['iso_a3'] == 'EUZ') & 
                (self.data['date'] == latest_date)
            ]
            if not euro_data.empty:
                euro_price = euro_data.iloc[0]['dollar_price']
                if pd.notna(euro_price) and euro_price > 0:
                    return euro_price / self.usd_price
        
        return None
    
    def _get_fallback_ratios(self) -> Dict[str, float]:
        """
        Fallback ratios for rich countries without Big Mac Index data.
        Based on GDP per capita (PPP) ratios and economic indicators.
        """
        # Get US ratio as baseline (should be 1.0, but get from data if available)
        us_ratio = 1.0
        if self.usd_price:
            # Try to get a reference ratio from a similar country to calibrate
            pass
        
        # GDP per capita (PPP) ratios relative to US (~$80,000)
        # These are rough estimates based on economic indicators
        fallback = {
            # Panama - similar to Costa Rica, high-income country
            'PA': 1.15,  # Panama GDP per capita PPP ~$35k, ratio ~1.15
            
            # Caribbean high-income countries
            'BS': 1.25,  # Bahamas - tourism-based economy, higher prices
            'BB': 1.10,  # Barbados - similar to other Caribbean nations
            'TT': 1.05,  # Trinidad & Tobago - oil-based economy
            'AG': 1.15,  # Antigua and Barbuda - tourism-based economy
            'KN': 1.12,  # St. Kitts and Nevis - tourism-based economy
            'LC': 1.10,  # St. Lucia - tourism-based economy
            'VC': 1.08,  # St. Vincent and the Grenadines
            'SC': 1.20,  # Seychelles - high-income island nation
            
            # Other rich countries without Big Mac data
            'BN': 1.18,  # Brunei - oil-rich, high GDP per capita
            
            # Note: Andorra (AD), Monaco (MC), San Marino (SM) use EUR and will get EUR ratio via fallback
            'LI': None,  # Liechtenstein - handled by proxy (Switzerland)
            'IS': None,  # Iceland - handled by proxy (Norway)
        }
        
        # Filter out None values and return
        return {k: v for k, v in fallback.items() if v is not None}
    
    def _get_similar_country_proxies(self) -> Dict[str, str]:
        """
        Map countries without Big Mac data to similar countries that have data.
        Note: Countries with fallback ratios will use those instead of proxies.
        """
        return {
            # Central America
            'PA': 'CR',  # Panama -> Costa Rica (similar Central American economy)
            
            # Caribbean - these will use fallback ratios, but proxy to countries with Big Mac data if needed
            # Note: BS, BB, TT, AG, KN, LC, VC have fallback ratios, so proxies are secondary
            'AG': 'BS',  # Antigua -> Bahamas (similar Caribbean economy)
            'KN': 'BS',  # St. Kitts -> Bahamas
            'LC': 'BS',  # St. Lucia -> Bahamas
            'VC': 'BS',  # St. Vincent -> Bahamas
            
            # Other regions
            'SC': 'MU',  # Seychelles -> Mauritius (if available) or use fallback
            'BN': 'SG',  # Brunei -> Singapore (similar wealthy Asian economy)
            
            # European microstates - use Euro area countries (will get EUR ratio via fallback)
            'AD': 'ES',  # Andorra -> Spain (uses EUR, will get EUR ratio)
            'MC': 'FR',  # Monaco -> France (uses EUR, will get EUR ratio)
            'SM': 'IT',  # San Marino -> Italy (uses EUR, will get EUR ratio)
        }
    
    def _get_territory_mapping(self) -> Dict[str, str]:
        """Map App Store Connect territory codes to ISO country codes"""
        # Common mappings - App Store uses ISO 3166-1 alpha-2 codes
        # Big Mac Index uses ISO 3166-1 alpha-3 codes
        mapping = {
            'US': 'USA',
            'USA': 'USA',  # Also handle USA directly
            'GB': 'GBR',
            'CA': 'CAN',
            'AU': 'AUS',
            'DE': 'DEU',
            'FR': 'FRA',
            'IT': 'ITA',
            'ES': 'ESP',
            'NL': 'NLD',
            'BE': 'BEL',
            'CH': 'CHE',
            'AT': 'AUT',
            'SE': 'SWE',
            'NO': 'NOR',
            'DK': 'DNK',
            'FI': 'FIN',
            'IE': 'IRL',
            'PT': 'PRT',
            'GR': 'GRC',
            'PL': 'POL',
            'CZ': 'CZE',
            'HU': 'HUN',
            'RO': 'ROU',
            'BG': 'BGR',
            'HR': 'HRV',
            'SK': 'SVK',
            'SI': 'SVN',
            'EE': 'EST',
            'LV': 'LVA',
            'LT': 'LTU',
            'JP': 'JPN',
            'CN': 'CHN',
            'KR': 'KOR',
            'IN': 'IND',
            'BR': 'BRA',
            'MX': 'MEX',
            'AR': 'ARG',
            'CL': 'CHL',
            'CO': 'COL',
            'PE': 'PER',
            'CR': 'CRI',
            'UY': 'URY',
            'ZA': 'ZAF',
            'NZ': 'NZL',
            'SG': 'SGP',
            'MY': 'MYS',
            'TH': 'THA',
            'PH': 'PHL',
            'ID': 'IDN',
            'VN': 'VNM',
            'TW': 'TWN',
            'HK': 'HKG',
            'TR': 'TUR',
            'RU': 'RUS',
            'IL': 'ISR',
            'AE': 'ARE',
            'SA': 'SAU',
            'QA': 'QAT',
            'KW': 'KWT',
            'BH': 'BHR',
            'OM': 'OMN',
            'BN': 'BRN',
            'PA': 'PAN',
            'BS': 'BHS',
            'BB': 'BRB',
            'TT': 'TTO',
            'AG': 'ATG',
            'KN': 'KNA',
            'LC': 'LCA',
            'VC': 'VCT',
            'SC': 'SYC',
            'AD': 'AND',
            'MC': 'MCO',
            'SM': 'SMR',
            'EG': 'EGY',
            'NG': 'NGA',
            'KE': 'KEN',
        }
        return mapping
    
    def get_all_ratios(self) -> Dict[str, float]:
        """Get ratios for all available countries"""
        if self.data is None or self.usd_price is None:
            return {}
        
        ratios = {}
        territory_mapping = self._get_territory_mapping()
        
        # Get latest data
        latest_date = self.data['date'].max()
        latest_data = self.data[self.data['date'] == latest_date]
        
        # First, get direct country ratios
        for _, row in latest_data.iterrows():
            iso_code = row['iso_a3']
            dollar_price = row['dollar_price']
            
            if pd.notna(dollar_price) and dollar_price > 0:
                ratio = dollar_price / self.usd_price
                
                # Find territory code
                for territory, iso in territory_mapping.items():
                    if iso == iso_code:
                        ratios[territory] = ratio
                        break
        
        # Get Euro area ratio for European countries without specific data
        euro_area_data = latest_data[latest_data['iso_a3'] == 'EUZ']
        euro_ratio = None
        if not euro_area_data.empty:
            euro_dollar_price = euro_area_data.iloc[0]['dollar_price']
            if pd.notna(euro_dollar_price) and euro_dollar_price > 0:
                euro_ratio = euro_dollar_price / self.usd_price
        
        # Add Euro area ratio for ALL European countries using EUR
        # The Big Mac Index uses "EUZ" (Euro area) for these countries
        # These are Tier 1/rich countries that use EUR
        all_euro_countries = {
            'AT': 'AUT',  # Austria
            'BE': 'BEL',  # Belgium
            'NL': 'NLD',  # Netherlands
            'FI': 'FIN',  # Finland
            'IE': 'IRL',  # Ireland
            'PT': 'PRT',  # Portugal
            'GR': 'GRC',  # Greece
            'LU': 'LUX',  # Luxembourg
            'MT': 'MLT',  # Malta
            'CY': 'CYP',  # Cyprus
            'SI': 'SVN',  # Slovenia
            'SK': 'SVK',  # Slovakia
            'EE': 'EST',  # Estonia
            'LV': 'LVA',  # Latvia
            'LT': 'LTU',  # Lithuania
            'HR': 'HRV',  # Croatia
            'FR': 'FRA',  # France - TIER 1
            'ES': 'ESP',  # Spain - TIER 1
            'DE': 'DEU',  # Germany - TIER 1
            'IT': 'ITA',  # Italy - TIER 1
        }
        
        if euro_ratio:
            for territory, iso in all_euro_countries.items():
                if territory not in ratios:  # Only add if not already present
                    ratios[territory] = euro_ratio
        
        # Use similar country proxies for other Tier 1 countries without data
        # Use closest neighbor or similar economy ratios
        proxy_mappings = {
            # Use Switzerland ratio for Liechtenstein (similar economy, uses CHF)
            'LI': ratios.get('CH'),  # Liechtenstein -> Switzerland
            
            # Use Norway ratio for Iceland (similar Nordic economy)
            'IS': ratios.get('NO'),  # Iceland -> Norway
            
            # Use UK ratio for other British territories
            'IM': ratios.get('GB'),  # Isle of Man -> UK
            'JE': ratios.get('GB'),  # Jersey -> UK
            'GG': ratios.get('GB'),  # Guernsey -> UK
            
            # Use Australia ratio for Pacific territories
            'NC': ratios.get('AU'),  # New Caledonia -> Australia
            'PF': ratios.get('AU'),  # French Polynesia -> Australia (via France/Euro)
            
            # Use Canada ratio for similar North American economies
            'BM': ratios.get('CA'),  # Bermuda -> Canada
            
            # Use Singapore ratio for similar Asian economies
            'MO': ratios.get('HK'),  # Macau -> Hong Kong
            
            # Use Israel ratio for similar Middle Eastern economies
            'IL': ratios.get('IL'),  # Already have, but keep for reference
            
            # Use South Korea ratio for similar Asian economies
            'TW': ratios.get('TW'),  # Already have Taiwan
            
            # Use Japan ratio for similar developed Asian economies
            # (Japan already in list)
        }
        
        for territory, proxy_ratio in proxy_mappings.items():
            if proxy_ratio and territory not in ratios:
                ratios[territory] = proxy_ratio
        
        # Add fallback ratios for countries without Big Mac data
        fallback_ratios = self._get_fallback_ratios()
        for territory, ratio in fallback_ratios.items():
            if territory not in ratios:
                ratios[territory] = ratio
        
        # Try to get ratios for countries using similar country proxies
        similar_proxies = self._get_similar_country_proxies()
        for territory, proxy_code in similar_proxies.items():
            if territory not in ratios:
                proxy_ratio = ratios.get(proxy_code)
                if proxy_ratio is None:
                    # Try to get ratio directly
                    proxy_ratio = self.get_country_ratio(proxy_code)
                if proxy_ratio is not None:
                    ratios[territory] = proxy_ratio
        
        return ratios

