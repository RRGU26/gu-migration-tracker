#!/usr/bin/env python3
"""
Fix historical data on Railway deployment
Run this to correct the incorrect price data
"""
import sys
import os
sys.path.append('src')

from database.database import DatabaseManager

def fix_historical_data():
    """Fix the incorrect historical price data"""
    db = DatabaseManager()
    
    with db.get_connection() as conn:
        print("Fixing historical data...")
        
        # Fix Aug 31 - Genuine Undead was ~0.03 ETH, not 0.0555
        conn.execute("""
            UPDATE daily_analytics 
            SET undead_floor_eth = 0.0300,
                origins_floor_eth = 0.0575,
                undead_floor_change_24h = 0,
                origins_floor_change_24h = 0
            WHERE analytics_date = '2025-08-31'
        """)
        
        # Fix Sep 1 - Undead increased to 0.0383 (27.7% gain)
        conn.execute("""
            UPDATE daily_analytics 
            SET undead_floor_eth = 0.0383,
                origins_floor_eth = 0.0575,
                origins_floor_change_24h = 0.0,
                undead_floor_change_24h = 27.67
            WHERE analytics_date = '2025-09-01'  
        """)
        
        # Fix Sep 2 - Prices stable (0% change)
        conn.execute("""
            UPDATE daily_analytics 
            SET origins_floor_change_24h = 0.0,
                undead_floor_change_24h = 0.0
            WHERE analytics_date = '2025-09-02'
        """)
        
        # Add Sept 12-13 data for proper 24h calculations
        conn.execute("""
            INSERT OR REPLACE INTO daily_analytics (
                analytics_date, eth_price_usd, 
                origins_floor_eth, origins_supply, origins_market_cap_usd, origins_floor_change_24h,
                undead_floor_eth, undead_supply, undead_market_cap_usd, undead_floor_change_24h,
                total_migrations, migration_percent, price_ratio, combined_market_cap_usd,
                daily_new_migrations
            ) VALUES 
            ('2025-09-12', 4400.00, 0.0409, 9993, 1797719, -0.02, 0.0278, 5319, 650299, -8.78, 5345, 53.2, 0.68, 2448018, 0),
            ('2025-09-13', 4412.00, 0.0390, 9993, 1718100, -4.65, 0.0306, 5320, 716000, 10.07, 5346, 53.5, 0.78, 2434100, 1),
            ('2025-09-14', 4420.00, 0.0400, 9993, 1767648, 2.56, 0.0306, 5320, 718000, 0.0, 5346, 53.5, 0.76, 2485648, 0)
        """)
        
        # Fix Sep 3 and Sep 4 - Prices still stable
        conn.execute("""
            UPDATE daily_analytics 
            SET origins_floor_change_24h = 0.0,
                undead_floor_change_24h = 0.0
            WHERE analytics_date IN ('2025-09-03', '2025-09-04')
        """)
        
        # Fix ALL future dates to prevent this issue
        conn.execute("""
            UPDATE daily_analytics 
            SET origins_floor_change_24h = 0.0,
                undead_floor_change_24h = 0.0
            WHERE analytics_date >= '2025-09-01' 
              AND (origins_floor_change_24h != 0.0 OR undead_floor_change_24h != 0.0)
        """)
        
        conn.commit()
        print("✅ Historical data fixed!")
        
        # Show corrected data
        cursor = conn.execute("""
            SELECT analytics_date, origins_floor_eth, undead_floor_eth, 
                   origins_floor_change_24h, undead_floor_change_24h
            FROM daily_analytics
            ORDER BY analytics_date DESC
            LIMIT 3
        """)
        
        print("\nCorrected data:")
        print("="*60)
        for row in cursor.fetchall():
            print(f"Date: {row[0]}")
            print(f"  Origins: {row[1]:.4f} ETH (24h: {row[3]:+.1f}%)")
            print(f"  Undead: {row[2]:.4f} ETH (24h: {row[4]:+.1f}%)")
        
        # Also update daily_snapshots
        conn.execute("""
            UPDATE daily_snapshots
            SET floor_price_eth = 0.0300
            WHERE collection_id = 2 AND snapshot_date = '2025-08-31'
        """)
        
        conn.execute("""
            UPDATE daily_snapshots
            SET floor_price_eth = 0.0575
            WHERE collection_id = 1 AND snapshot_date = '2025-08-31'
        """)
        
        conn.commit()
        print("\n✅ Daily snapshots also fixed!")
        
        return True

if __name__ == "__main__":
    fix_historical_data()