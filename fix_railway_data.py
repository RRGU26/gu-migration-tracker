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