#!/usr/bin/env python3
"""
Initialize database with initial data for Railway deployment
"""
import sys
import os
from datetime import date

sys.path.append('src')

from src.database.database import DatabaseManager

def init_database_with_data():
    """Initialize database and add initial data"""
    print("Initializing database with data...")
    
    # Create database
    db = DatabaseManager('data/gu_migration.db')
    
    # Add initial analytics data so dashboard doesn't show errors
    with db.get_connection() as conn:
        # Add initial data for today
        conn.execute("""
            INSERT OR REPLACE INTO daily_analytics (
                analytics_date, eth_price_usd, origins_floor_eth, origins_supply,
                origins_market_cap_usd, origins_floor_change_24h, undead_floor_eth,
                undead_supply, undead_market_cap_usd, undead_floor_change_24h,
                undead_supply_change_24h, total_migrations, migration_percent,
                price_ratio, combined_market_cap_usd, daily_new_migrations
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            date.today().isoformat(), 4260.79,  # Current date and ETH price
            0.0575, 9993, 2448239, -13.9,       # Origins data
            0.0383, 5037, 821979, -31.0, 0,     # Undead data
            5063, 50.4, 0.666, 3270219, 0       # Migration data
        ))
        
        # Add ETH price
        conn.execute("""
            INSERT OR REPLACE INTO daily_eth_prices (price_date, eth_price_usd)
            VALUES (?, ?)
        """, (date.today().isoformat(), 4260.79))
        
        # Add snapshots for both collections
        conn.execute("""
            INSERT OR REPLACE INTO daily_snapshots (
                collection_id, snapshot_date, total_supply, floor_price_eth,
                floor_price_usd, market_cap_eth, market_cap_usd, volume_24h_eth, volume_24h_usd
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (1, date.today().isoformat(), 9993, 0.0575, 244.83, 574.59, 2448239, 0, 0))
        
        conn.execute("""
            INSERT OR REPLACE INTO daily_snapshots (
                collection_id, snapshot_date, total_supply, floor_price_eth,
                floor_price_usd, market_cap_eth, market_cap_usd, volume_24h_eth, volume_24h_usd
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (2, date.today().isoformat(), 5037, 0.0383, 163.19, 192.92, 821979, 0, 0))
        
        conn.commit()
        print("Database initialized with initial data")

if __name__ == "__main__":
    init_database_with_data()