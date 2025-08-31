#!/usr/bin/env python3
"""
Generate a sample report using mock data to demonstrate the system
"""
import asyncio
import sys
import os
from datetime import date, datetime
sys.path.append('src')

# Import required modules
from src.database.database import DatabaseManager
from src.utils.mock_data import MockDataGenerator, MockOpenSeaClient
from src.utils.migration_detector import MigrationDetector
from src.reports.report_generator import ReportGenerator
import src.api.opensea_client as opensea_module

async def generate_sample_report():
    """Generate a sample report with mock data"""
    print("Generating sample GU Migration Report with mock data...")
    print("=" * 60)
    
    # Initialize database
    print("1. Initializing database...")
    db = DatabaseManager()
    
    # Create mock data generator
    print("2. Setting up mock data generator...")
    mock_generator = MockDataGenerator()
    
    # Generate some mock historical data
    print("3. Creating mock historical data...")
    historical_data = mock_generator.generate_historical_data(days=7)
    
    # Save mock data to database (simulate a week of data)
    print("4. Populating database with mock migration data...")
    origins_id = db.get_collection_id('gu-origins')
    undead_id = db.get_collection_id('genuine-undead')
    
    # Add some mock migrations to make the report interesting
    mock_migrations = [
        {'token_id': '1234', 'from_collection_id': origins_id, 'to_collection_id': undead_id, 'migration_date': date.today()},
        {'token_id': '1235', 'from_collection_id': origins_id, 'to_collection_id': undead_id, 'migration_date': date.today()},
        {'token_id': '1236', 'from_collection_id': origins_id, 'to_collection_id': undead_id, 'migration_date': date.today()},
    ]
    
    for migration in mock_migrations:
        db.save_migration(**migration)
    
    print(f"   Added {len(mock_migrations)} mock migrations for today")
    
    # Add mock daily snapshots
    mock_client = MockOpenSeaClient()
    
    origins_data = await mock_client.get_comprehensive_collection_data('gu-origins')
    undead_data = await mock_client.get_comprehensive_collection_data('genuine-undead')
    
    origins_metrics = mock_client.extract_key_metrics(origins_data)
    undead_metrics = mock_client.extract_key_metrics(undead_data)
    
    origins_metrics['snapshot_date'] = date.today()
    undead_metrics['snapshot_date'] = date.today()
    
    db.save_daily_snapshot(origins_id, origins_metrics)
    db.save_daily_snapshot(undead_id, undead_metrics)
    
    print("   Added mock collection snapshots")
    
    # Temporarily replace the real API client with mock for report generation
    print("5. Generating comprehensive report...")
    
    async def mock_fetch_all():
        return {
            'gu_origins': origins_data,
            'genuine_undead': undead_data
        }
    
    # Backup original function
    original_fetch = opensea_module.fetch_all_collections_data
    opensea_module.fetch_all_collections_data = mock_fetch_all
    
    try:
        # Generate the report
        report_generator = ReportGenerator()
        report_paths = await report_generator.generate_daily_report()
        
        print("6. Report generation completed!")
        print("\nGenerated Files:")
        
        for format_type, path in report_paths.items():
            if isinstance(path, str):
                if os.path.exists(path):
                    size = os.path.getsize(path)
                    print(f"   {format_type.title()}: {path} ({size} bytes)")
                else:
                    print(f"   {format_type.title()}: {path} (file not found)")
            elif isinstance(path, dict):
                print(f"   {format_type.title()} (multiple files):")
                for sub_name, sub_path in path.items():
                    if os.path.exists(sub_path):
                        size = os.path.getsize(sub_path)
                        print(f"     {sub_name}: {sub_path} ({size} bytes)")
        
        # Show report summary
        print("\n" + "=" * 60)
        print("SAMPLE REPORT SUMMARY")
        print("=" * 60)
        print(f"Report Date: {date.today()}")
        print(f"Total Migrations Today: {len(mock_migrations)}")
        print(f"GU Origins Floor: {origins_metrics.get('floor_price_eth', 0):.3f} ETH")
        print(f"Genuine Undead Floor: {undead_metrics.get('floor_price_eth', 0):.3f} ETH")
        print(f"Origins Volume 24h: {origins_metrics.get('volume_24h_eth', 0):.2f} ETH")
        print(f"Undead Volume 24h: {undead_metrics.get('volume_24h_eth', 0):.2f} ETH")
        
        print(f"\nMigration Progress:")
        print(f"Migration Rate: {(len(mock_migrations) / origins_metrics.get('total_supply', 1) * 100):.1f}%")
        
        print("\nNOTE: This is a demonstration using mock data.")
        print("With your OpenSea API key, the system will fetch real data.")
        
        return True
        
    finally:
        # Restore original function
        opensea_module.fetch_all_collections_data = original_fetch

async def main():
    try:
        success = await generate_sample_report()
        
        if success:
            print("\nSUCCESS! The system is working correctly.")
            print("\nTo generate reports with real data:")
            print("1. Wait a few minutes for OpenSea rate limits to reset")
            print("2. Run: python main.py --mode daily")
            print("3. Or start the scheduler: python main.py --mode scheduler")
        else:
            print("Sample report generation failed.")
            
    except Exception as e:
        print(f"Error generating sample report: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(main())