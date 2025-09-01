#!/usr/bin/env python3
"""
Manual script to collect today's data if scheduler isn't running
"""
import asyncio
import sys
import os
from datetime import date

# Add src to path
sys.path.append('src')

from src.reports.report_generator import ReportGenerator

async def collect_today_data():
    """Collect today's market data and save to database"""
    print(f"Collecting market data for {date.today()}...")
    
    try:
        # Initialize report generator
        report_gen = ReportGenerator()
        
        # Collect and save today's data (this saves daily snapshots)
        report_data = await report_gen._collect_report_data(date.today())
        
        print("SUCCESS: Today's data collected and saved!")
        print(f"ETH Price: ${report_data['eth_price_usd']:,.2f}")
        
        if 'origins' in report_data:
            origins = report_data['origins']['current']
            print(f"GU Origins: {origins['floor_price_eth']:.4f} ETH floor")
        
        if 'undead' in report_data:
            undead = report_data['undead']['current']
            print(f"Genuine Undead: {undead['floor_price_eth']:.4f} ETH floor")
            
        return True
        
    except Exception as e:
        print(f"ERROR: Failed to collect data: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(collect_today_data())
    print(f"\nData collection: {'SUCCESS' if success else 'FAILED'}")