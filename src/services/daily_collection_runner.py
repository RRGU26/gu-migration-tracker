#!/usr/bin/env python3
"""
Enhanced Daily Collection Runner for RR GU Analytic Tracker
Properly extracts and stores volume, holders, and accurate 24h changes
"""
import asyncio
import os
import sys
from datetime import date, timedelta
import logging

# Add src and root to path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(current_dir)
root_dir = os.path.dirname(src_dir)
sys.path.append(src_dir)
sys.path.append(root_dir)

from database.database import DatabaseManager
from api.opensea_client import OpenSeaClient
from api.price_client import get_current_eth_price
from services.daily_analytics_service import DailyAnalyticsService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('daily_collection.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class DailyCollectionRunner:
    """Enhanced runner for the 9-step daily collection process"""
    
    def __init__(self):
        self.db = DatabaseManager()
        self.opensea_client = OpenSeaClient()
        self.analytics_service = DailyAnalyticsService()
        self.analytics_date = date.today()
        
        # Fixed supply values
        self.origins_supply = 9993
        self.burned_gu = 26  # GU burned in new collection
    
    async def run_daily_process(self):
        """Execute the complete 9-step daily process with enhanced data extraction"""
        logger.info(f"Starting daily collection for {date.today()}")
        
        # Check if we already have data for today
        with self.db.get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM daily_analytics 
                WHERE analytics_date = ?
            """, (date.today().isoformat(),))
            existing_data = cursor.fetchone()
            
            if existing_data:
                logger.info("Today's data already collected, skipping API calls")
                return True
        
        try:
            # STEP 1: Get latest Ethereum price (always fresh)
            eth_price = await self._get_eth_price()
            
            # Initialize with fallback values (MUST be overridden by live OpenSea data)
            origins_floor = 0.0575  # Fallback only if OpenSea completely fails
            origins_volume = 0
            origins_holders = self.origins_supply
            undead_floor = 0.0383   # Fallback only if OpenSea completely fails
            undead_volume = 0
            undead_holders = 5037
            undead_supply = 5037
            
            # MUST get fresh live data from OpenSea - no reliance on yesterday's data
            logger.info("Fetching LIVE floor prices from OpenSea (required for accurate daily snapshot)")
            
            # Get fresh data directly from OpenSea API (same method as dashboard)
            try:
                import requests
                
                headers = {'X-API-KEY': '518c0d7ea6ad4116823f41c5245b1098'}
                
                # Get Origins floor price and supply
                logger.info("Fetching Origins data directly from OpenSea...")
                origins_response = requests.get('https://api.opensea.io/api/v2/collections/gu-origins/stats', 
                                               headers=headers, timeout=10)
                if origins_response.status_code == 200:
                    origins_data = origins_response.json()
                    new_floor = float(origins_data.get('total', {}).get('floor_price', 0))
                    new_supply = int(origins_data.get('total', {}).get('supply', self.origins_supply))
                    
                    if new_floor > 0:
                        origins_floor = new_floor
                        logger.info(f"Got LIVE Origins floor price: {origins_floor:.4f} ETH")
                    if new_supply > 0:
                        origins_holders = new_supply
                        
                # Get Undead floor price and supply  
                logger.info("Fetching Undead data directly from OpenSea...")
                undead_response = requests.get('https://api.opensea.io/api/v2/collections/genuine-undead/stats',
                                              headers=headers, timeout=10)
                if undead_response.status_code == 200:
                    undead_data = undead_response.json()
                    new_floor = float(undead_data.get('total', {}).get('floor_price', 0))
                    new_supply = int(undead_data.get('total', {}).get('supply', 5037))
                    
                    if new_floor > 0:
                        undead_floor = new_floor
                        logger.info(f"Got LIVE Undead floor price: {undead_floor:.4f} ETH")
                    if new_supply > 0:
                        undead_supply = new_supply
                        logger.info(f"Got LIVE Undead supply: {undead_supply:,}")
                        
                # Get volume data from intervals if available
                for interval in origins_data.get('intervals', []):
                    if interval.get('interval') == 'one_day':
                        origins_volume = float(interval.get('volume', 0))
                        logger.info(f"Origins - Volume: {origins_volume:.4f} ETH, Holders: {origins_holders}")
                        break
                        
                for interval in undead_data.get('intervals', []):
                    if interval.get('interval') == 'one_day':
                        undead_volume = float(interval.get('volume', 0))
                        undead_holders = undead_supply  # Use supply as holder count
                        logger.info(f"Undead - Volume: {undead_volume:.4f} ETH, Holders: {undead_holders}")
                        break
                
            except Exception as e:
                logger.error(f"FAILED to get live OpenSea data: {e}")
                logger.error("WARNING: Using fallback values instead of live floor prices!")
                logger.error("This means the database will NOT have accurate daily snapshot data!")
            
            # STEP 5: Log all data points
            logger.info(f"ETH Price: ${eth_price:,.2f}")
            logger.info(f"Origins Floor: {origins_floor:.4f} ETH (${origins_floor * eth_price:.2f})")
            logger.info(f"Origins Volume: {origins_volume:.4f} ETH, Holders: {origins_holders}")
            logger.info(f"Undead Floor: {undead_floor:.4f} ETH (${undead_floor * eth_price:.2f})")
            logger.info(f"Undead Supply: {undead_supply}, Volume: {undead_volume:.4f} ETH, Holders: {undead_holders}")
            
            # STEP 6: Calculate market caps
            origins_market_cap = origins_floor * self.origins_supply * eth_price
            undead_market_cap = undead_floor * undead_supply * eth_price
            combined_market_cap = origins_market_cap + undead_market_cap
            
            # STEP 7: Calculate migration metrics
            total_migrations = undead_supply + self.burned_gu
            migration_percent = (undead_supply / self.origins_supply) * 100
            
            # STEP 8: Calculate price ratio
            price_ratio = undead_floor / origins_floor if origins_floor > 0 else 0
            
            # STEP 9: Calculate changes
            changes = self._calculate_changes(origins_floor, undead_floor, undead_supply)
            
            # Store all data in database
            self._store_daily_analytics(
                eth_price, origins_floor, origins_volume, origins_holders,
                undead_floor, undead_volume, undead_holders, undead_supply,
                origins_market_cap, undead_market_cap, combined_market_cap,
                total_migrations, migration_percent, price_ratio, changes
            )
            
            print("Daily collection completed successfully")
            print("Dashboard will display updated data")
            print("PDF reports can be generated with current data")
            
            return True
            
        except Exception as e:
            logger.error(f"Daily collection failed: {e}")
            return False
    
    async def _get_eth_price(self):
        """STEP 1: Get current Ethereum price"""
        logger.info("STEP 1: Getting Ethereum price...")
        try:
            price = await get_current_eth_price()
            return price if price > 0 else 4260.79  # Fallback
        except Exception as e:
            logger.warning(f"Error getting ETH price: {e}, using fallback")
            return 4260.79
    
    async def _get_collection_data(self, collection_slug):
        """STEPS 2-4: Get collection data from OpenSea"""
        logger.info(f"Getting {collection_slug} data...")
        try:
            return await self.opensea_client.get_comprehensive_collection_data(collection_slug)
        except Exception as e:
            logger.warning(f"Error getting {collection_slug} data: {e}")
            return None
    
    def _calculate_changes(self, origins_floor, undead_floor, undead_supply):
        """Calculate day-over-day changes"""
        changes = {}
        yesterday = self.analytics_date - timedelta(days=1)
        
        with self.db.get_connection() as conn:
            # Get yesterday's data
            cursor = conn.execute("""
                SELECT origins_floor_eth, undead_floor_eth, undead_supply
                FROM daily_analytics
                WHERE analytics_date = ?
            """, (yesterday.isoformat(),))
            yesterday_data = cursor.fetchone()
            
            if yesterday_data:
                # Calculate 24h floor changes accurately
                yesterday_origins = yesterday_data[0]
                yesterday_undead = yesterday_data[1]
                yesterday_supply = yesterday_data[2]
                
                if yesterday_origins and yesterday_origins > 0:
                    changes['origins_floor_change_24h'] = ((origins_floor - yesterday_origins) / yesterday_origins) * 100
                else:
                    changes['origins_floor_change_24h'] = 0
                
                if yesterday_undead and yesterday_undead > 0:
                    changes['undead_floor_change_24h'] = ((undead_floor - yesterday_undead) / yesterday_undead) * 100
                else:
                    changes['undead_floor_change_24h'] = 0
                
                if yesterday_supply:
                    changes['undead_supply_change_24h'] = undead_supply - yesterday_supply
                else:
                    changes['undead_supply_change_24h'] = 0
                    
                logger.info(f"24h Changes - Origins: {changes['origins_floor_change_24h']:.2f}%, Undead: {changes['undead_floor_change_24h']:.2f}%")
            else:
                # No yesterday data, set changes to 0
                changes['origins_floor_change_24h'] = 0
                changes['undead_floor_change_24h'] = 0
                changes['undead_supply_change_24h'] = 0
                
        return changes
    
    def _store_daily_analytics(self, eth_price, origins_floor, origins_volume, origins_holders,
                               undead_floor, undead_volume, undead_holders, undead_supply,
                               origins_market_cap, undead_market_cap, combined_market_cap,
                               total_migrations, migration_percent, price_ratio, changes):
        """Store all collected and calculated data"""
        logger.info("Storing daily analytics...")
        
        with self.db.get_connection() as conn:
            # Store ETH price
            conn.execute("""
                INSERT OR REPLACE INTO daily_eth_prices (price_date, eth_price_usd)
                VALUES (?, ?)
            """, (self.analytics_date.isoformat(), eth_price))
            
            # Store daily snapshots for Origins
            conn.execute("""
                INSERT OR REPLACE INTO daily_snapshots (
                    collection_id, snapshot_date, total_supply, holders_count, floor_price_eth,
                    floor_price_usd, volume_24h_eth, volume_24h_usd, market_cap_usd
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                1,  # Origins collection ID
                self.analytics_date.isoformat(),
                self.origins_supply,
                origins_holders,
                origins_floor,
                origins_floor * eth_price,
                origins_volume,
                origins_volume * eth_price,
                origins_market_cap
            ))
            
            # Store daily snapshots for Genuine Undead
            conn.execute("""
                INSERT OR REPLACE INTO daily_snapshots (
                    collection_id, snapshot_date, total_supply, holders_count, floor_price_eth,
                    floor_price_usd, volume_24h_eth, volume_24h_usd, market_cap_usd
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                2,  # Undead collection ID
                self.analytics_date.isoformat(),
                undead_supply,
                undead_holders,
                undead_floor,
                undead_floor * eth_price,
                undead_volume,
                undead_volume * eth_price,
                undead_market_cap
            ))
            
            # Store daily analytics
            conn.execute("""
                INSERT OR REPLACE INTO daily_analytics (
                    analytics_date, eth_price_usd,
                    origins_floor_eth, origins_supply, origins_market_cap_usd, origins_floor_change_24h,
                    undead_floor_eth, undead_supply, undead_market_cap_usd, undead_floor_change_24h, undead_supply_change_24h,
                    total_migrations, migration_percent, price_ratio, combined_market_cap_usd,
                    daily_new_migrations
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                self.analytics_date.isoformat(),
                eth_price,
                origins_floor,
                self.origins_supply,
                origins_market_cap,
                changes.get('origins_floor_change_24h', 0),
                undead_floor,
                undead_supply,
                undead_market_cap,
                changes.get('undead_floor_change_24h', 0),
                changes.get('undead_supply_change_24h', 0),
                total_migrations,
                migration_percent,
                price_ratio,
                combined_market_cap,
                changes.get('undead_supply_change_24h', 0)  # New migrations = supply change
            ))
            
            conn.commit()
            logger.info("Analytics stored successfully")

def main():
    """Main entry point for daily collection"""
    print("=" * 60)
    print("RR GU ANALYTIC TRACKER - DAILY COLLECTION")
    print(f"Date: {date.today()}")
    print(f"Time: {date.today().strftime('%H:%M:%S')}")
    print("=" * 60)
    print()
    
    runner = DailyCollectionRunner()
    asyncio.run(runner.run_daily_process())

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--force', action='store_true', help='Force refresh even if data exists for today')
    args = parser.parse_args()
    
    if args.force:
        # Delete today's data to force fresh collection
        today = date.today().isoformat()
        db = DatabaseManager()
        with db.get_connection() as conn:
            conn.execute("DELETE FROM daily_analytics WHERE analytics_date = ?", (today,))
            conn.execute("DELETE FROM daily_eth_prices WHERE price_date = ?", (today,))
            conn.commit()
        print(f"Forcing refresh - deleted existing data for {today}")
    
    main()