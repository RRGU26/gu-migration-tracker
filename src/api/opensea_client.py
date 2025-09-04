import asyncio
import aiohttp
import time
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import json
from config.config import Config

class OpenSeaClient:
    def __init__(self):
        self.base_url = Config.OPENSEA_BASE_URL
        self.api_key = Config.OPENSEA_API_KEY
        self.rate_limit = Config.API_RATE_LIMIT
        self.timeout = Config.REQUEST_TIMEOUT
        self.logger = logging.getLogger(__name__)
        
        # Rate limiting
        self.last_request_time = 0
        self.request_count = 0
        
        # Simple cache to prevent duplicate API calls within 5 minutes
        self.cache = {}
        self.cache_duration = 300  # 5 minutes
        
        # Headers for API requests
        self.headers = {
            'X-API-KEY': self.api_key,
            'User-Agent': 'GU-Migration-Tracker/1.0',
            'Accept': 'application/json'
        }
    
    async def _rate_limit(self):
        """Enforce rate limiting"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < (1.0 / self.rate_limit):
            sleep_time = (1.0 / self.rate_limit) - time_since_last
            await asyncio.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    async def _make_request(self, session: aiohttp.ClientSession, endpoint: str, 
                          params: Dict = None) -> Optional[Dict]:
        """Make API request with error handling and rate limiting"""
        await self._rate_limit()
        
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        start_time = time.time()
        
        try:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            async with session.get(url, params=params, headers=self.headers, 
                                 timeout=timeout) as response:
                response_time_ms = int((time.time() - start_time) * 1000)
                
                # Log API call
                from src.database.database import DatabaseManager
                db = DatabaseManager()
                
                if response.status == 200:
                    data = await response.json()
                    db.log_api_call(endpoint, response.status, response_time_ms)
                    self.logger.debug(f"API call successful: {endpoint}")
                    return data
                else:
                    error_msg = f"API error {response.status}: {await response.text()}"
                    db.log_api_call(endpoint, response.status, response_time_ms, error_msg)
                    self.logger.error(error_msg)
                    return None
                    
        except asyncio.TimeoutError:
            response_time_ms = int((time.time() - start_time) * 1000)
            error_msg = f"Request timeout after {self.timeout}s"
            db.log_api_call(endpoint, 0, response_time_ms, error_msg)
            self.logger.error(f"Request timeout for {endpoint}")
            return None
            
        except Exception as e:
            response_time_ms = int((time.time() - start_time) * 1000)
            error_msg = str(e)
            db.log_api_call(endpoint, 0, response_time_ms, error_msg)
            self.logger.error(f"Request failed for {endpoint}: {e}")
            return None
    
    async def get_collection_stats(self, collection_slug: str) -> Optional[Dict]:
        """Get collection statistics from OpenSea"""
        # Check cache first
        cache_key = f"stats_{collection_slug}"
        if cache_key in self.cache:
            cached_time, cached_data = self.cache[cache_key]
            if time.time() - cached_time < self.cache_duration:
                self.logger.info(f"Using cached stats for {collection_slug}")
                return cached_data
        
        endpoint = f"/collections/{collection_slug}/stats"
        
        async with aiohttp.ClientSession() as session:
            response = await self._make_request(session, endpoint)
            
            if response and 'total' in response:
                # OpenSea API v2 returns data in 'total' key, restructure for compatibility
                total = response['total']
                intervals = response.get('intervals', [])
                
                # Find daily and weekly intervals
                one_day = next((i for i in intervals if i.get('interval') == 'one_day'), {})
                seven_day = next((i for i in intervals if i.get('interval') == 'seven_day'), {})
                
                result = {
                    'total_supply': int(total.get('market_cap', 0) / max(total.get('floor_price', 0.001), 0.001)) if total.get('floor_price') else 10000,  # Estimate
                    'floor_price': total.get('floor_price', 0),
                    'one_day_volume': one_day.get('volume', 0),
                    'seven_day_volume': seven_day.get('volume', 0),
                    'average_price': total.get('average_price', 0),
                    'num_owners': total.get('num_owners', 0),
                    'total_volume': total.get('volume', 0),
                    'num_sales': total.get('sales', 0),
                    'market_cap': total.get('market_cap', 0)
                }
                
                # Cache the result
                self.cache[cache_key] = (time.time(), result)
                return result
            return None
    
    async def get_collection_details(self, collection_slug: str) -> Optional[Dict]:
        """Get collection details from OpenSea"""
        endpoint = f"/collections/{collection_slug}"
        
        async with aiohttp.ClientSession() as session:
            response = await self._make_request(session, endpoint)
            return response
    
    async def get_collection_listings(self, collection_slug: str, limit: int = 200) -> List[Dict]:
        """Get collection NFT listings"""
        endpoint = f"/collection/{collection_slug}/nfts"
        params = {
            'limit': limit,
            'order_by': 'created_date',
            'order_direction': 'desc'
        }
        
        async with aiohttp.ClientSession() as session:
            response = await self._make_request(session, endpoint, params)
            
            if response and 'nfts' in response:
                return response['nfts']
            return []
    
    async def get_collection_events(self, collection_slug: str, event_type: str = None, 
                                  limit: int = 300) -> List[Dict]:
        """Get collection events (sales, transfers, etc.)"""
        endpoint = f"/events/collection/{collection_slug}"
        params = {
            'limit': limit,
            'order_by': 'created_date',
            'order_direction': 'desc'
        }
        
        if event_type:
            params['event_type'] = event_type
        
        async with aiohttp.ClientSession() as session:
            response = await self._make_request(session, endpoint, params)
            
            if response and 'asset_events' in response:
                return response['asset_events']
            return []
    
    async def get_nft_owners(self, collection_slug: str, limit: int = 200) -> List[Dict]:
        """Get NFT owners for migration detection"""
        endpoint = f"/collection/{collection_slug}/nfts"
        params = {
            'limit': limit,
            'order_by': 'token_id',
            'order_direction': 'asc'
        }
        
        owners = []
        next_cursor = None
        
        async with aiohttp.ClientSession() as session:
            while True:
                if next_cursor:
                    params['cursor'] = next_cursor
                
                response = await self._make_request(session, endpoint, params)
                
                if not response or 'nfts' not in response:
                    break
                
                for nft in response['nfts']:
                    if nft.get('owners') and len(nft['owners']) > 0:
                        owners.append({
                            'token_id': nft.get('identifier', ''),
                            'holder_address': nft['owners'][0].get('address', ''),
                            'contract_address': nft.get('contract', ''),
                        })
                
                # Check for pagination
                next_cursor = response.get('next')
                if not next_cursor:
                    break
                
                # Prevent infinite loops
                if len(owners) >= 10000:  # Reasonable limit
                    self.logger.warning(f"Reached owner limit for {collection_slug}")
                    break
        
        return owners
    
    async def get_comprehensive_collection_data(self, collection_slug: str) -> Dict[str, Any]:
        """Get comprehensive collection data with rate limiting"""
        # Check cache first
        cache_key = f"comprehensive_{collection_slug}"
        if cache_key in self.cache:
            cached_time, cached_data = self.cache[cache_key]
            if time.time() - cached_time < self.cache_duration:
                self.logger.info(f"Using cached comprehensive data for {collection_slug}")
                return cached_data
        
        # Execute API calls sequentially to avoid rate limiting
        stats = await self.get_collection_stats(collection_slug)
        await asyncio.sleep(2)  # 2 second delay between calls
        
        details = await self.get_collection_details(collection_slug)
        
        # Skip expensive calls that aren't critical for our use case
        listings = []
        sales = []
        owners = []
        
        results = [stats, details, listings, sales, owners]
        
        stats, details, listings, sales, owners = results
        
        # Handle exceptions
        if isinstance(stats, Exception):
            self.logger.error(f"Failed to get stats for {collection_slug}: {stats}")
            stats = None
        if isinstance(details, Exception):
            self.logger.error(f"Failed to get details for {collection_slug}: {details}")
            details = None
        if isinstance(listings, Exception):
            self.logger.error(f"Failed to get listings for {collection_slug}: {listings}")
            listings = []
        if isinstance(sales, Exception):
            self.logger.error(f"Failed to get sales for {collection_slug}: {sales}")
            sales = []
        if isinstance(owners, Exception):
            self.logger.error(f"Failed to get owners for {collection_slug}: {owners}")
            owners = []
        
        return {
            'slug': collection_slug,
            'stats': stats,
            'details': details,
            'listings': listings,
            'sales': sales,
            'owners': owners,
            'fetched_at': datetime.now().isoformat()
        }
    
    def extract_key_metrics(self, collection_data: Dict) -> Dict[str, Any]:
        """Extract key metrics from collection data for database storage"""
        stats = collection_data.get('stats', {})
        details = collection_data.get('details', {})
        listings = collection_data.get('listings', [])
        sales = collection_data.get('sales', [])
        owners = collection_data.get('owners', [])
        
        # Calculate listing percentage
        total_supply = stats.get('total_supply', 0)
        listed_count = len([l for l in listings if l.get('price_info')])
        listed_percentage = (listed_count / max(total_supply, 1)) * 100 if total_supply > 0 else 0
        
        # Calculate recent sales metrics
        recent_sales_24h = len([s for s in sales if s.get('created_date')])
        
        # Extract pricing information
        floor_price_eth = float(stats.get('floor_price', 0)) if stats.get('floor_price') else 0
        
        # Estimate USD price (you may want to integrate with a price API)
        eth_to_usd = 2000  # Placeholder - integrate with price API
        floor_price_usd = floor_price_eth * eth_to_usd
        
        # Calculate market cap
        market_cap_eth = floor_price_eth * total_supply
        market_cap_usd = market_cap_eth * eth_to_usd
        
        # Volume metrics
        volume_24h_eth = float(stats.get('one_day_volume', 0)) if stats.get('one_day_volume') else 0
        volume_7d_eth = float(stats.get('seven_day_volume', 0)) if stats.get('seven_day_volume') else 0
        
        result = {
            'total_supply': int(total_supply),
            'holders_count': len(set(o.get('holder_address', '') for o in owners if o.get('holder_address'))),
            'floor_price_eth': floor_price_eth,
            'floor_price_usd': floor_price_usd,
            'market_cap_eth': market_cap_eth,
            'market_cap_usd': market_cap_usd,
            'volume_24h_eth': volume_24h_eth,
            'volume_24h_usd': volume_24h_eth * eth_to_usd,
            'volume_7d_eth': volume_7d_eth,
            'volume_7d_usd': volume_7d_eth * eth_to_usd,
            'listed_count': listed_count,
            'listed_percentage': round(listed_percentage, 2),
            'average_price_eth': float(stats.get('average_price', 0)) if stats.get('average_price') else 0,
            'average_price_usd': float(stats.get('average_price', 0)) * eth_to_usd if stats.get('average_price') else 0,
            'num_sales_24h': recent_sales_24h
        }
        
        # Cache the result
        self.cache[cache_key] = (time.time(), result)
        return result

# Convenience functions for easy use
async def fetch_collection_data(collection_slug: str) -> Dict[str, Any]:
    """Fetch comprehensive collection data"""
    client = OpenSeaClient()
    return await client.get_comprehensive_collection_data(collection_slug)

async def fetch_all_collections_data() -> Dict[str, Dict]:
    """Fetch data for all configured collections"""
    client = OpenSeaClient()
    results = {}
    
    for key, collection_config in Config.COLLECTIONS.items():
        slug = collection_config['slug']
        data = await client.get_comprehensive_collection_data(slug)
        results[key] = data
    
    return results