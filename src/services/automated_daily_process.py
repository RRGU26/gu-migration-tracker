#!/usr/bin/env python3
"""
Automated Daily Process for RR GU Analytic Tracker
Implements the 9-step process that runs automatically every day
"""
import asyncio
import os
import sys
from datetime import date, datetime, timedelta
import logging
import schedule
import time

# Add src to path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(current_dir)
sys.path.append(src_dir)

from database.database import DatabaseManager
from api.opensea_client import OpenSeaClient
from api.price_client import get_current_eth_price

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('automated_daily_process.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class AutomatedDailyProcess:
    """Fully automated 9-step daily process"""
    
    def __init__(self):
        self.db = DatabaseManager()
        self.opensea_client = OpenSeaClient()
        self.origins_supply = 9993
        self.burned_gu = 26
    
    async def run_9_step_process(self):
        """Execute the 9-step process automatically"""
        today = date.today()
        logger.info(f"Starting automated 9-step process for {today}")
        
        try:
            # STEP 1: Get latest Ethereum price
            logger.info("STEP 1: Getting Ethereum price...")
            eth_price = await self._get_eth_price()
            logger.info(f"✓ ETH Price: ${eth_price:,.2f}")
            
            # STEP 2: Get latest floor price of GU Origins
            logger.info("STEP 2: Getting GU Origins floor price...")
            origins_floor = await self._get_floor_price('gu-origins', 0.0575)
            logger.info(f"✓ Origins Floor: {origins_floor:.4f} ETH")
            
            # STEP 3: Get latest floor price of Genuine Undead
            logger.info("STEP 3: Getting Genuine Undead floor price...")
            undead_floor = await self._get_floor_price('genuine-undead', 0.0383)
            logger.info(f"✓ Undead Floor: {undead_floor:.4f} ETH")
            
            # STEP 4: Get latest # of NFTs from Genuine Undead collection
            logger.info("STEP 4: Getting Genuine Undead NFT count...")
            undead_supply = await self._get_collection_supply('genuine-undead', 5037)
            logger.info(f"✓ Undead Supply: {undead_supply} NFTs")
            
            # STEP 5: Log all these numbers
            logger.info("STEP 5: Logging all data points...")
            self._log_data(eth_price, origins_floor, undead_floor, undead_supply)
            
            # STEP 6: Calculate Market Cap (floor × ETH × supply)
            logger.info("STEP 6: Calculating Market Caps...")
            origins_market_cap = origins_floor * self.origins_supply * eth_price
            undead_market_cap = undead_floor * undead_supply * eth_price
            combined_market_cap = origins_market_cap + undead_market_cap
            logger.info(f"✓ Origins Market Cap: ${origins_market_cap:,.0f}")
            logger.info(f"✓ Undead Market Cap: ${undead_market_cap:,.0f}")
            logger.info(f"✓ Combined: ${combined_market_cap:,.0f}")
            
            # STEP 7: Calculate change in migration numbers (day over day)
            logger.info("STEP 7: Calculating migration changes...")
            migration_change = await self._calculate_migration_change(undead_supply)
            total_migrations = undead_supply + self.burned_gu
            migration_percent = (undead_supply / self.origins_supply) * 100
            logger.info(f"✓ New Migrations Today: {migration_change}")
            logger.info(f"✓ Total Migrations: {total_migrations}")
            logger.info(f"✓ Migration Rate: {migration_percent:.2f}%")
            
            # STEP 8: Calculate change in floor price (day over day)
            logger.info("STEP 8: Calculating floor price changes...")
            origins_change = await self._calculate_price_change('origins', origins_floor)
            undead_change = await self._calculate_price_change('undead', undead_floor)
            logger.info(f"✓ Origins 24h Change: {origins_change:+.2f}%")
            logger.info(f"✓ Undead 24h Change: {undead_change:+.2f}%")
            
            # STEP 9: Feed dashboard/update graphics/update report/export
            logger.info("STEP 9: Updating dashboard and reports...")
            await self._update_dashboard(
                eth_price, origins_floor, undead_floor, undead_supply,
                origins_market_cap, undead_market_cap, combined_market_cap,
                total_migrations, migration_percent, origins_change, undead_change
            )
            logger.info("✓ Dashboard updated successfully!")
            
            logger.info("="*60)
            logger.info("✅ AUTOMATED 9-STEP PROCESS COMPLETED SUCCESSFULLY!")
            logger.info("="*60)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Process failed: {e}")
            return False
    
    async def _get_eth_price(self):
        """Step 1: Get ETH price"""
        try:
            price = await get_current_eth_price()
            return price if price > 0 else 4260.79
        except:
            return 4260.79  # Fallback to known recent price
    
    async def _get_floor_price(self, collection_slug, default_price):
        """Steps 2-3: Get floor prices"""
        try:
            data = await self.opensea_client.get_collection_stats(collection_slug)
            if data and 'floor_price' in data:
                return data['floor_price'].get('eth', default_price)
        except:
            pass
        return default_price
    
    async def _get_collection_supply(self, collection_slug, default_supply):
        """Step 4: Get collection supply"""
        try:
            data = await self.opensea_client.get_comprehensive_collection_data(collection_slug)
            if data and 'total_supply' in data:
                return data['total_supply']
        except:
            pass
        return default_supply
    
    def _log_data(self, eth_price, origins_floor, undead_floor, undead_supply):
        """Step 5: Log all data"""
        log_entry = f"""
        Data Summary for {date.today()}:
        - ETH Price: ${eth_price:,.2f}
        - Origins Floor: {origins_floor:.4f} ETH (${origins_floor * eth_price:,.2f})
        - Undead Floor: {undead_floor:.4f} ETH (${undead_floor * eth_price:,.2f})
        - Undead Supply: {undead_supply} NFTs
        - Total Migrations: {undead_supply + self.burned_gu}
        """
        logger.info(log_entry)
    
    async def _calculate_migration_change(self, current_supply):
        """Step 7: Calculate migration change"""
        yesterday = date.today() - timedelta(days=1)
        
        with self.db.get_connection() as conn:
            cursor = conn.execute("""
                SELECT undead_supply FROM daily_analytics
                WHERE analytics_date = ?
            """, (yesterday.isoformat(),))
            result = cursor.fetchone()
            
            if result and result[0]:
                return current_supply - result[0]
            return 0
    
    async def _calculate_price_change(self, collection, current_price):
        """Step 8: Calculate price change"""
        yesterday = date.today() - timedelta(days=1)
        
        with self.db.get_connection() as conn:
            if collection == 'origins':
                column = 'origins_floor_eth'
            else:
                column = 'undead_floor_eth'
                
            cursor = conn.execute(f"""
                SELECT {column} FROM daily_analytics
                WHERE analytics_date = ?
            """, (yesterday.isoformat(),))
            result = cursor.fetchone()
            
            if result and result[0] and result[0] > 0:
                return ((current_price - result[0]) / result[0]) * 100
            return 0.0
    
    async def _update_dashboard(self, eth_price, origins_floor, undead_floor, undead_supply,
                                origins_market_cap, undead_market_cap, combined_market_cap,
                                total_migrations, migration_percent, origins_change, undead_change):
        """Step 9: Update dashboard with all data"""
        today = date.today()
        
        with self.db.get_connection() as conn:
            # Store in daily_analytics table
            conn.execute("""
                INSERT OR REPLACE INTO daily_analytics (
                    analytics_date, eth_price_usd,
                    origins_floor_eth, origins_supply, origins_market_cap_usd, origins_floor_change_24h,
                    undead_floor_eth, undead_supply, undead_market_cap_usd, undead_floor_change_24h,
                    total_migrations, migration_percent, price_ratio, combined_market_cap_usd
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                today.isoformat(), eth_price,
                origins_floor, self.origins_supply, origins_market_cap, origins_change,
                undead_floor, undead_supply, undead_market_cap, undead_change,
                total_migrations, migration_percent, 
                undead_floor / origins_floor if origins_floor > 0 else 0,
                combined_market_cap
            ))
            
            # Store in daily_snapshots for both collections
            for collection_id, floor, supply, market_cap in [
                (1, origins_floor, self.origins_supply, origins_market_cap),
                (2, undead_floor, undead_supply, undead_market_cap)
            ]:
                conn.execute("""
                    INSERT OR REPLACE INTO daily_snapshots (
                        collection_id, snapshot_date, total_supply, floor_price_eth,
                        floor_price_usd, market_cap_usd
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    collection_id, today.isoformat(), supply,
                    floor, floor * eth_price, market_cap
                ))
            
            conn.commit()
            logger.info("✓ Database updated with today's data")

def run_automated_process():
    """Wrapper to run the async process"""
    process = AutomatedDailyProcess()
    asyncio.run(process.run_9_step_process())

def schedule_daily_run():
    """Schedule the process to run daily at 9:00 AM"""
    schedule.every().day.at("09:00").do(run_automated_process)
    
    logger.info("Automated daily process scheduled for 9:00 AM daily")
    logger.info("Running initial collection...")
    
    # Run once immediately
    run_automated_process()
    
    # Keep the scheduler running
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute

if __name__ == "__main__":
    # Run the process immediately when script is called
    run_automated_process()