import asyncio
import aiohttp
import logging
from typing import Dict, Optional
from datetime import datetime

class PriceClient:
    """Client for fetching cryptocurrency prices"""
    
    def __init__(self):
        self.coingecko_base_url = "https://api.coingecko.com/api/v3"
        self.logger = logging.getLogger(__name__)
    
    async def get_eth_price(self) -> Optional[float]:
        """Get current ETH price in USD from CoinGecko"""
        url = f"{self.coingecko_base_url}/simple/price"
        params = {
            'ids': 'ethereum',
            'vs_currencies': 'usd'
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        eth_price = data.get('ethereum', {}).get('usd')
                        if eth_price:
                            self.logger.debug(f"ETH price fetched: ${eth_price}")
                            return float(eth_price)
        except Exception as e:
            self.logger.error(f"Failed to fetch ETH price: {e}")
        
        # Fallback to reasonable default if API fails
        self.logger.warning("Using fallback ETH price of $2000")
        return 2000.0
    
    async def get_historical_eth_price(self, date: str) -> Optional[float]:
        """Get historical ETH price for a specific date (YYYY-MM-DD format)"""
        url = f"{self.coingecko_base_url}/coins/ethereum/history"
        params = {
            'date': date,
            'localization': 'false'
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        price = data.get('market_data', {}).get('current_price', {}).get('usd')
                        if price:
                            return float(price)
        except Exception as e:
            self.logger.error(f"Failed to fetch historical ETH price for {date}: {e}")
        
        return None

# Global price cache to avoid repeated API calls
_price_cache = {
    'eth_usd': None,
    'last_updated': None,
    'cache_duration': 300  # 5 minutes
}

async def get_current_eth_price() -> float:
    """Get current ETH price with caching"""
    global _price_cache
    
    now = datetime.now()
    
    # Check cache
    if (_price_cache['eth_usd'] is not None and 
        _price_cache['last_updated'] is not None and
        (now - _price_cache['last_updated']).seconds < _price_cache['cache_duration']):
        return _price_cache['eth_usd']
    
    # Fetch new price
    client = PriceClient()
    price = await client.get_eth_price()
    
    if price:
        _price_cache['eth_usd'] = price
        _price_cache['last_updated'] = now
    
    return price or 2000.0  # Fallback