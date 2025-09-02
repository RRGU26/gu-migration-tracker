#!/usr/bin/env python3
"""
Daily Analytics Service
Collects, calculates, and stores all daily metrics including:
- ETH price
- Collection floor prices and supplies  
- Market cap calculations
- Migration percentages (with +26 burned GU)
- Price ratios
- Daily migration activity
"""

import logging
import asyncio
from datetime import datetime, date, timedelta
from typing import Dict, Optional, Tuple

from src.database.database import DatabaseManager
from src.api.opensea_client import OpenSeaClient
from src.api.price_client import get_current_eth_price

class DailyAnalyticsService:
    """Service for collecting and calculating daily analytics"""
    
    def __init__(self, db_path=None):
        # Use provided db_path or default to the main database
        if db_path is None:
            import os
            # Get the path relative to the src directory  
            current_dir = os.path.dirname(__file__)
            db_path = os.path.join(current_dir, '..', '..', 'data', 'gu_migration.db')
        
        self.db = DatabaseManager(db_path)
        self.opensea_client = OpenSeaClient()
        self.logger = logging.getLogger(__name__)
        
        # Constants
        self.BURNED_GU_COUNT = 26  # 26 GU were burned in the new collection
        
        # Get collection IDs
        self.origins_id = self.db.get_collection_id('gu-origins')
        self.undead_id = self.db.get_collection_id('genuine-undead')
        
        if not self.origins_id or not self.undead_id:
            raise ValueError("Collection IDs not found in database")
    
    async def collect_and_store_daily_data(self, target_date: date = None) -> Dict:
        """Collect all data and perform calculations for a specific date"""
        if target_date is None:
            target_date = date.today()
        
        self.logger.info(f"Collecting daily analytics for {target_date}")
        
        try:
            # 1. Get ETH price
            eth_price = await self._get_eth_price()
            if not eth_price:
                self.logger.error("Failed to get ETH price")
                return {'error': 'Could not fetch ETH price'}
            
            # Store ETH price
            self._store_daily_eth_price(target_date, eth_price)
            
            # 2. Get collection data
            origins_data = await self._get_collection_data('gu-origins')
            undead_data = await self._get_collection_data('genuine-undead')
            
            if not origins_data or not undead_data:
                self.logger.error("Failed to get collection data")
                return {'error': 'Could not fetch collection data'}
            
            # 3. Store daily snapshots (existing functionality)
            self._store_daily_snapshot(self.origins_id, target_date, origins_data, eth_price)
            self._store_daily_snapshot(self.undead_id, target_date, undead_data, eth_price)
            
            # 4. Calculate analytics
            analytics = self._calculate_daily_analytics(
                target_date, eth_price, origins_data, undead_data
            )
            
            # 5. Store calculated analytics
            self._store_daily_analytics(target_date, analytics)
            
            self.logger.info(f"Successfully collected and stored analytics for {target_date}")
            
            return {
                'success': True,
                'date': target_date,
                'eth_price': eth_price,
                'analytics': analytics
            }
            
        except Exception as e:
            self.logger.error(f"Failed to collect daily analytics for {target_date}: {e}")
            return {'error': str(e)}
    
    async def _get_eth_price(self) -> Optional[float]:
        """Get current ETH price in USD"""
        try:
            return await get_current_eth_price()
        except Exception as e:
            self.logger.error(f"Error getting ETH price: {e}")
            return None
    
    async def _get_collection_data(self, collection_slug: str) -> Optional[Dict]:
        """Get comprehensive collection data from OpenSea"""
        try:
            data = await self.opensea_client.get_comprehensive_collection_data(collection_slug)
            return data
        except Exception as e:
            self.logger.error(f"Error getting {collection_slug} data: {e}")
            return None
    
    def _store_daily_eth_price(self, price_date: date, eth_price: float):
        """Store daily ETH price"""
        with self.db.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO daily_eth_prices (price_date, eth_price_usd)
                VALUES (?, ?)
            """, (price_date.isoformat(), eth_price))
    
    def _store_daily_snapshot(self, collection_id: int, snapshot_date: date, 
                            collection_data: Dict, eth_price: float):
        """Store daily snapshot (enhanced version of existing functionality)"""
        floor_price_eth = collection_data.get('floor_price', {}).get('eth', 0)
        total_supply = collection_data.get('total_supply', 0)
        
        # Calculate market cap
        market_cap_eth = floor_price_eth * total_supply if floor_price_eth and total_supply else 0
        market_cap_usd = market_cap_eth * eth_price if market_cap_eth else 0
        
        with self.db.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO daily_snapshots (
                    collection_id, snapshot_date, total_supply, floor_price_eth, 
                    floor_price_usd, market_cap_eth, market_cap_usd, volume_24h_eth,
                    volume_24h_usd
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                collection_id, snapshot_date.isoformat(), total_supply,
                floor_price_eth, floor_price_eth * eth_price if floor_price_eth else 0,
                market_cap_eth, market_cap_usd,
                collection_data.get('volume_24h', {}).get('eth', 0),
                collection_data.get('volume_24h', {}).get('usd', 0)
            ))
    
    def _calculate_daily_analytics(self, target_date: date, eth_price: float,
                                 origins_data: Dict, undead_data: Dict) -> Dict:
        """Calculate all daily analytics"""
        
        # Extract collection data
        origins_floor = origins_data.get('floor_price', {}).get('eth', 0)
        origins_supply = origins_data.get('total_supply', 0)
        undead_floor = undead_data.get('floor_price', {}).get('eth', 0)
        undead_supply = undead_data.get('total_supply', 0)
        
        # Calculate market caps
        origins_market_cap = origins_floor * origins_supply * eth_price if origins_floor and origins_supply else 0
        undead_market_cap = undead_floor * undead_supply * eth_price if undead_floor and undead_supply else 0
        combined_market_cap = origins_market_cap + undead_market_cap
        
        # Calculate 24h changes
        origins_floor_change = self._calculate_floor_change(self.origins_id, target_date, origins_floor)
        undead_floor_change = self._calculate_floor_change(self.undead_id, target_date, undead_floor)
        undead_supply_change = self._calculate_supply_change(self.undead_id, target_date, undead_supply)
        
        # Calculate migrations (supply change + 26 burned)
        total_migrations = self.BURNED_GU_COUNT + max(0, undead_supply_change)
        migration_percent = (total_migrations / undead_supply) * 100 if undead_supply > 0 else 0
        
        # Calculate price ratio
        price_ratio = undead_floor / origins_floor if origins_floor > 0 else 0
        
        # Daily new migrations (just the supply change)
        daily_new_migrations = max(0, undead_supply_change)
        
        return {
            'eth_price_usd': eth_price,
            'origins_floor_eth': origins_floor,
            'origins_supply': origins_supply,
            'origins_market_cap_usd': origins_market_cap,
            'origins_floor_change_24h': origins_floor_change,
            'undead_floor_eth': undead_floor,
            'undead_supply': undead_supply,
            'undead_market_cap_usd': undead_market_cap,
            'undead_floor_change_24h': undead_floor_change,
            'undead_supply_change_24h': undead_supply_change,
            'total_migrations': total_migrations,
            'migration_percent': migration_percent,
            'price_ratio': price_ratio,
            'combined_market_cap_usd': combined_market_cap,
            'daily_new_migrations': daily_new_migrations
        }
    
    def _calculate_floor_change(self, collection_id: int, current_date: date, 
                              current_floor: float) -> float:
        """Calculate 24h floor price change percentage"""
        try:
            yesterday = current_date - timedelta(days=1)
            with self.db.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT floor_price_eth FROM daily_snapshots
                    WHERE collection_id = ? AND snapshot_date = ?
                """, (collection_id, yesterday.isoformat()))
                
                row = cursor.fetchone()
                if row and row['floor_price_eth'] and row['floor_price_eth'] > 0:
                    yesterday_floor = row['floor_price_eth']
                    return ((current_floor - yesterday_floor) / yesterday_floor) * 100
                
            return 0.0
        except Exception as e:
            self.logger.error(f"Error calculating floor change: {e}")
            return 0.0
    
    def _calculate_supply_change(self, collection_id: int, current_date: date, 
                               current_supply: int) -> int:
        """Calculate 24h supply change"""
        try:
            yesterday = current_date - timedelta(days=1)
            with self.db.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT total_supply FROM daily_snapshots
                    WHERE collection_id = ? AND snapshot_date = ?
                """, (collection_id, yesterday.isoformat()))
                
                row = cursor.fetchone()
                if row and row['total_supply']:
                    yesterday_supply = row['total_supply']
                    return current_supply - yesterday_supply
                
            return 0
        except Exception as e:
            self.logger.error(f"Error calculating supply change: {e}")
            return 0
    
    def _store_daily_analytics(self, analytics_date: date, analytics: Dict):
        """Store calculated daily analytics"""
        with self.db.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO daily_analytics (
                    analytics_date, eth_price_usd, origins_floor_eth, origins_supply,
                    origins_market_cap_usd, origins_floor_change_24h, undead_floor_eth,
                    undead_supply, undead_market_cap_usd, undead_floor_change_24h,
                    undead_supply_change_24h, total_migrations, migration_percent,
                    price_ratio, combined_market_cap_usd, daily_new_migrations
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                analytics_date.isoformat(),
                analytics['eth_price_usd'],
                analytics['origins_floor_eth'],
                analytics['origins_supply'],
                analytics['origins_market_cap_usd'],
                analytics['origins_floor_change_24h'],
                analytics['undead_floor_eth'],
                analytics['undead_supply'],
                analytics['undead_market_cap_usd'],
                analytics['undead_floor_change_24h'],
                analytics['undead_supply_change_24h'],
                analytics['total_migrations'],
                analytics['migration_percent'],
                analytics['price_ratio'],
                analytics['combined_market_cap_usd'],
                analytics['daily_new_migrations']
            ))
    
    def get_latest_analytics(self) -> Optional[Dict]:
        """Get the most recent analytics data"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT * FROM daily_analytics
                    ORDER BY analytics_date DESC
                    LIMIT 1
                """)
                row = cursor.fetchone()
                
                if row:
                    return dict(row)
                return None
                
        except Exception as e:
            self.logger.error(f"Error getting latest analytics: {e}")
            return None
    
    def get_analytics_for_date(self, target_date: date) -> Optional[Dict]:
        """Get analytics for a specific date"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT * FROM daily_analytics
                    WHERE analytics_date = ?
                """, (target_date.isoformat(),))
                row = cursor.fetchone()
                
                if row:
                    return dict(row)
                return None
                
        except Exception as e:
            self.logger.error(f"Error getting analytics for {target_date}: {e}")
            return None

async def run_daily_analytics_collection(target_date: date = None) -> Dict:
    """Convenience function to run daily analytics collection"""
    service = DailyAnalyticsService()
    return await service.collect_and_store_daily_data(target_date)

if __name__ == "__main__":
    # Test the service
    import asyncio
    result = asyncio.run(run_daily_analytics_collection())
    print(f"Daily analytics result: {result}")